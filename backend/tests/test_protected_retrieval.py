from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_retrieval_index_publication import create_publication, publication_fixture
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.protected_retrieval_schemas import (
    OperationalKnowledgeRetrievalInput,
    OperationalKnowledgeRetrievalResultData,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.protected_retrieval_memory import (
    InMemoryOperationalKnowledgeRetrievalPolicySource,
    MemoryOperationalKnowledgeRetrievalRepository,
)
from atlas.modules.knowledge.adapters.protected_retrieval_postgres import (
    PostgreSQLOperationalKnowledgeRetrievalRepository,
)
from atlas.modules.knowledge.adapters.protected_retrieval_synthetic import (
    SyntheticOperationalKnowledgeTrustedRetriever,
    UnavailableOperationalKnowledgeTrustedRetriever,
)
from atlas.modules.knowledge.application.protected_retrieval import (
    OperationalKnowledgeProtectedRetrievalService,
    build_development_operational_knowledge_retrieval_policy,
)
from atlas.modules.knowledge.application.protected_retrieval_ports import (
    OperationalKnowledgeRetrievalError,
)
from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeRetrievalPolicySnapshot,
    OperationalKnowledgeRetrievalResult,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationRecord,
)


class RecordingRetrievalPermissionAuthorizer:
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
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_permission_denied"
            )


class StaticPublicationSource:
    def __init__(self, publication: OperationalKnowledgeRetrievalPublicationRecord) -> None:
        self.publication = publication

    async def source_for_governed_retrieval(
        self, *, publication_id: str
    ) -> OperationalKnowledgeRetrievalPublicationRecord | None:
        return self.publication if publication_id == self.publication.publication_id else None


async def retrieval_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
) -> tuple[
    OperationalKnowledgeProtectedRetrievalService,
    MemoryOperationalKnowledgeRetrievalRepository,
    OperationalKnowledgeRetrievalPublicationRecord,
    OperationalKnowledgeRetrievalPolicySnapshot,
    AuthenticatedSubject,
    SyntheticOperationalKnowledgeTrustedRetriever | UnavailableOperationalKnowledgeTrustedRetriever,
    RecordingRetrievalPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        publication_service,
        _,
        index,
        publication_policy,
        publication_actor,
        *_,
    ) = await publication_fixture()
    publication = await create_publication(
        publication_service, index, publication_policy, publication_actor
    )
    policy = build_development_operational_knowledge_retrieval_policy(
        organization_id=publication.organization_id,
        environment_id=publication.environment_id,
        issued_at=publication.published_at - timedelta(hours=1),
        expires_at=publication.published_at + timedelta(days=1),
        subject_digest_salt_digest=publication_policy.subject_digest_salt_digest,
    )
    retriever: (
        SyntheticOperationalKnowledgeTrustedRetriever
        | UnavailableOperationalKnowledgeTrustedRetriever
    )
    if unavailable:
        retriever = UnavailableOperationalKnowledgeTrustedRetriever()
    else:
        retriever = SyntheticOperationalKnowledgeTrustedRetriever(
            clock=lambda: publication.published_at
        )
    permission = RecordingRetrievalPermissionAuthorizer(deny=deny)
    repository = MemoryOperationalKnowledgeRetrievalRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeProtectedRetrievalService(
        repository=repository,
        publication_source=StaticPublicationSource(publication),
        policy_source=InMemoryOperationalKnowledgeRetrievalPolicySource((policy,)),
        permission_authorizer=permission,
        retriever=retriever,
        audit_sink=audit,
        environment_id=publication.environment_id,
        clock=lambda: publication.published_at,
    )
    actor = target_session_operator("subject.knowledge-retrieval-consumer")
    return service, repository, publication, policy, actor, retriever, permission, audit


async def create_retrieval(
    service: OperationalKnowledgeProtectedRetrievalService,
    publication: OperationalKnowledgeRetrievalPublicationRecord,
    policy: OperationalKnowledgeRetrievalPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "protected-knowledge-retrieval-001",
    query: str = "What evidence explains the current storage controller warning?",
) -> OperationalKnowledgeRetrievalResult:
    return await service.create(
        actor=actor,
        publication_id=publication.publication_id,
        publication_digest=publication.canonical_digest,
        retrieval_policy_id=policy.policy_id,
        retrieval_policy_digest=policy.canonical_digest,
        query=query,
        purpose="Retrieve approved evidence for a read-only controller warning investigation.",
        untrusted_evidence_acknowledged=True,
        unsafe_instructions_acknowledged=True,
        no_model_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_protected_knowledge_retrieval",
    )


@pytest.mark.asyncio
async def test_protected_retrieval_rejects_non_human_actor() -> None:
    service, _, publication, policy, actor, *_ = await retrieval_fixture()
    with pytest.raises(OperationalKnowledgeRetrievalError, match="human_required"):
        await create_retrieval(
            service,
            publication,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


@pytest.mark.asyncio
async def test_protected_retrieval_accepts_development_identity_under_default_policy() -> None:
    service, _, publication, policy, _, *_ = await retrieval_fixture()
    actor = development_target_session_operator("subject.knowledge-retrieval-consumer")

    result = await create_retrieval(service, publication, policy, actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert result.record.consumer_subject_digest != actor.subject_id


@pytest.mark.asyncio
async def test_protected_retrieval_rejects_insufficient_explicit_assurance_policy() -> None:
    service, _, publication, policy, _, *_ = await retrieval_fixture()
    actor = development_target_session_operator("subject.knowledge-retrieval-consumer")
    stronger_policy = replace(
        policy,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        canonical_digest="0" * 64,
    )
    stronger_policy = replace(
        stronger_policy,
        canonical_digest=service._digest(service._payload(stronger_policy)),
    )
    service._policy_source = InMemoryOperationalKnowledgeRetrievalPolicySource((stronger_policy,))
    with pytest.raises(OperationalKnowledgeRetrievalError, match="assurance_required"):
        await create_retrieval(service, publication, stronger_policy, actor)


@pytest.mark.parametrize(
    "assurance_level",
    (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ),
)
def test_protected_retrieval_policy_accepts_supported_assurance_levels(
    assurance_level: AssuranceLevel,
) -> None:
    issued_at = datetime.now(UTC)
    policy = OperationalKnowledgeRetrievalPolicySnapshot(
        policy_id="operational-knowledge-retrieval-policy.test",
        schema_version="atlas.operational-knowledge-retrieval-policy.v1",
        version=1,
        organization_id="org.test",
        environment_id="env.test",
        policy_version="policy-version.test-v1",
        required_publication_schema="atlas.operational-knowledge-retrieval-publication.v1",
        required_publication_state="operational_knowledge_retrieval_published",
        required_retriever_id="operational-knowledge-retriever.test",
        required_retriever_attestor_id="subject.retriever-attestor",
        required_receipt_schema="atlas.operational-knowledge-retrieval-receipt.v1",
        protected_vault_id="protected-vault.test",
        retrieval_profile_digest="a" * 64,
        authorization_profile_digest="b" * 64,
        ranking_profile_digest="c" * 64,
        evidence_profile_digest="d" * 64,
        subject_digest_salt_digest="e" * 64,
        browser_binding_key_digest="f" * 64,
        maximum_authentication_age_minutes=15,
        maximum_query_characters=1_000,
        maximum_results=5,
        maximum_excerpt_characters=1_000,
        retention_minutes=30,
        required_assurance_level=assurance_level,
        signed_by="subject.policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=1),
        canonical_digest="0" * 64,
    )
    assert policy.required_assurance_level is assurance_level


@pytest.mark.asyncio
async def test_protected_retrieval_is_authorized_bounded_and_idempotent() -> None:
    (
        service,
        _repository,
        publication,
        policy,
        actor,
        retriever,
        permission,
        audit,
    ) = await retrieval_fixture()
    result = await create_retrieval(service, publication, policy, actor)
    repeated = await create_retrieval(service, publication, policy, actor)
    replay = await service.get(
        actor=actor,
        retrieval_id=result.record.retrieval_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_knowledge_retrieval_read",
    )
    assert result.record.knowledge_retrieved
    assert not result.record.model_context_available
    assert not result.record.execution_authorized
    assert len(result.evidence.results) == 1
    assert repeated.record.reused and replay.record.reused
    assert isinstance(retriever, SyntheticOperationalKnowledgeTrustedRetriever)
    assert len(retriever.calls) == 1
    assert len(permission.calls) == 3
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_retrieval_requested",
        "operational_knowledge_retrieval_claimed",
        "operational_knowledge_retrieved",
        "operational_knowledge_retrieval_read",
        "operational_knowledge_retrieval_read",
    ]
    persisted = OperationalKnowledgeProtectedRetrievalService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    restored = PostgreSQLOperationalKnowledgeRetrievalRepository._record_to_domain(persisted)
    assert restored == result.record
    raw = asdict(result.record)
    for forbidden in ("query", "excerpt", "source_title", "citation_location", "vector"):
        assert forbidden not in raw
    response = OperationalKnowledgeRetrievalResultData.from_domain(result).model_dump()
    for private in (
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "protected_artifact_reference",
        "protected_artifact_digest",
        "claim_id",
    ):
        assert private not in response["retrieval"]


@pytest.mark.asyncio
async def test_protected_retrieval_rejects_supply_chain_actor_before_claim() -> None:
    service, repository, publication, policy, *_ = await retrieval_fixture()
    actor = target_session_operator("subject.knowledge-retrieval-publication-steward")
    with pytest.raises(OperationalKnowledgeRetrievalError, match="separation_required"):
        await create_retrieval(service, publication, policy, actor)
    assert not repository._claims


@pytest.mark.asyncio
async def test_protected_retrieval_permission_denial_precedes_claim() -> None:
    service, repository, publication, policy, actor, retriever, *_ = await retrieval_fixture(
        deny=True
    )
    with pytest.raises(OperationalKnowledgeRetrievalError, match="permission_denied"):
        await create_retrieval(service, publication, policy, actor)
    assert not repository._claims
    assert isinstance(retriever, SyntheticOperationalKnowledgeTrustedRetriever)
    assert not retriever.calls


@pytest.mark.asyncio
async def test_protected_retrieval_conflicting_idempotency_never_reruns() -> None:
    service, _, publication, policy, actor, retriever, *_ = await retrieval_fixture()
    await create_retrieval(service, publication, policy, actor)
    with pytest.raises(OperationalKnowledgeRetrievalError, match="idempotency_conflict"):
        await create_retrieval(
            service,
            publication,
            policy,
            actor,
            query="Show a different body of operational evidence.",
        )
    assert isinstance(retriever, SyntheticOperationalKnowledgeTrustedRetriever)
    assert len(retriever.calls) == 1


@pytest.mark.asyncio
async def test_protected_retrieval_production_boundary_fails_closed() -> None:
    service, repository, publication, policy, actor, *_ = await retrieval_fixture(unavailable=True)
    with pytest.raises(OperationalKnowledgeRetrievalError, match="retriever_unavailable"):
        await create_retrieval(service, publication, policy, actor)
    assert repository._claims
    assert not repository._records


@pytest.mark.asyncio
async def test_protected_retrieval_rejects_publication_drift() -> None:
    service, repository, publication, policy, actor, *_ = await retrieval_fixture()
    service._publication_source = StaticPublicationSource(
        replace(publication, route_generation_digest="f" * 64)
    )
    with pytest.raises(OperationalKnowledgeRetrievalError, match="source_invalid"):
        await create_retrieval(service, publication, policy, actor)
    assert not repository._claims


def test_protected_retrieval_input_is_strict() -> None:
    with pytest.raises(ValidationError):
        OperationalKnowledgeRetrievalInput.model_validate(
            {
                "publication_digest": "a" * 64,
                "retrieval_policy_id": "operational-knowledge-retrieval-policy.development",
                "retrieval_policy_digest": "b" * 64,
                "query": "What evidence is available?",
                "purpose": "Retrieve approved evidence for an investigation.",
                "acknowledged_untrusted_evidence": True,
                "acknowledged_unsafe_instructions": True,
                "acknowledged_no_model_or_operational_authority": True,
                "filters": {"classification": "restricted"},
            }
        )
