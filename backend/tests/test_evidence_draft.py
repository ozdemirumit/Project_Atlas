from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_invocation_evidence import evidence_fixture, ingest_evidence
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.app import create_app
from atlas.core.persistence.models import (
    OperationalEvidenceKnowledgeDraftClaimModel,
    OperationalEvidenceKnowledgeDraftModel,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.evidence_draft_memory import (
    InMemoryOperationalEvidenceKnowledgeDraftPolicySource,
    InMemoryOperationalEvidenceKnowledgeDraftRepository,
)
from atlas.modules.knowledge.adapters.evidence_draft_postgres import (
    PostgreSQLOperationalEvidenceKnowledgeDraftRepository,
)
from atlas.modules.knowledge.adapters.evidence_draft_synthetic import (
    SyntheticOperationalEvidenceKnowledgeDraftAdapter,
    UnavailableOperationalEvidenceKnowledgeDraftAdapter,
)
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftService,
    _signed_policy,
    build_development_operational_evidence_knowledge_draft_policy,
)
from atlas.modules.knowledge.application.evidence_draft_ports import (
    OperationalEvidenceKnowledgeDraftError,
    OperationalEvidenceKnowledgeDraftUncertainError,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftInstruction,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    OperationalEvidenceKnowledgeDraftReceipt,
    OperationalEvidenceKnowledgeDraftRecord,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_result_is_an_unapproved_non_retrievable_draft"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class RecordingDraftPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, correlation_id
        self.calls.append((organization_id, environment_id))
        if self.deny:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_permission_denied"
            )


class UncertainDraftAdapter:
    available = True

    def __init__(self) -> None:
        self.calls = 0

    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        del instruction
        self.calls += 1
        raise OperationalEvidenceKnowledgeDraftUncertainError(
            "operational_evidence_knowledge_draft_storage_outcome_uncertain"
        )


class TimeoutDraftAdapter:
    available = True

    def __init__(self) -> None:
        self.calls = 0

    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        del instruction
        self.calls += 1
        raise TimeoutError("draft adapter timeout")


class AlteredDraftReceiptAdapter(SyntheticOperationalEvidenceKnowledgeDraftAdapter):
    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        receipt = await super().create_draft(instruction)
        altered = replace(receipt, classification="classification.restricted")
        payload = cast(dict[str, object], asdict(altered))
        payload.pop("canonical_digest")
        return replace(
            altered,
            canonical_digest=OperationalEvidenceKnowledgeDraftService._digest(
                OperationalEvidenceKnowledgeDraftService._normalize(payload)
            ),
        )


class BlockingDraftAdapter(SyntheticOperationalEvidenceKnowledgeDraftAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        self.started.set()
        await self.release.wait()
        return await super().create_draft(instruction)


async def draft_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingDraftPermissionAuthorizer | None = None,
    adapter: SyntheticOperationalEvidenceKnowledgeDraftAdapter
    | UncertainDraftAdapter
    | TimeoutDraftAdapter
    | AlteredDraftReceiptAdapter
    | BlockingDraftAdapter
    | UnavailableOperationalEvidenceKnowledgeDraftAdapter
    | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalEvidenceKnowledgeDraftService,
    InMemoryOperationalEvidenceKnowledgeDraftRepository,
    OperationalEvidenceKnowledgeDraftRecord | None,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    RecordingDraftPermissionAuthorizer,
    SyntheticOperationalEvidenceKnowledgeDraftAdapter
    | UncertainDraftAdapter
    | TimeoutDraftAdapter
    | AlteredDraftReceiptAdapter
    | BlockingDraftAdapter
    | UnavailableOperationalEvidenceKnowledgeDraftAdapter,
    tuple[Any, ...],
]:
    evidence_parts = await evidence_fixture()
    evidence_service, invocation, ingestion_policy = evidence_parts[:3]
    evidence = await ingest_evidence(evidence_service, invocation, ingestion_policy)
    policy = build_development_operational_evidence_knowledge_draft_policy(
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
        issued_at=evidence.ingested_at - timedelta(hours=1),
        expires_at=evidence.ingested_at + timedelta(days=1),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
    repository = InMemoryOperationalEvidenceKnowledgeDraftRepository()
    authorizer = permission_authorizer or RecordingDraftPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticOperationalEvidenceKnowledgeDraftAdapter(
        clock=lambda: evidence.ingested_at
    )
    service = OperationalEvidenceKnowledgeDraftService(
        repository=repository,
        source=evidence_service,
        policy_source=InMemoryOperationalEvidenceKnowledgeDraftPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=evidence.environment_id,
        clock=lambda: evidence.ingested_at,
    )
    return (
        service,
        repository,
        None,
        policy,
        authorizer,
        resolved_adapter,
        (
            evidence,
            evidence_service,
            evidence_parts,
        ),
    )


async def create_draft(
    service: OperationalEvidenceKnowledgeDraftService,
    evidence: Any,
    policy: OperationalEvidenceKnowledgeDraftPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "evidence-draft-001",
) -> OperationalEvidenceKnowledgeDraftRecord:
    return await service.create(
        actor=actor or target_session_operator("subject.connector-independent-knowledge-curator"),
        source_ingestion_id=evidence.ingestion_id,
        curation_option_id=service._option_id(evidence, policy),
        purpose="Create a governed review-only draft from exact operational evidence.",
        unapproved_non_retrievable_draft_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_evidence_draft",
    )


@pytest.mark.asyncio
async def test_evidence_draft_is_immutable_minimized_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, _, policy, authorizer, adapter, source = await draft_fixture(audit_sink=audit)
    evidence = source[0]
    record = await create_draft(service, evidence, policy)
    repeated = await create_draft(service, evidence, policy)

    assert record.instance_state == "draft_operational_knowledge_created"
    assert record.evidence_ingested and record.knowledge_item_created
    assert record.immutable_draft_confirmed and record.encrypted_at_rest
    assert record.knowledge_lifecycle == "draft"
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.knowledge_published
    assert not record.chunks_created and not record.embeddings_created
    assert not record.retrieval_published and not record.model_context_available
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.draft_id == record.draft_id
    assert isinstance(adapter, SyntheticOperationalEvidenceKnowledgeDraftAdapter)
    assert len(adapter.calls) == 1
    assert authorizer.calls == [(evidence.organization_id, evidence.environment_id)]
    assert [item.result_code for item in audit.records] == [
        "operational_evidence_knowledge_draft_requested",
        "operational_evidence_knowledge_draft_source_claimed",
        "operational_evidence_knowledge_draft_created",
    ]


@pytest.mark.asyncio
async def test_evidence_draft_accepts_development_identity_under_default_policy() -> None:
    service, _, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    actor = development_target_session_operator("subject.connector-independent-knowledge-curator")

    record = await create_draft(service, evidence, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.curated_by == actor.subject_id


@pytest.mark.asyncio
async def test_evidence_draft_options_and_inventory_are_authoritative_and_one_way() -> None:
    service, _, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    actor = target_session_operator("subject.connector-independent-knowledge-curator")

    options = await service.list_options(
        actor=actor,
        source_ingestion_id=evidence.ingestion_id,
        correlation_id="cor_draft_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.curation_option_id == service._option_id(evidence, policy)
    assert option.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert option.classification == evidence.classification
    assert option.access_policy_id == evidence.access_policy_id
    assert option.retention_policy_id == evidence.retention_policy_id

    record = await create_draft(service, evidence, policy, actor=actor)
    assert (
        await service.list_options(
            actor=actor,
            source_ingestion_id=evidence.ingestion_id,
            correlation_id="cor_draft_options_consumed",
        )
        == ()
    )
    assert await service.list_drafts(
        actor=actor,
        source_ingestion_id=evidence.ingestion_id,
        correlation_id="cor_draft_inventory",
    ) == (record,)
    foreign_actor = replace(actor, organization_id="organization.foreign")
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="record_not_found"):
        await service.get(
            actor=foreign_actor,
            draft_id=record.draft_id,
            correlation_id="cor_draft_foreign",
        )


@pytest.mark.asyncio
async def test_evidence_draft_rejects_unknown_option_before_claim() -> None:
    service, repository, _, policy, _, adapter, source = await draft_fixture()
    evidence = source[0]
    actor = target_session_operator("subject.connector-independent-knowledge-curator")

    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="option_invalid"):
        await service.create(
            actor=actor,
            source_ingestion_id=evidence.ingestion_id,
            curation_option_id="operational-evidence-knowledge-draft-option.not-authoritative",
            purpose="Create a governed review-only draft from exact operational evidence.",
            unapproved_non_retrievable_draft_acknowledged=True,
            idempotency_key="draft-invalid-option",
            correlation_id="cor_draft_invalid_option",
        )
    assert (
        await repository.get_claim_by_source_in_scope(
            source_ingestion_id=evidence.ingestion_id,
            organization_id=evidence.organization_id,
            environment_id=evidence.environment_id,
        )
        is None
    )
    assert isinstance(adapter, SyntheticOperationalEvidenceKnowledgeDraftAdapter)
    assert adapter.calls == []
    assert policy.canonical_digest != "0" * 64


@pytest.mark.asyncio
async def test_evidence_draft_unavailable_adapter_returns_no_options_and_claims_nothing() -> None:
    service, repository, _, policy, _, adapter, source = await draft_fixture(
        adapter=UnavailableOperationalEvidenceKnowledgeDraftAdapter()
    )
    evidence = source[0]
    actor = target_session_operator("subject.connector-independent-knowledge-curator")

    assert not adapter.available
    assert (
        await service.list_options(
            actor=actor,
            source_ingestion_id=evidence.ingestion_id,
            correlation_id="cor_draft_unavailable_options",
        )
        == ()
    )
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="adapter_unavailable"):
        await create_draft(service, evidence, policy, actor=actor)
    assert (
        await repository.get_claim_by_source_in_scope(
            source_ingestion_id=evidence.ingestion_id,
            organization_id=evidence.organization_id,
            environment_id=evidence.environment_id,
        )
        is None
    )


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_evidence_draft_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, policy, authorizer, adapter, source = await draft_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="assurance_required"):
        await create_draft(
            service,
            source[0],
            policy,
            actor=development_target_session_operator(
                "subject.connector-independent-knowledge-curator"
            ),
        )

    assert authorizer.calls == []
    assert getattr(adapter, "calls", []) in ([], 0)


@pytest.mark.asyncio
async def test_evidence_draft_denies_non_human_identity() -> None:
    service, _, _, policy, authorizer, adapter, source = await draft_fixture()
    actor = replace(
        development_target_session_operator("subject.connector-independent-knowledge-curator"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="human_required"):
        await create_draft(service, source[0], policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "calls", []) in ([], 0)


@pytest.mark.asyncio
async def test_evidence_draft_atomically_rejects_concurrent_second_claim() -> None:
    adapter = BlockingDraftAdapter()
    service, _, _, policy, _, _, source = await draft_fixture(adapter=adapter)
    evidence = source[0]
    first = asyncio.create_task(
        create_draft(service, evidence, policy, key="draft-concurrent-first")
    )
    await adapter.started.wait()
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="idempotency_conflict"):
        await create_draft(service, evidence, policy, key="draft-concurrent-second")
    adapter.release.set()
    record = await first
    assert record.knowledge_item_created and len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_evidence_draft_cancellation_after_claim_is_permanently_consumed() -> None:
    adapter = BlockingDraftAdapter()
    service, repository, _, policy, _, _, source = await draft_fixture(adapter=adapter)
    evidence = source[0]
    attempt = asyncio.create_task(create_draft(service, evidence, policy, key="draft-cancelled"))
    await adapter.started.wait()
    attempt.cancel()
    with pytest.raises(asyncio.CancelledError):
        await attempt

    assert await repository.get_claim_by_source_in_scope(
        source_ingestion_id=evidence.ingestion_id,
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
    )
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="already_claimed"):
        await create_draft(service, evidence, policy, key="draft-cancelled")
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_evidence_draft_denies_actor_reuse_and_permission_before_claim() -> None:
    service, repository, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="separation_required"):
        await create_draft(
            service,
            evidence,
            policy,
            actor=target_session_operator(evidence.ingested_by),
        )
    assert (
        await repository.get_claim_by_source_in_scope(
            source_ingestion_id=evidence.ingestion_id,
            organization_id=evidence.organization_id,
            environment_id=evidence.environment_id,
        )
        is None
    )

    denied_service, denied_repository, _, policy, _, _, source = await draft_fixture(
        permission_authorizer=RecordingDraftPermissionAuthorizer(deny=True)
    )
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="permission_denied"):
        await create_draft(denied_service, evidence, policy)
    assert (
        await denied_repository.get_claim_by_source_in_scope(
            source_ingestion_id=evidence.ingestion_id,
            organization_id=evidence.organization_id,
            environment_id=evidence.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_evidence_draft_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainDraftAdapter()
    service, repository, _, policy, _, _, source = await draft_fixture(adapter=uncertain)
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftUncertainError, match="uncertain"):
        await create_draft(service, evidence, policy)
    assert uncertain.calls == 1
    assert await repository.get_claim_by_source_in_scope(
        source_ingestion_id=evidence.ingestion_id,
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
    )
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="already_claimed"):
        await create_draft(service, evidence, policy)
    assert uncertain.calls == 1

    altered = AlteredDraftReceiptAdapter(clock=lambda: evidence.ingested_at)
    altered_service, _, _, policy, _, _, source = await draft_fixture(adapter=altered)
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftUncertainError, match="receipt_invalid"):
        await create_draft(altered_service, evidence, policy)


@pytest.mark.asyncio
async def test_evidence_draft_timeout_after_claim_is_permanently_consumed() -> None:
    timeout = TimeoutDraftAdapter()
    service, repository, _, policy, _, _, source = await draft_fixture(adapter=timeout)
    evidence = source[0]

    with pytest.raises(OperationalEvidenceKnowledgeDraftUncertainError, match="uncertain"):
        await create_draft(service, evidence, policy, key="draft-timeout")
    assert await repository.get_claim_by_source_in_scope(
        source_ingestion_id=evidence.ingestion_id,
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
    )
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="already_claimed"):
        await create_draft(service, evidence, policy, key="draft-timeout")
    assert timeout.calls == 1


@pytest.mark.asyncio
async def test_evidence_draft_claim_audit_failure_stays_claimed() -> None:
    service, repository, _, policy, _, adapter, source = await draft_fixture(
        audit_sink=FailSecondAuditSink()
    )
    evidence = source[0]
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await create_draft(service, evidence, policy)
    assert await repository.get_claim_by_source_in_scope(
        source_ingestion_id=evidence.ingestion_id,
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
    )
    assert isinstance(adapter, SyntheticOperationalEvidenceKnowledgeDraftAdapter)
    assert len(adapter.calls) == 0


@pytest.mark.asyncio
async def test_evidence_draft_postgres_round_trip_excludes_content() -> None:
    service, repository, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    record = await create_draft(service, evidence, policy)
    claim = await repository.get_claim_by_source_in_scope(
        source_ingestion_id=evidence.ingestion_id,
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
    )
    assert claim is not None
    raw_claim = OperationalEvidenceKnowledgeDraftService._normalize(asdict(claim))
    raw_record = OperationalEvidenceKnowledgeDraftService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalEvidenceKnowledgeDraftRepository._claim_to_domain(raw_claim) == claim
    )
    assert (
        PostgreSQLOperationalEvidenceKnowledgeDraftRepository._record_to_domain(raw_record)
        == record
    )
    for hidden in (
        "evidence_content",
        "draft_content",
        "excerpt",
        "observation_values",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "secret_reference_id",
        "session_handle",
        "idempotency_key",
    ):
        assert hidden not in raw_claim and hidden not in raw_record


@pytest.mark.asyncio
async def test_live_postgres_evidence_drafts_isolate_same_identifiers_by_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, repository, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    base_record = await create_draft(service, evidence, policy)
    base_claim = await repository.get_claim_by_source_in_scope(
        source_ingestion_id=evidence.ingestion_id,
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
    )
    assert base_claim is not None
    suffix = uuid4().hex[:12]
    source_ingestion_id = f"connector-invocation-evidence-ingestion.scoped-draft-{suffix}"
    claim_id = f"operational-evidence-knowledge-draft-claim.scoped-{suffix}"
    draft_id = f"operational-evidence-knowledge-draft.scoped-{suffix}"
    first_claim = replace(
        base_claim,
        claim_id=claim_id,
        source_ingestion_id=source_ingestion_id,
        draft_id=draft_id,
        canonical_digest="0" * 64,
    )
    first_claim = replace(
        first_claim,
        canonical_digest=service._digest(service._claim_payload(first_claim)),
    )
    second_claim = replace(
        first_claim,
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    second_claim = replace(
        second_claim,
        canonical_digest=service._digest(service._claim_payload(second_claim)),
    )
    first_record = replace(
        base_record,
        draft_id=draft_id,
        claim_id=claim_id,
        source_ingestion_id=source_ingestion_id,
        canonical_digest="0" * 64,
    )
    first_record = replace(
        first_record,
        canonical_digest=service._digest(service._record_payload(first_record)),
    )
    second_record = replace(
        first_record,
        organization_id=second_claim.organization_id,
        canonical_digest="0" * 64,
    )
    second_record = replace(
        second_record,
        canonical_digest=service._digest(service._record_payload(second_record)),
    )

    first_engine = create_async_engine(database_url)
    second_engine = create_async_engine(database_url)
    first_repository = PostgreSQLOperationalEvidenceKnowledgeDraftRepository(first_engine)
    second_repository = PostgreSQLOperationalEvidenceKnowledgeDraftRepository(second_engine)
    try:
        assert await first_repository.claim(first_claim)
        assert await second_repository.claim(second_claim)
        assert await first_repository.add(first_record)
        assert await second_repository.add(second_record)
        assert (
            await first_repository.get_in_scope(
                draft_id=draft_id,
                organization_id=first_record.organization_id,
                environment_id=first_record.environment_id,
            )
            == first_record
        )
        assert (
            await second_repository.get_in_scope(
                draft_id=draft_id,
                organization_id=second_record.organization_id,
                environment_id=second_record.environment_id,
            )
            == second_record
        )

        def reject_deserialization(
            raw: dict[str, Any],
        ) -> OperationalEvidenceKnowledgeDraftRecord:
            del raw
            raise AssertionError("foreign tenant payload must not be deserialized")

        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(
                PostgreSQLOperationalEvidenceKnowledgeDraftRepository,
                "_record_to_domain",
                staticmethod(reject_deserialization),
            )
            assert (
                await second_repository.get_in_scope(
                    draft_id=draft_id,
                    organization_id="organization.missing",
                    environment_id=second_record.environment_id,
                )
                is None
            )
        first_inventory = await first_repository.list_scope(
            organization_id=first_record.organization_id,
            environment_id=first_record.environment_id,
        )
        second_inventory = await second_repository.list_scope(
            organization_id=second_record.organization_id,
            environment_id=second_record.environment_id,
        )
        assert first_record in first_inventory and second_record not in first_inventory
        assert second_record in second_inventory and first_record not in second_inventory
    finally:
        async with first_engine.begin() as connection:
            await connection.execute(
                delete(OperationalEvidenceKnowledgeDraftModel).where(
                    OperationalEvidenceKnowledgeDraftModel.draft_id == draft_id
                )
            )
            await connection.execute(
                delete(OperationalEvidenceKnowledgeDraftClaimModel).where(
                    OperationalEvidenceKnowledgeDraftClaimModel.claim_id == claim_id
                )
            )
        await first_repository.close()
        await second_repository.close()


def test_live_postgres_populated_legacy_draft_migration_preserves_digests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    monkeypatch.setenv("ATLAS_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    suffix = uuid4().hex[:12]
    organization_id = f"organization.legacy-draft-{suffix}"
    second_organization_id = f"organization.legacy-draft-other-{suffix}"
    environment_id = "environment.development"
    claim_id = f"operational-evidence-knowledge-draft-claim.legacy-{suffix}"
    draft_id = f"operational-evidence-knowledge-draft.legacy-{suffix}"
    source_ingestion_id = f"connector-invocation-evidence-ingestion.legacy-{suffix}"
    expected_digests = {
        "operational_evidence_knowledge_draft_claims": "7" * 64,
        "operational_evidence_knowledge_drafts": "8" * 64,
    }
    engine = create_engine(database_url)
    command.downgrade(config, "20260825_0162")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO operational_evidence_knowledge_draft_claims "
                    "(claim_id, source_ingestion_id, draft_id, claimed_by, idempotency_digest, "
                    "organization_id, environment_id, canonical_digest, payload) VALUES "
                    "(:claim_id, :source_id, :draft_id, :actor, :idem, :organization_id, "
                    ":environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "claim_id": claim_id,
                    "source_id": source_ingestion_id,
                    "draft_id": draft_id,
                    "actor": f"subject.legacy-draft-{suffix}",
                    "idem": "9" * 64,
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["operational_evidence_knowledge_draft_claims"],
                    "payload": json.dumps({"legacy": "draft-claim"}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO operational_evidence_knowledge_drafts "
                    "(draft_id, claim_id, source_ingestion_id, instance_id, capability_id, "
                    "evidence_package_id, curated_by, organization_id, environment_id, "
                    "canonical_digest, payload) VALUES (:draft_id, :claim_id, :source_id, "
                    ":instance_id, :capability_id, :package_id, :actor, :organization_id, "
                    ":environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "draft_id": draft_id,
                    "claim_id": claim_id,
                    "source_id": source_ingestion_id,
                    "instance_id": f"connector-instance.legacy-draft-{suffix}",
                    "capability_id": "storage.health.read",
                    "package_id": f"evidence-package.legacy-draft-{suffix}",
                    "actor": f"subject.legacy-draft-{suffix}",
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["operational_evidence_knowledge_drafts"],
                    "payload": json.dumps({"legacy": "draft-record"}),
                },
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            for table_name, expected in expected_digests.items():
                actual = connection.execute(
                    text(
                        f"SELECT canonical_digest FROM {table_name} "
                        "WHERE organization_id = :organization_id "
                        "AND environment_id = :environment_id"
                    ),
                    {
                        "organization_id": organization_id,
                        "environment_id": environment_id,
                    },
                ).scalar_one()
                assert actual == expected
        schema = inspect(engine)
        assert schema.get_pk_constraint("operational_evidence_knowledge_draft_claims")[
            "constrained_columns"
        ] == ["claim_id", "organization_id", "environment_id"]
        assert schema.get_pk_constraint("operational_evidence_knowledge_drafts")[
            "constrained_columns"
        ] == ["draft_id", "organization_id", "environment_id"]
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO operational_evidence_knowledge_draft_claims "
                    "(claim_id, source_ingestion_id, draft_id, claimed_by, idempotency_digest, "
                    "organization_id, environment_id, canonical_digest, payload) "
                    "SELECT claim_id, source_ingestion_id, draft_id, claimed_by, "
                    "idempotency_digest, :second_organization_id, environment_id, "
                    "canonical_digest, payload FROM operational_evidence_knowledge_draft_claims "
                    "WHERE organization_id = :organization_id AND claim_id = :claim_id"
                ),
                {
                    "second_organization_id": second_organization_id,
                    "organization_id": organization_id,
                    "claim_id": claim_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO operational_evidence_knowledge_drafts "
                    "(draft_id, claim_id, source_ingestion_id, instance_id, capability_id, "
                    "evidence_package_id, curated_by, organization_id, environment_id, "
                    "canonical_digest, payload) SELECT draft_id, claim_id, "
                    "source_ingestion_id, instance_id, capability_id, evidence_package_id, "
                    "curated_by, :second_organization_id, environment_id, canonical_digest, "
                    "payload FROM operational_evidence_knowledge_drafts "
                    "WHERE organization_id = :organization_id AND draft_id = :draft_id"
                ),
                {
                    "second_organization_id": second_organization_id,
                    "organization_id": organization_id,
                    "draft_id": draft_id,
                },
            )

        with pytest.raises(RuntimeError, match="identifiers overlap between tenants"):
            command.downgrade(config, "20260825_0162")
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM operational_evidence_knowledge_drafts "
                    "WHERE source_ingestion_id = :source_ingestion_id"
                ),
                {"source_ingestion_id": source_ingestion_id},
            )
            connection.execute(
                text(
                    "DELETE FROM operational_evidence_knowledge_draft_claims "
                    "WHERE source_ingestion_id = :source_ingestion_id"
                ),
                {"source_ingestion_id": source_ingestion_id},
            )
        command.upgrade(config, "head")
        engine.dispose()


def test_evidence_draft_api_forbids_content_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, _, policy, _, _, source = asyncio.run(draft_fixture())
    evidence, evidence_service, evidence_parts = source
    bounded = evidence_parts[5]
    bounded_service, authorization_service, target_service, runtime_service, brokerage_service = (
        bounded[:5]
    )
    runtime_fixture = bounded[5]
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_configuration_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = target_session_operator("subject.connector-independent-knowledge-curator")
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.operational-evidence-knowledge-draft-input.v1",
        "source_ingestion_id": evidence.ingestion_id,
        "curation_option_id": service._option_id(evidence, policy),
        "purpose": "Create a governed review-only draft from exact operational evidence.",
        ACKNOWLEDGEMENT_FIELD: True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_configuration_service,
            credential_assignment_service=assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=target_service,
            invocation_authorization_service=authorization_service,
            bounded_invocation_service=bounded_service,
            invocation_evidence_service=evidence_service,
            operational_evidence_knowledge_draft_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/knowledge/operational-evidence-drafts"
        options = client.get(
            f"{endpoint}/options", params={"source_ingestion_id": evidence.ingestion_id}
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "draft-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "draft_content": "trusted-looking injected content"},
            headers={
                "Idempotency-Key": "draft-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        forged_policy = client.post(
            endpoint,
            json={
                **payload,
                "curation_policy_id": policy.policy_id,
                "curation_policy_digest": policy.canonical_digest,
                "classification": "classification.public",
                "retention_policy_id": "retention-policy.browser-controlled",
            },
            headers={
                "Idempotency-Key": "draft-api-forged",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "draft-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        draft_id = created.json()["data"]["draft_id"]
        read = client.get(f"{endpoint}/{draft_id}")
        inventory = client.get(endpoint, params={"source_ingestion_id": evidence.ingestion_id})
        consumed_options = client.get(
            f"{endpoint}/options", params={"source_ingestion_id": evidence.ingestion_id}
        )

    assert options.status_code == 200 and len(options.json()["data"]) == 1
    assert options.json()["data"][0]["curation_option_id"] == payload["curation_option_id"]
    assert denied.status_code == 403
    assert forbidden.status_code == forged_policy.status_code == 422
    assert read.status_code == inventory.status_code == consumed_options.status_code == 200
    assert len(inventory.json()["data"]) == 1 and consumed_options.json()["data"] == []
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["knowledge_lifecycle"] == "draft"
    assert data["knowledge_item_created"] is True
    assert data["knowledge_approved"] is False
    assert data["retrieval_published"] is False
    assert data["model_context_available"] is False
    for hidden in (
        "evidence_content",
        "draft_content",
        "excerpt",
        "observation_values",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
        "claim_id",
        "organization_id",
        "environment_id",
        "curated_by",
        "purpose",
        "draft_artifact_id",
        "draft_content_digest",
    ):
        assert hidden not in data
