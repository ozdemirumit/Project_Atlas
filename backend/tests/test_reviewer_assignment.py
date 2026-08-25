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
from test_draft_review_request import request_review, review_request_fixture
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.app import create_app
from atlas.core.persistence.models import (
    OperationalKnowledgeReviewerAssignmentClaimModel,
    OperationalKnowledgeReviewerAssignmentModel,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.reviewer_assignment_memory import (
    InMemoryOperationalKnowledgeReviewerAssignmentPolicySource,
    InMemoryOperationalKnowledgeReviewerAssignmentRepository,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_postgres import (
    PostgreSQLOperationalKnowledgeReviewerAssignmentRepository,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_synthetic import (
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter,
    UnavailableOperationalKnowledgeReviewerAssignmentAdapter,
)
from atlas.modules.knowledge.application.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentService,
    _signed_policy,
    build_development_operational_knowledge_reviewer_assignment_policy,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentError,
    OperationalKnowledgeReviewerAssignmentUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentInstruction,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentReceipt,
    OperationalKnowledgeReviewerAssignmentRecord,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_assignment_opens_no_content_and_records_no_decision"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class RecordingReviewerAssignmentPermissionAuthorizer:
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
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_permission_denied"
            )


class UncertainReviewerAssignmentAdapter:
    available = True
    adapter_id = "operational-knowledge-reviewer-assignment-adapter.synthetic"
    attestor_id = "subject.operational-knowledge-reviewer-assignment-adapter-attestor"

    def __init__(self) -> None:
        self.calls = 0

    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        del instruction
        self.calls += 1
        raise OperationalKnowledgeReviewerAssignmentUncertainError(
            "operational_knowledge_reviewer_assignment_directory_outcome_uncertain"
        )


class AlteredReviewerAssignmentReceiptAdapter(
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter
):
    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        receipt = await super().assign_reviewers(instruction)
        altered = replace(
            receipt,
            routing_digest="f" * 64,
        )
        payload = cast(dict[str, object], asdict(altered))
        payload.pop("canonical_digest")
        return replace(
            altered,
            canonical_digest=OperationalKnowledgeReviewerAssignmentService._digest(
                OperationalKnowledgeReviewerAssignmentService._normalize(payload)
            ),
        )


class BlockingReviewerAssignmentAdapter(SyntheticOperationalKnowledgeReviewerAssignmentAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        self.started.set()
        await self.release.wait()
        return await super().assign_reviewers(instruction)


class VanishingReviewerAssignmentPolicySource(
    InMemoryOperationalKnowledgeReviewerAssignmentPolicySource
):
    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot | None:
        del policy_id, organization_id, environment_id
        return None


async def reviewer_assignment_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingReviewerAssignmentPermissionAuthorizer | None = None,
    adapter: SyntheticOperationalKnowledgeReviewerAssignmentAdapter
    | UncertainReviewerAssignmentAdapter
    | AlteredReviewerAssignmentReceiptAdapter
    | BlockingReviewerAssignmentAdapter
    | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeReviewerAssignmentService,
    InMemoryOperationalKnowledgeReviewerAssignmentRepository,
    OperationalKnowledgeReviewRequestRecord,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    RecordingReviewerAssignmentPermissionAuthorizer,
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter
    | UncertainReviewerAssignmentAdapter
    | AlteredReviewerAssignmentReceiptAdapter
    | BlockingReviewerAssignmentAdapter,
    tuple[Any, ...],
]:
    review_parts = await review_request_fixture()
    review_service, _, draft, review_policy, *_ = review_parts
    review_request = await request_review(review_service, draft, review_policy)
    policy = build_development_operational_knowledge_reviewer_assignment_policy(
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
        issued_at=review_request.created_at - timedelta(hours=1),
        expires_at=review_request.created_at + timedelta(days=1),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
    repository = InMemoryOperationalKnowledgeReviewerAssignmentRepository()
    authorizer = permission_authorizer or RecordingReviewerAssignmentPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticOperationalKnowledgeReviewerAssignmentAdapter(
        clock=lambda: review_request.created_at
    )
    service = OperationalKnowledgeReviewerAssignmentService(
        repository=repository,
        source=review_service,
        policy_source=InMemoryOperationalKnowledgeReviewerAssignmentPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=review_request.environment_id,
        clock=lambda: review_request.created_at,
    )
    return (
        service,
        repository,
        review_request,
        policy,
        authorizer,
        resolved_adapter,
        review_parts,
    )


async def assign_reviewers(
    service: OperationalKnowledgeReviewerAssignmentService,
    review_request: OperationalKnowledgeReviewRequestRecord,
    policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "knowledge-reviewer-assignment-001",
) -> OperationalKnowledgeReviewerAssignmentRecord:
    resolved_actor = actor or target_session_operator("subject.knowledge-review-coordinator")
    return await service.create(
        actor=resolved_actor,
        source_review_request_id=review_request.review_request_id,
        assignment_option_id=service._option_id(review_request, policy),
        purpose="Assign distinct eligible domain and security reviewers without exposing identity.",
        assignment_only_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_knowledge_reviewer_assignment",
    )


@pytest.mark.asyncio
async def test_reviewer_assignment_is_minimized_distinct_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture(
        audit_sink=audit
    )
    record = await assign_reviewers(service, review_request, policy)
    repeated = await assign_reviewers(service, review_request, policy)

    assert record.knowledge_lifecycle == "reviewer_assigned"
    assert record.reviewer_assigned and record.immutable_assignments_confirmed
    assert record.domain_status == record.security_status == "assigned"
    assert record.domain_assignment_id != record.security_assignment_id
    assert record.domain_reviewer_subject_digest != record.security_reviewer_subject_digest
    assert not record.content_inspection_opened
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.retrieval_published
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.assignment_set_id == record.assignment_set_id
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 1
    assert authorizer.calls == [(review_request.organization_id, review_request.environment_id)]
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_reviewer_assignment_requested",
        "operational_knowledge_review_request_claimed_for_assignment",
        "operational_knowledge_reviewers_assigned",
    ]


@pytest.mark.asyncio
async def test_reviewer_assignment_inventory_and_options_are_authoritative() -> None:
    service, _, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    actor = target_session_operator("subject.knowledge-review-coordinator")

    options = await service.list_options(
        actor=actor,
        source_review_request_id=review_request.review_request_id,
        correlation_id="cor_assignment_options",
    )
    assert len(options) == 1
    option = options[0]
    assert option.assignment_option_id == service._option_id(review_request, policy)
    assert option.assignment_policy_id == policy.policy_id
    assert option.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert option.domain_track_code == "review-track.domain"
    assert option.security_track_code == "review-track.security"
    assert (
        await service.list_assignments(
            actor=actor,
            source_review_request_id=review_request.review_request_id,
            correlation_id="cor_assignment_inventory_empty",
        )
        == ()
    )

    record = await assign_reviewers(service, review_request, policy, actor=actor)
    assert (
        await service.list_options(
            actor=actor,
            source_review_request_id=review_request.review_request_id,
            correlation_id="cor_assignment_options_consumed",
        )
        == ()
    )
    inventory = await service.list_assignments(
        actor=actor,
        source_review_request_id=review_request.review_request_id,
        correlation_id="cor_assignment_inventory",
    )
    assert inventory == (record,)


@pytest.mark.asyncio
async def test_reviewer_assignment_repository_accepts_identical_ids_in_distinct_tenants() -> None:
    service, repository, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    record = await assign_reviewers(service, review_request, policy)
    claim = await repository.get_claim_by_source_in_scope(
        source_review_request_id=review_request.review_request_id,
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
    )
    assert claim is not None
    foreign_claim = replace(
        claim,
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    foreign_claim = replace(
        foreign_claim,
        canonical_digest=service._digest(service._claim_payload(foreign_claim)),
    )
    foreign_record = replace(
        record,
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    foreign_record = replace(
        foreign_record,
        canonical_digest=service._digest(service._record_payload(foreign_record)),
    )

    assert await repository.claim(foreign_claim)
    assert await repository.add(foreign_record)
    assert (
        await repository.get_in_scope(
            assignment_set_id=record.assignment_set_id,
            organization_id=review_request.organization_id,
            environment_id=review_request.environment_id,
        )
        == record
    )
    assert (
        await repository.get_in_scope(
            assignment_set_id=foreign_record.assignment_set_id,
            organization_id=foreign_record.organization_id,
            environment_id=foreign_record.environment_id,
        )
        == foreign_record
    )


@pytest.mark.asyncio
async def test_live_postgres_reviewer_assignments_isolate_same_identifiers_before_deserialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, repository, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    base_record = await assign_reviewers(service, review_request, policy)
    base_claim = await repository.get_claim_by_source_in_scope(
        source_review_request_id=review_request.review_request_id,
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
    )
    assert base_claim is not None
    suffix = uuid4().hex[:12]
    claim_id = f"operational-knowledge-reviewer-assignment-claim.scoped-{suffix}"
    assignment_set_id = f"operational-knowledge-reviewer-assignment.scoped-{suffix}"
    source_review_request_id = f"operational-knowledge-review-request.scoped-{suffix}"
    first_claim = replace(
        base_claim,
        claim_id=claim_id,
        assignment_set_id=assignment_set_id,
        source_review_request_id=source_review_request_id,
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
        assignment_set_id=assignment_set_id,
        claim_id=claim_id,
        source_review_request_id=source_review_request_id,
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

    async def exercise_repository() -> None:
        first_engine = create_async_engine(database_url)
        second_engine = create_async_engine(database_url)
        race_claim_id = f"operational-knowledge-reviewer-assignment-claim.race-{suffix}"
        first_repository = PostgreSQLOperationalKnowledgeReviewerAssignmentRepository(first_engine)
        second_repository = PostgreSQLOperationalKnowledgeReviewerAssignmentRepository(
            second_engine
        )
        try:
            assert await first_repository.claim(first_claim)
            assert await second_repository.claim(second_claim)
            assert await first_repository.add(first_record)
            assert await second_repository.add(second_record)
            assert (
                await first_repository.get_in_scope(
                    assignment_set_id=assignment_set_id,
                    organization_id=first_record.organization_id,
                    environment_id=first_record.environment_id,
                )
                == first_record
            )
            assert (
                await second_repository.get_in_scope(
                    assignment_set_id=assignment_set_id,
                    organization_id=second_record.organization_id,
                    environment_id=second_record.environment_id,
                )
                == second_record
            )
            race_claim = replace(
                first_claim,
                claim_id=race_claim_id,
                assignment_set_id=f"operational-knowledge-reviewer-assignment.race-{suffix}",
                source_review_request_id=(
                    f"operational-knowledge-review-request.assignment-race-{suffix}"
                ),
                idempotency_digest="a" * 64,
                canonical_digest="0" * 64,
            )
            race_claim = replace(
                race_claim,
                canonical_digest=service._digest(service._claim_payload(race_claim)),
            )
            race_results = await asyncio.gather(
                first_repository.claim(race_claim),
                second_repository.claim(race_claim),
            )
            assert sorted(race_results) == [False, True]

            def reject_deserialization(
                raw: dict[str, Any],
            ) -> OperationalKnowledgeReviewerAssignmentRecord:
                del raw
                raise AssertionError("foreign tenant payload must not be deserialized")

            with monkeypatch.context() as scoped_patch:
                scoped_patch.setattr(
                    PostgreSQLOperationalKnowledgeReviewerAssignmentRepository,
                    "_record_to_domain",
                    staticmethod(reject_deserialization),
                )
                assert (
                    await second_repository.get_in_scope(
                        assignment_set_id=assignment_set_id,
                        organization_id="organization.missing",
                        environment_id=second_record.environment_id,
                    )
                    is None
                )
            async with first_engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE operational_knowledge_reviewer_assignments "
                        "SET payload = jsonb_set(payload, '{organization_id}', "
                        "CAST(:foreign_scope AS JSONB), false) "
                        "WHERE assignment_set_id = :assignment_set_id "
                        "AND organization_id = :organization_id "
                        "AND environment_id = :environment_id"
                    ),
                    {
                        "foreign_scope": json.dumps("organization.foreign"),
                        "assignment_set_id": assignment_set_id,
                        "organization_id": first_record.organization_id,
                        "environment_id": first_record.environment_id,
                    },
                )
            with pytest.raises(
                OperationalKnowledgeReviewerAssignmentError,
                match="persistence_integrity_failed",
            ):
                await first_repository.get_in_scope(
                    assignment_set_id=assignment_set_id,
                    organization_id=first_record.organization_id,
                    environment_id=first_record.environment_id,
                )
        finally:
            async with first_engine.begin() as connection:
                await connection.execute(
                    delete(OperationalKnowledgeReviewerAssignmentModel).where(
                        OperationalKnowledgeReviewerAssignmentModel.assignment_set_id
                        == assignment_set_id
                    )
                )
                await connection.execute(
                    delete(OperationalKnowledgeReviewerAssignmentClaimModel).where(
                        OperationalKnowledgeReviewerAssignmentClaimModel.claim_id.in_(
                            [claim_id, race_claim_id]
                        )
                    )
                )
            await first_repository.close()
            await second_repository.close()

    def run_with_selector_loop() -> None:
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(exercise_repository())

    await asyncio.to_thread(run_with_selector_loop)


def test_live_postgres_reviewer_assignment_migration_round_trip_and_collision_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    monkeypatch.setenv("ATLAS_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    suffix = uuid4().hex[:12]
    organization_id = f"organization.legacy-assignment-{suffix}"
    second_organization_id = f"organization.legacy-assignment-other-{suffix}"
    environment_id = "environment.development"
    claim_id = f"operational-knowledge-reviewer-assignment-claim.legacy-{suffix}"
    assignment_set_id = f"operational-knowledge-reviewer-assignment.legacy-{suffix}"
    source_review_request_id = f"operational-knowledge-review-request.legacy-assign-{suffix}"
    expected_digests = {
        "operational_knowledge_reviewer_assignment_claims": "7" * 64,
        "operational_knowledge_reviewer_assignments": "8" * 64,
    }
    engine = create_engine(database_url)
    command.downgrade(config, "20260825_0164")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_reviewer_assignment_claims "
                    "(claim_id, source_review_request_id, assignment_set_id, claimed_by, "
                    "idempotency_digest, organization_id, environment_id, canonical_digest, "
                    "payload) VALUES (:claim_id, :source_id, :assignment_id, :actor, :idem, "
                    ":organization_id, :environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "claim_id": claim_id,
                    "source_id": source_review_request_id,
                    "assignment_id": assignment_set_id,
                    "actor": f"subject.legacy-assignment-{suffix}",
                    "idem": "9" * 64,
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["operational_knowledge_reviewer_assignment_claims"],
                    "payload": json.dumps(
                        {
                            "claim_id": claim_id,
                            "source_review_request_id": source_review_request_id,
                            "assignment_set_id": assignment_set_id,
                            "claimed_by": f"subject.legacy-assignment-{suffix}",
                            "idempotency_digest": "9" * 64,
                            "organization_id": organization_id,
                            "environment_id": environment_id,
                            "canonical_digest": expected_digests[
                                "operational_knowledge_reviewer_assignment_claims"
                            ],
                        }
                    ),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_reviewer_assignments "
                    "(assignment_set_id, claim_id, source_review_request_id, knowledge_item_id, "
                    "requested_by, organization_id, environment_id, canonical_digest, payload) "
                    "VALUES (:assignment_id, :claim_id, :source_id, :knowledge_id, :actor, "
                    ":organization_id, :environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "assignment_id": assignment_set_id,
                    "claim_id": claim_id,
                    "source_id": source_review_request_id,
                    "knowledge_id": f"knowledge-item.legacy-assignment-{suffix}",
                    "actor": f"subject.legacy-assignment-{suffix}",
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["operational_knowledge_reviewer_assignments"],
                    "payload": json.dumps(
                        {
                            "assignment_set_id": assignment_set_id,
                            "claim_id": claim_id,
                            "source_review_request_id": source_review_request_id,
                            "knowledge_item_id": f"knowledge-item.legacy-assignment-{suffix}",
                            "requested_by": f"subject.legacy-assignment-{suffix}",
                            "organization_id": organization_id,
                            "environment_id": environment_id,
                            "canonical_digest": expected_digests[
                                "operational_knowledge_reviewer_assignments"
                            ],
                        }
                    ),
                },
            )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE operational_knowledge_reviewer_assignment_claims "
                    "SET payload = payload || CAST(:patch AS JSONB) WHERE claim_id = :claim_id"
                ),
                {
                    "claim_id": claim_id,
                    "patch": json.dumps({"organization_id": second_organization_id}),
                },
            )
        with pytest.raises(RuntimeError, match="indexed columns and immutable payloads disagree"):
            command.upgrade(config, "head")
        assert inspect(engine).get_pk_constraint(
            "operational_knowledge_reviewer_assignment_claims"
        )["constrained_columns"] == ["claim_id"]
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE operational_knowledge_reviewer_assignment_claims "
                    "SET payload = payload || CAST(:patch AS JSONB) WHERE claim_id = :claim_id"
                ),
                {
                    "claim_id": claim_id,
                    "patch": json.dumps({"organization_id": organization_id}),
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
        assert schema.get_pk_constraint("operational_knowledge_reviewer_assignment_claims")[
            "constrained_columns"
        ] == ["claim_id", "organization_id", "environment_id"]
        assert schema.get_pk_constraint("operational_knowledge_reviewer_assignments")[
            "constrained_columns"
        ] == ["assignment_set_id", "organization_id", "environment_id"]

        command.downgrade(config, "20260825_0164")
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_reviewer_assignment_claims "
                    "(claim_id, source_review_request_id, assignment_set_id, claimed_by, "
                    "idempotency_digest, organization_id, environment_id, canonical_digest, "
                    "payload) SELECT claim_id, source_review_request_id, assignment_set_id, "
                    "claimed_by, idempotency_digest, :second_organization_id, environment_id, "
                    "canonical_digest, payload FROM "
                    "operational_knowledge_reviewer_assignment_claims "
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
                    "INSERT INTO operational_knowledge_reviewer_assignments "
                    "(assignment_set_id, claim_id, source_review_request_id, knowledge_item_id, "
                    "requested_by, organization_id, environment_id, canonical_digest, payload) "
                    "SELECT assignment_set_id, claim_id, source_review_request_id, "
                    "knowledge_item_id, requested_by, :second_organization_id, environment_id, "
                    "canonical_digest, payload FROM operational_knowledge_reviewer_assignments "
                    "WHERE organization_id = :organization_id "
                    "AND assignment_set_id = :assignment_set_id"
                ),
                {
                    "second_organization_id": second_organization_id,
                    "organization_id": organization_id,
                    "assignment_set_id": assignment_set_id,
                },
            )

        with pytest.raises(RuntimeError, match="identifiers overlap between tenants"):
            command.downgrade(config, "20260825_0164")
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM operational_knowledge_reviewer_assignments "
                    "WHERE source_review_request_id = :source_review_request_id"
                ),
                {"source_review_request_id": source_review_request_id},
            )
            connection.execute(
                text(
                    "DELETE FROM operational_knowledge_reviewer_assignment_claims "
                    "WHERE source_review_request_id = :source_review_request_id"
                ),
                {"source_review_request_id": source_review_request_id},
            )
        command.upgrade(config, "head")
        engine.dispose()


@pytest.mark.asyncio
async def test_reviewer_assignment_options_fail_closed_without_trusted_adapter() -> None:
    (
        service,
        repository,
        review_request,
        policy,
        authorizer,
        _,
        _,
    ) = await reviewer_assignment_fixture(
        adapter=cast(Any, UnavailableOperationalKnowledgeReviewerAssignmentAdapter())
    )
    options = await service.list_options(
        actor=target_session_operator("subject.knowledge-review-coordinator"),
        source_review_request_id=review_request.review_request_id,
        correlation_id="cor_assignment_options_unavailable",
    )
    assert options == ()
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="adapter_unavailable"):
        await assign_reviewers(service, review_request, policy)
    assert authorizer.calls == []
    assert (
        await repository.get_claim_by_source_in_scope(
            source_review_request_id=review_request.review_request_id,
            organization_id=review_request.organization_id,
            environment_id=review_request.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_reviewer_assignment_accepts_development_identity_under_default_policy() -> None:
    service, _, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    actor = development_target_session_operator("subject.knowledge-review-coordinator")

    record = await assign_reviewers(service, review_request, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.requested_by == actor.subject_id


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_reviewer_assignment_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="assurance_required"):
        await assign_reviewers(
            service,
            review_request,
            policy,
            actor=development_target_session_operator("subject.knowledge-review-coordinator"),
        )

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_denies_non_human_identity() -> None:
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture()
    actor = replace(
        development_target_session_operator("subject.knowledge-review-coordinator"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="human_required"):
        await assign_reviewers(service, review_request, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_source_lookup_is_tenant_scoped() -> None:
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture()
    actor = replace(
        development_target_session_operator("subject.knowledge-review-coordinator"),
        organization_id="organization.foreign",
    )

    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="source_not_found"):
        await assign_reviewers(service, review_request, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_atomically_rejects_concurrent_second_claim() -> None:
    adapter = BlockingReviewerAssignmentAdapter()
    service, _, review_request, policy, _, _, _ = await reviewer_assignment_fixture(adapter=adapter)
    first = asyncio.create_task(
        assign_reviewers(service, review_request, policy, key="assign-first")
    )
    await adapter.started.wait()
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="idempotency_conflict"):
        await assign_reviewers(service, review_request, policy, key="assign-second")
    adapter.release.set()
    record = await first
    assert record.reviewer_assigned and adapter.call_count == 1


@pytest.mark.asyncio
async def test_reviewer_assignment_permission_denial_happens_before_claim() -> None:
    service, repository, review_request, policy, _, adapter, _ = await reviewer_assignment_fixture(
        permission_authorizer=RecordingReviewerAssignmentPermissionAuthorizer(deny=True)
    )
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="permission_denied"):
        await assign_reviewers(service, review_request, policy)
    assert (
        await repository.get_claim_by_source_in_scope(
            source_review_request_id=review_request.review_request_id,
            organization_id=review_request.organization_id,
            environment_id=review_request.environment_id,
        )
        is None
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_revalidates_policy_immediately_before_claim() -> None:
    service, repository, review_request, policy, _, adapter, _ = await reviewer_assignment_fixture()
    service._policy_source = VanishingReviewerAssignmentPolicySource((policy,))

    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="option_invalid"):
        await assign_reviewers(service, review_request, policy)

    assert (
        await repository.get_claim_by_source_in_scope(
            source_review_request_id=review_request.review_request_id,
            organization_id=review_request.organization_id,
            environment_id=review_request.environment_id,
        )
        is None
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainReviewerAssignmentAdapter()
    service, repository, review_request, policy, _, _, _ = await reviewer_assignment_fixture(
        adapter=uncertain
    )
    with pytest.raises(OperationalKnowledgeReviewerAssignmentUncertainError, match="uncertain"):
        await assign_reviewers(service, review_request, policy)
    assert uncertain.calls == 1
    inventory = await service.list_inventory(
        actor=target_session_operator("subject.knowledge-review-coordinator"),
        source_review_request_id=review_request.review_request_id,
        correlation_id="cor_assignment_uncertain_inventory",
    )
    assert len(inventory) == 1
    assert getattr(inventory[0], "claim_state", None) == "claim_consumed_unresolved"
    assert getattr(inventory[0], "automatic_retry_allowed", None) is False
    assert await repository.get_claim_by_source_in_scope(
        source_review_request_id=review_request.review_request_id,
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
    )
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="already_claimed"):
        await assign_reviewers(service, review_request, policy)

    altered = AlteredReviewerAssignmentReceiptAdapter(clock=lambda: review_request.created_at)
    (
        altered_service,
        _,
        altered_request,
        altered_policy,
        _,
        _,
        _,
    ) = await reviewer_assignment_fixture(adapter=altered)
    with pytest.raises(
        OperationalKnowledgeReviewerAssignmentUncertainError, match="receipt_invalid"
    ):
        await assign_reviewers(altered_service, altered_request, altered_policy)


@pytest.mark.asyncio
async def test_reviewer_assignment_claim_audit_failure_stays_claimed() -> None:
    service, repository, review_request, policy, _, adapter, _ = await reviewer_assignment_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await assign_reviewers(service, review_request, policy)
    assert await repository.get_claim_by_source_in_scope(
        source_review_request_id=review_request.review_request_id,
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_postgres_round_trip_excludes_identity_and_content() -> None:
    service, repository, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    record = await assign_reviewers(service, review_request, policy)
    claim = await repository.get_claim_by_source_in_scope(
        source_review_request_id=review_request.review_request_id,
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
    )
    assert claim is not None
    raw_claim = OperationalKnowledgeReviewerAssignmentService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeReviewerAssignmentService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeReviewerAssignmentRepository._claim_to_domain(raw_claim)
        == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeReviewerAssignmentRepository._record_to_domain(raw_record)
        == record
    )
    for hidden in (
        "draft_content",
        "evidence_content",
        "excerpt",
        "domain_reviewer_id",
        "security_reviewer_id",
        "reviewer_group",
        "directory_attributes",
        "idempotency_key",
    ):
        assert hidden not in raw_claim and hidden not in raw_record


def test_reviewer_assignment_api_forbids_identity_selection_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, review_request, _policy, _, _, review_parts = asyncio.run(
        reviewer_assignment_fixture()
    )
    review_service, _, _, _, _, _, draft_parts = review_parts
    draft_service = draft_parts[0]
    source = draft_parts[6]
    evidence_service = source[1]
    evidence_parts = source[2]
    bounded = evidence_parts[5]
    bounded_service, authorization_service, target_service, runtime_service, brokerage_service = (
        bounded[:5]
    )
    runtime_fixture = bounded[5]
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        credential_assignment_service,
        target_configuration_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = target_session_operator("subject.knowledge-review-coordinator")
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.operational-knowledge-reviewer-assignment-input.v1",
        "source_review_request_id": review_request.review_request_id,
        "purpose": (
            "Assign distinct eligible domain and security reviewers without exposing identity."
        ),
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
            credential_assignment_service=credential_assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=target_service,
            invocation_authorization_service=authorization_service,
            bounded_invocation_service=bounded_service,
            invocation_evidence_service=evidence_service,
            operational_evidence_knowledge_draft_service=draft_service,
            operational_knowledge_review_request_service=review_service,
            operational_knowledge_reviewer_assignment_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/knowledge/operational-reviewer-assignments"
        options = client.get(
            f"{endpoint}/options",
            params={"source_review_request_id": review_request.review_request_id},
        )
        empty_inventory = client.get(
            endpoint,
            params={"source_review_request_id": review_request.review_request_id},
        )
        assert options.status_code == 200, options.text
        assert len(options.json()["data"]) == 1
        assert empty_inventory.status_code == 200
        assert empty_inventory.json()["data"] == []
        payload["assignment_option_id"] = options.json()["data"][0]["assignment_option_id"]
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "assign-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "domain_reviewer_id": "subject.self-selected-reviewer"},
            headers={
                "Idempotency-Key": "assign-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "assign-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        assignment_set_id = created.json()["data"]["assignment_set_id"]
        read = client.get(f"{endpoint}/{assignment_set_id}")
        inventory = client.get(
            endpoint,
            params={"source_review_request_id": review_request.review_request_id},
        )
        consumed_options = client.get(
            f"{endpoint}/options",
            params={"source_review_request_id": review_request.review_request_id},
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert inventory.status_code == consumed_options.status_code == 200
    assert len(inventory.json()["data"]) == 1
    assert consumed_options.json()["data"] == []
    for response in (options, empty_inventory, created, read, inventory, consumed_options):
        assert response.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["knowledge_lifecycle"] == "reviewer_assigned"
    assert data["reviewer_assigned"] is True
    assert data["content_inspection_opened"] is False
    assert data["knowledge_approved"] is False
    assert data["retrieval_published"] is False
    for hidden in (
        "domain_reviewer_id",
        "security_reviewer_id",
        "reviewer_group",
        "directory_attributes",
        "domain_reviewer_subject_digest",
        "security_reviewer_subject_digest",
        "requested_by",
        "claim_id",
        "domain_queue_id",
        "security_queue_id",
        "assignment_adapter_id",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
    ):
        assert hidden not in data
