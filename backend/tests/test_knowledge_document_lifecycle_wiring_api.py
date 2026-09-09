"""An audit of the operational-knowledge document lifecycle found nine route files -- the
governed chain from a curated document draft through operational-knowledge final resolution,
publication preparation, source materialization, deterministic chunking, embedding generation,
index staging validation, retrieval index publication, and protected retrieval -- that are all
registered on the real app with real permission decorators, but were reachable through no HTTP
call anywhere. Only the underlying service classes were unit-tested directly. These tests drive
both governed pipelines through the real HTTP API, not just the service layer, to prove the
wiring genuinely closes that gap.

``document_knowledge.py`` (drafts -> reviews -> approvals -> publication-preparations) is its own
self-contained pipeline behind ``DocumentKnowledgeService``; it does not feed the second pipeline.
The eight ``operational_knowledge_*`` routes form a single chain in which each stage's service is
constructed with the previous stage's service as its own upstream "source" (confirmed by reading
``atlas/api/app.py`` around the ``operational_knowledge_*_service`` wiring), and each stage's own
validation requires the acting human to differ from every accountable actor in every prior stage
(a real separation-of-duties control, not a test artifact). This test therefore drives each of the
eight stages through its own real HTTP session, authenticated as a distinct dev identity, and
carries the *real* service instance the app itself constructed for the previous stage into the
next stage's ``create_app`` call -- otherwise a freshly default-built service would start from an
empty repository and the chain would break. Every record consumed after the first stage is a real
record produced by a real prior HTTP call; nothing about the chain wiring itself is faked.

Reaching the first stage honestly is the one place this test borrows machinery from
``test_final_resolution.py``: a valid final resolution requires a review request that already
carries two passed, differently-tracked review decisions over a curated evidence draft, which in
turn sit behind a *separate*, much deeper governed pipeline (evidence ingestion, reviewer
assignment, protected content leasing, review findings, finding presentation -- one of which,
finding presentation, has no HTTP route of its own at all). That pipeline is out of scope for this
gap and already has its own fixture-level coverage, so this test reuses the exact
``final_resolution_fixture()`` helper those tests already trust to build a self-consistent
(decisions, review request, draft) bundle, rescopes it into the dev organization/environment so a
real dev HTTP identity can reach it, and constructs a real
``OperationalKnowledgeFinalResolutionService`` (real repository, real policy, real synthetic
attestor) around that bundle. That is the only service in the whole chain built by anything other
than the app's own default wiring.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
from datetime import UTC, datetime
from hashlib import sha256

from fastapi.testclient import TestClient
from test_final_resolution import (
    RecordingFinalResolutionPermissionAuthorizer,
    StaticFinalResolutionSource,
    final_resolution_fixture,
)
from test_package_acquisition import CollectingAuditSink

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.core.protected_content import InMemoryProtectedContentStore
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.adapters.document_chunking import ParagraphBoundedChunker
from atlas.modules.knowledge.adapters.document_embedding_fastembed import (
    FastEmbedDocumentEmbedder,
)
from atlas.modules.knowledge.adapters.document_knowledge_memory import (
    InMemoryDocumentKnowledgeRepository,
)
from atlas.modules.knowledge.adapters.document_vector_index_memory import (
    InMemoryDocumentVectorIndex,
)
from atlas.modules.knowledge.adapters.final_resolution_memory import (
    InMemoryOperationalKnowledgeFinalResolutionPolicySource,
    InMemoryOperationalKnowledgeFinalResolutionRepository,
)
from atlas.modules.knowledge.adapters.final_resolution_synthetic import (
    SyntheticOperationalKnowledgeFinalResolutionAttestor,
)
from atlas.modules.knowledge.application.deterministic_chunking import (
    OperationalKnowledgeDeterministicChunkingService,
    build_development_operational_knowledge_chunking_policy,
)
from atlas.modules.knowledge.application.document_knowledge import DocumentKnowledgeService
from atlas.modules.knowledge.application.document_retrieval import (
    DocumentKnowledgeRetrievalService,
)
from atlas.modules.knowledge.application.embedding_generation import (
    OperationalKnowledgeEmbeddingGenerationService,
    build_development_operational_knowledge_embedding_policy,
)
from atlas.modules.knowledge.application.final_resolution import (
    OperationalKnowledgeFinalResolutionService,
    build_development_operational_knowledge_final_resolution_policy,
)
from atlas.modules.knowledge.application.index_staging_validation import (
    OperationalKnowledgeIndexStagingValidationService,
    build_development_operational_knowledge_index_policy,
)
from atlas.modules.knowledge.application.protected_retrieval import (
    build_development_operational_knowledge_retrieval_policy,
)
from atlas.modules.knowledge.application.publication_preparation import (
    OperationalKnowledgePublicationPreparationService,
    build_development_operational_knowledge_publication_preparation_policy,
)
from atlas.modules.knowledge.application.retrieval_index_publication import (
    OperationalKnowledgeRetrievalIndexPublicationService,
    build_development_operational_knowledge_retrieval_publication_policy,
)
from atlas.modules.knowledge.application.source_materialization import (
    OperationalKnowledgeSourceMaterializationService,
    build_development_operational_knowledge_source_materialization_policy,
)
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionPolicySnapshot,
)

_ORGANIZATION_ID = Settings().development_organization_id
_ENVIRONMENT_ID = "environment.test"
_POLICY_ISSUED_AT = datetime(2026, 8, 1, tzinfo=UTC)
_POLICY_EXPIRES_AT = datetime(2030, 1, 1, tzinfo=UTC)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


async def _build_seeded_final_resolution_service() -> tuple[
    OperationalKnowledgeFinalResolutionService,
    StaticFinalResolutionSource,
    OperationalKnowledgeFinalResolutionPolicySnapshot,
]:
    """Build a real final-resolution service around a fixture-derived, self-consistent source.

    Reuses ``final_resolution_fixture()`` (the same helper ``test_final_resolution.py``'s own
    passing unit tests trust) purely to obtain a valid, mutually consistent
    (decisions, review request, draft) bundle -- then rescopes only the review request's
    organization/environment so the real dev HTTP identity used below can pass the service's own
    scope check. Nothing checked by ``OperationalKnowledgeFinalResolutionService.create`` beyond
    that scope match depends on the request's organization or environment, so this is a pure
    rescoping, not a change to any validated business rule.
    """
    _, _, source, _, _, _, _, _ = await final_resolution_fixture()
    scoped_request = dataclasses.replace(
        source.request, organization_id=_ORGANIZATION_ID, environment_id=_ENVIRONMENT_ID
    )
    scoped_source = StaticFinalResolutionSource(source.decisions, scoped_request, source.draft)
    policy = build_development_operational_knowledge_final_resolution_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
    )
    service = OperationalKnowledgeFinalResolutionService(
        repository=InMemoryOperationalKnowledgeFinalResolutionRepository(),
        source=scoped_source,
        policy_source=InMemoryOperationalKnowledgeFinalResolutionPolicySource((policy,)),
        permission_authorizer=RecordingFinalResolutionPermissionAuthorizer(),
        attestor=SyntheticOperationalKnowledgeFinalResolutionAttestor(),
        audit_sink=CollectingAuditSink(),
        environment_id=_ENVIRONMENT_ID,
    )
    return service, scoped_source, policy


def test_operational_knowledge_document_lifecycle_is_reachable_through_the_api() -> None:
    final_resolution_service, source, resolution_policy = asyncio.run(
        _build_seeded_final_resolution_service()
    )
    ordered = tuple(sorted(source.decisions, key=lambda item: item.track_code))
    publication_preparation_service: OperationalKnowledgePublicationPreparationService | None = None
    source_materialization_service: OperationalKnowledgeSourceMaterializationService | None = None
    deterministic_chunking_service: OperationalKnowledgeDeterministicChunkingService | None = None
    embedding_generation_service: OperationalKnowledgeEmbeddingGenerationService | None = None
    index_staging_validation_service: OperationalKnowledgeIndexStagingValidationService | None = (
        None
    )
    retrieval_index_publication_service: (
        OperationalKnowledgeRetrievalIndexPublicationService | None
    ) = None

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.ok-final-resolver"),
            operational_knowledge_final_resolution_service=final_resolution_service,
        )
    ) as client:
        csrf = _login(client)
        resolved = client.post(
            f"/api/v1/knowledge/review-requests/{source.request.review_request_id}/"
            "final-resolutions",
            json={
                "review_request_digest": source.request.canonical_digest,
                "decision_ids": [ordered[0].decision_id, ordered[1].decision_id],
                "decision_digests": [ordered[0].canonical_digest, ordered[1].canonical_digest],
                "disposition_code": "final-resolution.approved",
                "basis_codes": [
                    "final-basis.domain-and-security-passed",
                    "final-basis.governance-scope-accepted",
                ],
                "resolution_policy_id": resolution_policy.policy_id,
                "resolution_policy_digest": resolution_policy.canonical_digest,
                "purpose": "Record the accountable final resolution for the wiring test chain.",
                "acknowledged_immutable_review_generation": True,
                "acknowledged_publication_readiness_only": True,
                "acknowledged_no_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "know-life-final-resolution-0001"},
        )
        assert resolved.status_code == 201
        resolution = resolved.json()["data"]
        assert resolution["instance_state"] == "operational_knowledge_final_approved"
        assert resolution["disposition_code"] == "final-resolution.approved"
        assert resolution["knowledge_approved"] is True
        assert resolution["publication_ready"] is True

        refetched = client.get(
            f"/api/v1/knowledge/review-requests/{source.request.review_request_id}/"
            f"final-resolutions/{resolution['resolution_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert refetched.status_code == 200
        assert refetched.json()["data"]["resolution_id"] == resolution["resolution_id"]

    preparation_policy = build_development_operational_knowledge_publication_preparation_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
    )
    publication_preparation_app = create_app(
        _settings(development_subject_id="subject.ok-publication-preparer"),
        operational_knowledge_final_resolution_service=final_resolution_service,
    )
    with TestClient(publication_preparation_app) as client:
        csrf = _login(client)
        prepared = client.post(
            f"/api/v1/knowledge/final-resolutions/{resolution['resolution_id']}/"
            "publication-preparations",
            json={
                "final_resolution_digest": resolution["canonical_digest"],
                "preparation_policy_id": preparation_policy.policy_id,
                "preparation_policy_digest": preparation_policy.canonical_digest,
                "purpose": "Prepare the approved resolution for downstream publication staging.",
                "acknowledged_immutable_approved_generation": True,
                "acknowledged_metadata_only_preparation": True,
                "acknowledged_no_processing_or_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "know-life-publication-prep-0001"},
        )
        assert prepared.status_code == 201
        preparation = prepared.json()["data"]
        assert preparation["instance_state"] == "operational_knowledge_publication_prepared"
        assert preparation["resolution_id"] == resolution["resolution_id"]
        assert preparation["publication_prepared"] is True
        publication_preparation_service = (
            publication_preparation_app.state.operational_knowledge_publication_preparation_service
        )

    materialization_policy = build_development_operational_knowledge_source_materialization_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
    )
    source_materialization_app = create_app(
        _settings(development_subject_id="subject.ok-source-materializer"),
        operational_knowledge_final_resolution_service=final_resolution_service,
        operational_knowledge_publication_preparation_service=publication_preparation_service,
    )
    with TestClient(source_materialization_app) as client:
        csrf = _login(client)
        materialized = client.post(
            f"/api/v1/knowledge/publication-preparations/{preparation['preparation_id']}/"
            "source-materializations",
            json={
                "publication_preparation_digest": preparation["canonical_digest"],
                "materialization_policy_id": materialization_policy.policy_id,
                "materialization_policy_digest": materialization_policy.canonical_digest,
                "purpose": "Materialize the approved source content for deterministic chunking.",
                "acknowledged_immutable_approved_source": True,
                "acknowledged_protected_content_boundary": True,
                "acknowledged_no_chunking_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "know-life-source-materialize-0001",
            },
        )
        assert materialized.status_code == 201
        materialization = materialized.json()["data"]
        assert materialization["instance_state"] == "operational_knowledge_source_materialized"
        assert materialization["preparation_id"] == preparation["preparation_id"]
        assert materialization["source_materialized"] is True
        source_materialization_service = (
            source_materialization_app.state.operational_knowledge_source_materialization_service
        )

    chunking_policy = build_development_operational_knowledge_chunking_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
    )
    chunking_app = create_app(
        _settings(development_subject_id="subject.ok-chunker"),
        operational_knowledge_final_resolution_service=final_resolution_service,
        operational_knowledge_publication_preparation_service=publication_preparation_service,
        operational_knowledge_source_materialization_service=source_materialization_service,
    )
    with TestClient(chunking_app) as client:
        csrf = _login(client)
        chunked = client.post(
            f"/api/v1/knowledge/source-materializations/{materialization['materialization_id']}/"
            "chunk-sets",
            json={
                "source_materialization_digest": materialization["canonical_digest"],
                "chunking_policy_id": chunking_policy.policy_id,
                "chunking_policy_digest": chunking_policy.canonical_digest,
                "purpose": "Deterministically chunk the materialized source for embedding.",
                "acknowledged_protected_content_boundary": True,
                "acknowledged_immutable_chunking_profile": True,
                "acknowledged_no_embedding_or_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "know-life-chunking-0001"},
        )
        assert chunked.status_code == 201
        chunk_set = chunked.json()["data"]
        assert chunk_set["instance_state"] == "operational_knowledge_chunks_created"
        assert chunk_set["materialization_id"] == materialization["materialization_id"]
        assert chunk_set["chunk_count"] > 0
        deterministic_chunking_service = (
            chunking_app.state.operational_knowledge_deterministic_chunking_service
        )

    embedding_policy = build_development_operational_knowledge_embedding_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
    )
    embedding_app = create_app(
        _settings(development_subject_id="subject.ok-embedder"),
        operational_knowledge_final_resolution_service=final_resolution_service,
        operational_knowledge_publication_preparation_service=publication_preparation_service,
        operational_knowledge_source_materialization_service=source_materialization_service,
        operational_knowledge_deterministic_chunking_service=deterministic_chunking_service,
    )
    with TestClient(embedding_app) as client:
        csrf = _login(client)
        embedded = client.post(
            f"/api/v1/knowledge/chunk-sets/{chunk_set['chunk_set_id']}/embedding-sets",
            json={
                "chunk_set_digest": chunk_set["canonical_digest"],
                "embedding_policy_id": embedding_policy.policy_id,
                "embedding_policy_digest": embedding_policy.canonical_digest,
                "purpose": "Generate embeddings for the deterministically chunked content.",
                "acknowledged_protected_chunk_boundary": True,
                "acknowledged_immutable_model_profile": True,
                "acknowledged_no_index_or_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "know-life-embedding-0001"},
        )
        assert embedded.status_code == 201
        embedding_set = embedded.json()["data"]
        assert embedding_set["instance_state"] == "operational_knowledge_embeddings_created"
        assert embedding_set["chunk_set_id"] == chunk_set["chunk_set_id"]
        assert embedding_set["embedding_count"] > 0
        embedding_generation_service = (
            embedding_app.state.operational_knowledge_embedding_generation_service
        )

    index_policy = build_development_operational_knowledge_index_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
        embedding_policy=embedding_policy,
    )
    index_staging_app = create_app(
        _settings(development_subject_id="subject.ok-index-stager"),
        operational_knowledge_final_resolution_service=final_resolution_service,
        operational_knowledge_publication_preparation_service=publication_preparation_service,
        operational_knowledge_source_materialization_service=source_materialization_service,
        operational_knowledge_deterministic_chunking_service=deterministic_chunking_service,
        operational_knowledge_embedding_generation_service=embedding_generation_service,
    )
    with TestClient(index_staging_app) as client:
        csrf = _login(client)
        staged = client.post(
            f"/api/v1/knowledge/embedding-sets/{embedding_set['embedding_set_id']}/index-stages",
            json={
                "embedding_set_digest": embedding_set["canonical_digest"],
                "index_policy_id": index_policy.policy_id,
                "index_policy_digest": index_policy.canonical_digest,
                "purpose": "Stage and validate the embeddings into an inactive index projection.",
                "acknowledged_protected_vector_boundary": True,
                "acknowledged_inactive_projection": True,
                "acknowledged_no_publication_or_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "know-life-index-stage-0001"},
        )
        assert staged.status_code == 201
        index_staging = staged.json()["data"]
        assert index_staging["instance_state"] == "operational_knowledge_index_validated"
        assert index_staging["embedding_set_id"] == embedding_set["embedding_set_id"]
        assert index_staging["staged_point_count"] > 0
        index_staging_validation_service = (
            index_staging_app.state.operational_knowledge_index_staging_validation_service
        )

    retrieval_publication_policy = (
        build_development_operational_knowledge_retrieval_publication_policy(
            organization_id=_ORGANIZATION_ID,
            environment_id=_ENVIRONMENT_ID,
            issued_at=_POLICY_ISSUED_AT,
            expires_at=_POLICY_EXPIRES_AT,
            index_policy=index_policy,
        )
    )
    retrieval_pub_app = create_app(
        _settings(development_subject_id="subject.ok-retrieval-publisher"),
        operational_knowledge_final_resolution_service=final_resolution_service,
        operational_knowledge_publication_preparation_service=publication_preparation_service,
        operational_knowledge_source_materialization_service=source_materialization_service,
        operational_knowledge_deterministic_chunking_service=deterministic_chunking_service,
        operational_knowledge_embedding_generation_service=embedding_generation_service,
        operational_knowledge_index_staging_validation_service=index_staging_validation_service,
    )
    with TestClient(retrieval_pub_app) as client:
        csrf = _login(client)
        published = client.post(
            f"/api/v1/knowledge/index-stages/{index_staging['index_staging_id']}/publications",
            json={
                "index_staging_digest": index_staging["canonical_digest"],
                "publication_policy_id": retrieval_publication_policy.policy_id,
                "publication_policy_digest": retrieval_publication_policy.canonical_digest,
                "purpose": "Publish the validated index stage for policy-filtered retrieval.",
                "acknowledged_policy_filtered_visibility": True,
                "acknowledged_no_vector_store_disclosure": True,
                "acknowledged_no_context_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "know-life-retrieval-publish-0001",
            },
        )
        assert published.status_code == 201
        publication = published.json()["data"]
        assert publication["instance_state"] == "operational_knowledge_retrieval_published"
        assert publication["index_staging_id"] == index_staging["index_staging_id"]
        assert publication["retrieval_published"] is True
        retrieval_index_publication_service = (
            retrieval_pub_app.state.operational_knowledge_retrieval_index_publication_service
        )

    retrieval_policy = build_development_operational_knowledge_retrieval_policy(
        organization_id=_ORGANIZATION_ID,
        environment_id=_ENVIRONMENT_ID,
        issued_at=_POLICY_ISSUED_AT,
        expires_at=_POLICY_EXPIRES_AT,
        subject_digest_salt_digest=index_policy.subject_digest_salt_digest,
    )
    with TestClient(
        create_app(
            _settings(development_subject_id="subject.ok-retriever"),
            operational_knowledge_final_resolution_service=final_resolution_service,
            operational_knowledge_publication_preparation_service=publication_preparation_service,
            operational_knowledge_source_materialization_service=source_materialization_service,
            operational_knowledge_deterministic_chunking_service=deterministic_chunking_service,
            operational_knowledge_embedding_generation_service=embedding_generation_service,
            operational_knowledge_index_staging_validation_service=(
                index_staging_validation_service
            ),
            operational_knowledge_retrieval_index_publication_service=(
                retrieval_index_publication_service
            ),
        )
    ) as client:
        csrf = _login(client)
        retrieved = client.post(
            f"/api/v1/knowledge/retrieval-publications/{publication['publication_id']}/retrievals",
            json={
                "publication_digest": publication["canonical_digest"],
                "retrieval_policy_id": retrieval_policy.policy_id,
                "retrieval_policy_digest": retrieval_policy.canonical_digest,
                "query": "How is the failover controller restarted safely?",
                "purpose": "Retrieve published evidence to answer an operator support question.",
                "acknowledged_untrusted_evidence": True,
                "acknowledged_unsafe_instructions": True,
                "acknowledged_no_model_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "know-life-protected-retrieval-0001",
            },
        )
        assert retrieved.status_code == 201
        retrieval = retrieved.json()["data"]
        assert retrieval["retrieval"]["publication_id"] == publication["publication_id"]
        assert retrieval["retrieval"]["instance_state"] == "operational_knowledge_retrieved"
        assert retrieval["evidence"]["query"] == (
            "How is the failover controller restarted safely?"
        )
        assert retrieval["evidence"]["outcome"] in (
            "retrieval-outcome.evidence-available",
            "retrieval-outcome.insufficient-evidence",
        )

        refetched_retrieval = client.get(
            f"/api/v1/knowledge/retrieval-publications/{publication['publication_id']}/"
            f"retrievals/{retrieval['retrieval']['retrieval_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert refetched_retrieval.status_code == 200
        assert (
            refetched_retrieval.json()["data"]["retrieval"]["retrieval_id"]
            == retrieval["retrieval"]["retrieval_id"]
        )


class _AlwaysAllowDocumentKnowledgePermissionAuthorizer:
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None:
        del actor, organization_id, environment_id, permission_id, correlation_id


def _build_shared_document_knowledge_service() -> DocumentKnowledgeService:
    return DocumentKnowledgeService(
        repository=InMemoryDocumentKnowledgeRepository(),
        protected_content=InMemoryProtectedContentStore(),
        permission_authorizer=_AlwaysAllowDocumentKnowledgePermissionAuthorizer(),
        audit_sink=CollectingAuditSink(),
        subject_salt="document-knowledge-subject-salt.wiring-test",
    )


def test_document_knowledge_lifecycle_is_reachable_through_the_api() -> None:
    """Drives the document_knowledge draft/review/approval/publication-preparation chain across
    three distinct dev identities (a curator, an independent reviewer, and an independent final
    approver) so the service's own separation-of-duties checks are satisfied honestly, exactly as
    they would be for three real distinct operators. The three ``create_app`` calls share one
    ``DocumentKnowledgeService`` instance (and therefore one in-memory repository), so state
    created through one HTTP session is genuinely visible to the next.
    """
    service = _build_shared_document_knowledge_service()
    content_base64 = base64.b64encode(
        b"Runbook: restart the failover controller CTL01 safely."
    ).decode()

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-curator"),
            document_knowledge_service=service,
        )
    ) as curator_client:
        csrf = _login(curator_client)
        drafted = curator_client.post(
            "/api/v1/knowledge/documents/drafts",
            json={
                "content_base64": content_base64,
                "title": "Failover Controller Restart Runbook",
                "draft_domain": "domain.storage-operations",
                "content_type": "text/plain",
                "classification": "classification.internal",
                "access_policy_id": "access-policy.default",
                "retention_policy_id": "retention-policy.default",
                "purpose": "Curate a runbook draft for the document knowledge wiring test.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert drafted.status_code == 201
        draft = drafted.json()["data"]
        assert draft["instance_state"] == "document_knowledge_draft_created"
        assert draft["title"] == "Failover Controller Restart Runbook"

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-reviewer"),
            document_knowledge_service=service,
        )
    ) as reviewer_client:
        csrf = _login(reviewer_client)
        reviewed = reviewer_client.post(
            "/api/v1/knowledge/documents/reviews",
            json={
                "draft_id": draft["draft_id"],
                "decision": "passed",
                "findings": ["The restart sequence matches the vendor-approved procedure."],
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert reviewed.status_code == 201
        review = reviewed.json()["data"]
        assert review["instance_state"] == "document_knowledge_review_decided"
        assert review["decision"] == "passed"
        assert review["draft_id"] == draft["draft_id"]

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-approver"),
            document_knowledge_service=service,
        )
    ) as approver_client:
        csrf = _login(approver_client)
        approved = approver_client.post(
            "/api/v1/knowledge/documents/approvals",
            json={
                "review_id": review["review_id"],
                "decision": "approved",
                "rationale": "Independent final approval after a passed domain review.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert approved.status_code == 201
        approval = approved.json()["data"]
        assert approval["instance_state"] == "document_knowledge_final_approved"
        assert approval["decision"] == "approved"
        assert approval["review_id"] == review["review_id"]

        prepared = approver_client.post(
            "/api/v1/knowledge/documents/publication-preparations",
            json={
                "approval_id": approval["approval_id"],
                "chunking_profile_digest": sha256(
                    b"knowledge-chunking-profile.wiring-test"
                ).hexdigest(),
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert prepared.status_code == 201
        preparation = prepared.json()["data"]
        assert preparation["instance_state"] == "document_knowledge_publication_prepared"
        assert preparation["approval_id"] == approval["approval_id"]
        assert preparation["draft_id"] == draft["draft_id"]


def test_document_knowledge_indexing_and_search_is_reachable_through_the_api() -> None:
    """``document_knowledge.py`` also registers ``POST /knowledge/documents/index`` (gated by
    the real ``authorize_document_knowledge_indexing_create`` dependency) and
    ``POST /knowledge/documents/search`` (gated by the real
    ``authorize_document_knowledge_retrieval_create`` dependency), backed by the real
    ``DocumentKnowledgeRetrievalService`` -- chunking, embedding (real fastembed model, not a
    stub), and vector search over an already-approved document. Neither endpoint had any HTTP
    coverage anywhere in the suite. This test curates and approves a document through the same
    HTTP pipeline as ``test_document_knowledge_lifecycle_is_reachable_through_the_api`` above,
    then indexes and searches it through the real HTTP API, sharing one repository and one
    protected-content store between the ``DocumentKnowledgeService`` and the
    ``DocumentKnowledgeRetrievalService`` so the retrieval service can see the approved,
    prepared document that the knowledge service produced.
    """
    repository = InMemoryDocumentKnowledgeRepository()
    protected_content = InMemoryProtectedContentStore()
    knowledge_service = DocumentKnowledgeService(
        repository=repository,
        protected_content=protected_content,
        permission_authorizer=_AlwaysAllowDocumentKnowledgePermissionAuthorizer(),
        audit_sink=CollectingAuditSink(),
        subject_salt="document-knowledge-retrieval-subject-salt.wiring-test",
    )
    retrieval_service = DocumentKnowledgeRetrievalService(
        repository=repository,
        protected_content=protected_content,
        chunker=ParagraphBoundedChunker(maximum_chunk_characters=200),
        embedder=FastEmbedDocumentEmbedder(),
        vector_index=InMemoryDocumentVectorIndex(),
        permission_authorizer=_AlwaysAllowDocumentKnowledgePermissionAuthorizer(),
        audit_sink=CollectingAuditSink(),
    )
    content_base64 = base64.b64encode(
        b"# Storage Controller Runbook\n\n"
        b"When a storage controller reports a warning status, engineers should first confirm "
        b"the condition persists across two consecutive read-only health checks before taking "
        b"any action.\n\n"
        b"# Escalation Procedure\n\n"
        b"If the warning persists, open a change record and notify the on-call storage "
        b"engineer. Do not restart the controller without an approved change window."
    ).decode()

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-retrieval-curator"),
            document_knowledge_service=knowledge_service,
        )
    ) as curator_client:
        csrf = _login(curator_client)
        drafted = curator_client.post(
            "/api/v1/knowledge/documents/drafts",
            json={
                "content_base64": content_base64,
                "title": "Storage Controller Runbook",
                "draft_domain": "domain.storage-operations",
                "content_type": "text/markdown",
                "classification": "classification.internal",
                "access_policy_id": "access-policy.default",
                "retention_policy_id": "retention-policy.default",
                "purpose": "Curate a runbook draft for the document knowledge retrieval test.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert drafted.status_code == 201
        draft = drafted.json()["data"]

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-retrieval-reviewer"),
            document_knowledge_service=knowledge_service,
        )
    ) as reviewer_client:
        csrf = _login(reviewer_client)
        reviewed = reviewer_client.post(
            "/api/v1/knowledge/documents/reviews",
            json={
                "draft_id": draft["draft_id"],
                "decision": "passed",
                "findings": ["The restart sequence matches the vendor-approved procedure."],
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert reviewed.status_code == 201
        review = reviewed.json()["data"]

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-retrieval-approver"),
            document_knowledge_service=knowledge_service,
        )
    ) as approver_client:
        csrf = _login(approver_client)
        approved = approver_client.post(
            "/api/v1/knowledge/documents/approvals",
            json={
                "review_id": review["review_id"],
                "decision": "approved",
                "rationale": "Independent final approval after a passed domain review.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert approved.status_code == 201
        approval = approved.json()["data"]

        prepared = approver_client.post(
            "/api/v1/knowledge/documents/publication-preparations",
            json={
                "approval_id": approval["approval_id"],
                "chunking_profile_digest": sha256(
                    b"knowledge-chunking-profile.retrieval-wiring-test"
                ).hexdigest(),
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert prepared.status_code == 201
        preparation = prepared.json()["data"]

    with TestClient(
        create_app(
            _settings(development_subject_id="subject.document-knowledge-retrieval-indexer"),
            document_knowledge_service=knowledge_service,
            document_knowledge_retrieval_service=retrieval_service,
        )
    ) as retrieval_client:
        csrf = _login(retrieval_client)

        indexed_unknown_preparation = retrieval_client.post(
            "/api/v1/knowledge/documents/index",
            json={"preparation_id": "document-knowledge-preparation.does-not-exist"},
            headers={"X-CSRF-Token": csrf},
        )
        assert indexed_unknown_preparation.status_code == 404
        assert (
            indexed_unknown_preparation.json()["code"] == "document_knowledge_preparation_not_found"
        )

        indexed = retrieval_client.post(
            "/api/v1/knowledge/documents/index",
            json={"preparation_id": preparation["preparation_id"]},
            headers={"X-CSRF-Token": csrf},
        )
        assert indexed.status_code == 201
        assert indexed.headers["Cache-Control"] == "no-store"
        index_data = indexed.json()["data"]
        assert index_data["preparation_id"] == preparation["preparation_id"]
        assert index_data["chunk_count"] >= 1

        searched = retrieval_client.post(
            "/api/v1/knowledge/documents/search",
            json={
                "query": "storage controller warning status escalation",
                "top_k": 3,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert searched.status_code == 200
        assert searched.headers["Cache-Control"] == "no-store"
        results = searched.json()["data"]
        assert results
        assert results[0]["knowledge_item_id"] == draft["knowledge_item_id"]
        assert (
            "controller" in results[0]["excerpt"].lower()
            or "escalation" in results[0]["excerpt"].lower()
        )


def test_knowledge_document_lifecycle_wiring_requires_authentication() -> None:
    """No session cookie and no development identity: the route must fail closed at
    authentication, not merely at authorization -- proving `browser_session_subject` really runs
    ahead of every permission dependency in this file's coverage.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post("/api/v1/knowledge/documents/drafts", json={})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_knowledge_document_lifecycle_wiring_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must be denied by the
    real `AuthorizationService`, not by a faked dependency override, for every permission gating
    this file's coverage: the six ``document_knowledge.py`` permissions and one representative
    (create) endpoint for each of the eight ``operational_knowledge_*`` stage-chain route files.

    FastAPI resolves each route's `Depends(authorize_...)` sub-dependency (which itself depends on
    `browser_session_subject`) before parsing the request body -- see
    `fastapi.dependencies.utils.solve_dependencies`, which walks `dependant.dependencies` and
    calls each sub-dependency directly, well before `request_body_to_args` runs for the endpoint's
    own body. So the denial below fires, and is asserted, before any of these placeholder,
    intentionally-nonexistent path identifiers or empty bodies would ever reach real service
    logic -- an empty body is deliberately used throughout to prove that.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        paths = (
            "/api/v1/knowledge/documents/drafts",
            "/api/v1/knowledge/documents/reviews",
            "/api/v1/knowledge/documents/approvals",
            "/api/v1/knowledge/documents/publication-preparations",
            "/api/v1/knowledge/documents/index",
            "/api/v1/knowledge/documents/search",
            "/api/v1/knowledge/review-requests/review-request.denied/final-resolutions",
            "/api/v1/knowledge/final-resolutions/final-resolution.denied/publication-preparations",
            "/api/v1/knowledge/publication-preparations/publication-preparation.denied/"
            "source-materializations",
            "/api/v1/knowledge/source-materializations/source-materialization.denied/chunk-sets",
            "/api/v1/knowledge/chunk-sets/chunk-set.denied/embedding-sets",
            "/api/v1/knowledge/embedding-sets/embedding-set.denied/index-stages",
            "/api/v1/knowledge/index-stages/index-staging.denied/publications",
            "/api/v1/knowledge/retrieval-publications/retrieval-publication.denied/retrievals",
        )
        for path in paths:
            response = client.post(path, json={}, headers={"X-CSRF-Token": csrf})
            assert response.status_code == 403, f"POST {path}: {response.text}"
            assert response.json()["code"] == "authorization_denied", path
