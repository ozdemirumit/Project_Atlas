from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_model_context_assembly import context_fixture, create_context
from test_package_acquisition import CollectingAuditSink

from atlas.api.protected_model_invocation_schemas import (
    ProtectedModelInvocationInput,
    ProtectedModelInvocationResultData,
)
from atlas.modules.ai.adapters.protected_model_invocation_memory import (
    InMemoryProtectedModelInvocationPolicySource,
    MemoryProtectedModelInvocationRepository,
)
from atlas.modules.ai.adapters.protected_model_invocation_postgres import (
    PostgreSQLProtectedModelInvocationRepository,
)
from atlas.modules.ai.adapters.protected_model_invocation_synthetic import (
    SyntheticTrustedProtectedModelGateway,
    UnavailableTrustedProtectedModelGateway,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
    build_development_protected_model_invocation_policy,
)
from atlas.modules.ai.application.protected_model_invocation_ports import (
    ProtectedModelInvocationError,
)
from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationPolicySnapshot,
    ProtectedModelInvocationResult,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.adapters.model_context_assembly_synthetic import (
    SyntheticTrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextResult


class RecordingInvocationPermissionAuthorizer:
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
            raise ProtectedModelInvocationError("protected_model_invocation_permission_denied")


async def invocation_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedProtectedModelInvocationService,
    MemoryProtectedModelInvocationRepository,
    ProtectedModelContextResult,
    ProtectedModelInvocationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedModelGateway | UnavailableTrustedProtectedModelGateway,
    RecordingInvocationPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        context_service,
        _,
        retrieval,
        context_policy,
        actor,
        assembler,
        _,
        audit,
    ) = await context_fixture()
    context = await create_context(context_service, retrieval, context_policy, actor)
    policy = build_development_protected_model_invocation_policy(
        organization_id=context.record.organization_id,
        environment_id=context.record.environment_id,
        issued_at=context.record.assembled_at - timedelta(hours=1),
        expires_at=context.record.assembled_at + timedelta(days=1),
    )
    gateway = (
        UnavailableTrustedProtectedModelGateway()
        if unavailable
        else SyntheticTrustedProtectedModelGateway(clock=lambda: context.record.assembled_at)
    )
    permission = RecordingInvocationPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedModelInvocationRepository()
    assert isinstance(assembler, SyntheticTrustedProtectedModelContextAssembler)
    service = GovernedProtectedModelInvocationService(
        repository=repository,
        context_source=context_service,
        context_vault=assembler,
        policy_source=InMemoryProtectedModelInvocationPolicySource((policy,)),
        permission_authorizer=permission,
        gateway=gateway,
        audit_sink=audit,
        environment_id=context.record.environment_id,
        clock=lambda: context.record.assembled_at,
    )
    return service, repository, context, policy, actor, gateway, permission, audit


async def create_invocation(
    service: GovernedProtectedModelInvocationService,
    context: ProtectedModelContextResult,
    policy: ProtectedModelInvocationPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "protected-model-invocation-001",
) -> ProtectedModelInvocationResult:
    return await service.create(
        actor=actor,
        context_id=context.record.context_id,
        context_digest=context.record.canonical_digest,
        invocation_policy_id=policy.policy_id,
        invocation_policy_digest=policy.canonical_digest,
        purpose=context.record.purpose,
        draft_untrusted_acknowledged=True,
        citations_and_unknowns_acknowledged=True,
        no_answer_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_protected_model_invocation",
    )


@pytest.mark.asyncio
async def test_invocation_is_private_bounded_and_idempotent() -> None:
    service, _, context, policy, actor, gateway, permission, _ = await invocation_fixture()
    result = await create_invocation(service, context, policy, actor)
    repeated = await create_invocation(service, context, policy, actor)
    replay = await service.get(
        actor=actor,
        invocation_id=result.record.invocation_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_model_invocation_read",
    )
    adjudication_source, protected_draft = await service.rehydrate_for_adjudication(
        actor=actor,
        invocation_id=result.record.invocation_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_model_invocation_adjudication",
    )
    assert result.record.model_invoked and result.record.protected_draft_available
    assert not result.record.answer_generated and not result.record.execution_authorized
    assert result.manifest.citation_count == 1 and result.manifest.unknown_count == 2
    assert repeated.record.reused and replay.record.reused
    assert adjudication_source.record.reused
    assert protected_draft.canonical_digest == result.record.draft_digest
    assert isinstance(gateway, SyntheticTrustedProtectedModelGateway)
    assert len(gateway.calls) == 1
    assert len(permission.calls) == 4
    raw = asdict(result.record)
    for forbidden in ("summary", "unknowns", "objective", "evidence", "endpoint_url", "secret"):
        assert forbidden not in raw
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    restored = PostgreSQLProtectedModelInvocationRepository._record_to_domain(persisted)
    assert restored == result.record
    response = ProtectedModelInvocationResultData.from_domain(result).model_dump()
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "invocation_authorization_digest",
        "protected_draft_reference",
        "protected_draft_digest",
    ):
        assert private not in response["invocation"]


@pytest.mark.asyncio
async def test_invocation_denial_precedes_claim() -> None:
    service, repository, context, policy, actor, gateway, *_ = await invocation_fixture(deny=True)
    with pytest.raises(ProtectedModelInvocationError, match="permission_denied"):
        await create_invocation(service, context, policy, actor)
    assert not repository._claims
    assert isinstance(gateway, SyntheticTrustedProtectedModelGateway)
    assert not gateway.calls


@pytest.mark.asyncio
async def test_invocation_production_boundary_fails_closed_without_retry() -> None:
    service, repository, context, policy, actor, gateway, *_ = await invocation_fixture(
        unavailable=True
    )
    with pytest.raises(ProtectedModelInvocationError, match="gateway_unavailable"):
        await create_invocation(service, context, policy, actor)
    assert repository._claims and not repository._records
    assert isinstance(gateway, UnavailableTrustedProtectedModelGateway)


def test_invocation_input_is_strict() -> None:
    with pytest.raises(ValidationError):
        ProtectedModelInvocationInput.model_validate(
            {
                "context_digest": "a" * 64,
                "invocation_policy_id": "protected-model-invocation-policy.development",
                "invocation_policy_digest": "b" * 64,
                "purpose": "Analyze approved evidence for a read-only investigation.",
                "acknowledged_draft_is_untrusted": True,
                "acknowledged_citations_and_unknowns_require_validation": True,
                "acknowledged_no_answer_or_operational_authority": True,
                "model_id": "caller-selected-model",
            }
        )
