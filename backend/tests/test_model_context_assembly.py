from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_protected_retrieval import create_retrieval, retrieval_fixture
from test_target_session import development_target_session_operator

from atlas.api.model_context_assembly_schemas import (
    ProtectedModelContextInput,
    ProtectedModelContextResultData,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.model_context_assembly_memory import (
    InMemoryProtectedModelContextPolicySource,
    MemoryProtectedModelContextRepository,
)
from atlas.modules.knowledge.adapters.model_context_assembly_postgres import (
    PostgreSQLProtectedModelContextRepository,
)
from atlas.modules.knowledge.adapters.model_context_assembly_synthetic import (
    SyntheticTrustedProtectedModelContextAssembler,
    UnavailableTrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.application.model_context_assembly import (
    GovernedProtectedModelContextService,
    build_development_protected_model_context_policy,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    ProtectedModelContextError,
)
from atlas.modules.knowledge.domain.model_context_assembly import (
    ProtectedModelContextPolicySnapshot,
    ProtectedModelContextResult,
)
from atlas.modules.knowledge.domain.protected_retrieval import OperationalKnowledgeRetrievalResult


class RecordingContextPermissionAuthorizer:
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
            raise ProtectedModelContextError("protected_model_context_permission_denied")


class StaticRetrievalSource:
    def __init__(self, result: OperationalKnowledgeRetrievalResult) -> None:
        self.result = result

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        retrieval_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult:
        del actor, browser_session_id, correlation_id
        if retrieval_id != self.result.record.retrieval_id:
            raise ProtectedModelContextError("protected_model_context_source_not_found")
        return self.result


async def context_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedProtectedModelContextService,
    MemoryProtectedModelContextRepository,
    OperationalKnowledgeRetrievalResult,
    ProtectedModelContextPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedModelContextAssembler
    | UnavailableTrustedProtectedModelContextAssembler,
    RecordingContextPermissionAuthorizer,
    CollectingAuditSink,
]:
    retrieval_service, _, publication, retrieval_policy, actor, *_ = await retrieval_fixture()
    retrieval = await create_retrieval(retrieval_service, publication, retrieval_policy, actor)
    policy = build_development_protected_model_context_policy(
        organization_id=retrieval.record.organization_id,
        environment_id=retrieval.record.environment_id,
        issued_at=retrieval.record.retrieved_at - timedelta(hours=1),
        expires_at=retrieval.record.retrieved_at + timedelta(days=1),
    )
    assembler: (
        SyntheticTrustedProtectedModelContextAssembler
        | UnavailableTrustedProtectedModelContextAssembler
    )
    if unavailable:
        assembler = UnavailableTrustedProtectedModelContextAssembler()
    else:
        assembler = SyntheticTrustedProtectedModelContextAssembler(
            clock=lambda: retrieval.record.retrieved_at
        )
    permission = RecordingContextPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedModelContextRepository()
    audit = CollectingAuditSink()
    service = GovernedProtectedModelContextService(
        repository=repository,
        retrieval_source=retrieval_service,
        policy_source=InMemoryProtectedModelContextPolicySource((policy,)),
        permission_authorizer=permission,
        assembler=assembler,
        audit_sink=audit,
        environment_id=retrieval.record.environment_id,
        clock=lambda: retrieval.record.retrieved_at,
    )
    return service, repository, retrieval, policy, actor, assembler, permission, audit


async def create_context(
    service: GovernedProtectedModelContextService,
    retrieval: OperationalKnowledgeRetrievalResult,
    policy: ProtectedModelContextPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "protected-model-context-001",
    objective: str = "Analyze the retrieved controller warning evidence with citations.",
) -> ProtectedModelContextResult:
    return await service.create(
        actor=actor,
        retrieval_id=retrieval.record.retrieval_id,
        retrieval_digest=retrieval.record.canonical_digest,
        context_policy_id=policy.policy_id,
        context_policy_digest=policy.canonical_digest,
        objective=objective,
        purpose=retrieval.record.purpose,
        untrusted_intent_acknowledged=True,
        citation_boundaries_acknowledged=True,
        no_model_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_protected_model_context",
    )


def _signed_context_policy(
    service: GovernedProtectedModelContextService,
    policy: ProtectedModelContextPolicySnapshot,
    required_assurance_level: AssuranceLevel,
) -> ProtectedModelContextPolicySnapshot:
    updated = replace(
        policy,
        required_assurance_level=required_assurance_level,
        canonical_digest="0" * 64,
    )
    return replace(
        updated,
        canonical_digest=service._digest(service._payload(updated)),
    )


def test_context_policy_supports_governed_assurance_levels() -> None:
    policy = build_development_protected_model_context_policy(
        organization_id="org.atlas",
        environment_id="environment.development",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    for level in (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ):
        assert replace(policy, required_assurance_level=level).required_assurance_level is level


@pytest.mark.asyncio
async def test_context_requires_step_up_only_when_signed_policy_requests_it() -> None:
    (
        service,
        repository,
        retrieval,
        policy,
        actor,
        assembler,
        permission,
        audit,
    ) = await context_fixture()
    stronger = _signed_context_policy(service, policy, AssuranceLevel.MULTI_FACTOR)
    service = GovernedProtectedModelContextService(
        repository=repository,
        retrieval_source=service._retrieval_source,
        policy_source=InMemoryProtectedModelContextPolicySource((stronger,)),
        permission_authorizer=permission,
        assembler=assembler,
        audit_sink=audit,
        environment_id=retrieval.record.environment_id,
        clock=lambda: retrieval.record.retrieved_at,
    )
    actor = development_target_session_operator(actor.subject_id)
    with pytest.raises(ProtectedModelContextError, match="policy_assurance_required"):
        await create_context(service, retrieval, stronger, actor)


@pytest.mark.asyncio
async def test_context_rejects_non_human_actor() -> None:
    service, _, retrieval, policy, actor, *_ = await context_fixture()
    with pytest.raises(ProtectedModelContextError, match="human_required"):
        await create_context(service, retrieval, policy, replace(actor, kind=SubjectKind.SERVICE))


@pytest.mark.asyncio
async def test_model_context_is_bounded_private_and_idempotent() -> None:
    service, _, retrieval, policy, actor, assembler, permission, audit = await context_fixture()
    result = await create_context(service, retrieval, policy, actor)
    repeated = await create_context(service, retrieval, policy, actor)
    replay = await service.get(
        actor=actor,
        context_id=result.record.context_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_model_context_read",
    )
    assert result.record.model_context_available
    assert not result.record.model_invoked
    assert not result.record.execution_authorized
    assert result.manifest.included_evidence_count == 1
    assert result.manifest.estimated_token_count <= result.manifest.maximum_estimated_tokens
    assert repeated.record.reused and replay.record.reused
    assert isinstance(assembler, SyntheticTrustedProtectedModelContextAssembler)
    assert len(assembler.calls) == 1
    assert len(permission.calls) == 3
    assert [item.result_code for item in audit.records] == [
        "protected_model_context_requested",
        "protected_model_context_claimed",
        "protected_model_context_assembled",
        "protected_model_context_read",
        "protected_model_context_read",
    ]
    persisted = GovernedProtectedModelContextService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    restored = PostgreSQLProtectedModelContextRepository._record_to_domain(persisted)
    assert restored == result.record
    raw = asdict(result.record)
    for forbidden in (
        "objective",
        "query",
        "excerpt",
        "source_title",
        "citation_location",
        "platform_safety_layer",
        "prompt",
    ):
        assert forbidden not in raw
    response = ProtectedModelContextResultData.from_domain(result).model_dump()
    for private in (
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "authorization_context_digest",
        "protected_artifact_reference",
        "protected_artifact_digest",
        "claim_id",
    ):
        assert private not in response["context"]


@pytest.mark.asyncio
async def test_model_context_permission_denial_precedes_claim() -> None:
    service, repository, retrieval, policy, actor, assembler, *_ = await context_fixture(deny=True)
    with pytest.raises(ProtectedModelContextError, match="permission_denied"):
        await create_context(service, retrieval, policy, actor)
    assert not repository._claims
    assert isinstance(assembler, SyntheticTrustedProtectedModelContextAssembler)
    assert not assembler.calls


@pytest.mark.asyncio
async def test_model_context_conflicting_idempotency_never_reassembles() -> None:
    service, _, retrieval, policy, actor, assembler, *_ = await context_fixture()
    await create_context(service, retrieval, policy, actor)
    with pytest.raises(ProtectedModelContextError, match="idempotency_conflict"):
        await create_context(
            service,
            retrieval,
            policy,
            actor,
            objective="Analyze a different objective from the same evidence package.",
        )
    assert isinstance(assembler, SyntheticTrustedProtectedModelContextAssembler)
    assert len(assembler.calls) == 1


@pytest.mark.asyncio
async def test_model_context_production_boundary_fails_closed() -> None:
    service, repository, retrieval, policy, actor, *_ = await context_fixture(unavailable=True)
    with pytest.raises(ProtectedModelContextError, match="assembler_unavailable"):
        await create_context(service, retrieval, policy, actor)
    assert repository._claims
    assert not repository._records


@pytest.mark.asyncio
async def test_model_context_rejects_retrieval_drift() -> None:
    service, repository, retrieval, policy, actor, *_ = await context_fixture()
    service._retrieval_source = StaticRetrievalSource(
        OperationalKnowledgeRetrievalResult(
            record=replace(retrieval.record, evidence_package_digest="f" * 64),
            evidence=retrieval.evidence,
        )
    )
    with pytest.raises(ProtectedModelContextError, match="source_invalid"):
        await create_context(service, retrieval, policy, actor)
    assert not repository._claims


@pytest.mark.asyncio
async def test_model_context_safety_and_budget_are_deterministic() -> None:
    service, _, retrieval, policy, actor, assembler, *_ = await context_fixture()
    await create_context(service, retrieval, policy, actor)
    assert isinstance(assembler, SyntheticTrustedProtectedModelContextAssembler)
    instruction = assembler.calls[0]
    unsafe_item = replace(retrieval.evidence.results[0], safety_state="safety.unreviewed")
    unsafe_package = replace(
        retrieval.evidence,
        results=(unsafe_item,),
        canonical_digest="0" * 64,
    )
    payload = asdict(unsafe_package)
    payload.pop("canonical_digest")
    unsafe_package = replace(
        unsafe_package,
        canonical_digest=GovernedProtectedModelContextService._digest(payload),
    )
    with pytest.raises(ProtectedModelContextError, match="safety_validation_failed"):
        await assembler.assemble(
            replace(
                instruction,
                context_id="protected-model-context.unsafe",
                evidence_package_digest=unsafe_package.canonical_digest,
            ),
            unsafe_package,
        )

    receipt, package = await assembler.assemble(
        replace(
            instruction,
            context_id="protected-model-context.budget-limited",
            maximum_context_characters=1_000,
            maximum_estimated_tokens=256,
        ),
        retrieval.evidence,
    )
    assert receipt.outcome == "context-outcome.insufficient-evidence"
    assert receipt.included_evidence_count == 0
    assert not package.evidence_units
    assert package.character_count <= 1_000
    assert package.estimated_token_count <= 256


def test_model_context_input_is_strict() -> None:
    with pytest.raises(ValidationError):
        ProtectedModelContextInput.model_validate(
            {
                "retrieval_digest": "a" * 64,
                "context_policy_id": "protected-model-context-policy.development",
                "context_policy_digest": "b" * 64,
                "objective": "Analyze the authorized evidence.",
                "purpose": "Analyze approved evidence for a read-only investigation.",
                "acknowledged_untrusted_intent": True,
                "acknowledged_citation_boundaries": True,
                "acknowledged_no_model_or_operational_authority": True,
                "model_id": "caller-selected-model",
            }
        )
