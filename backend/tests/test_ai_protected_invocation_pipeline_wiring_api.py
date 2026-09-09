"""Pass 22's audit found that the AI protected-invocation chain --
model_context_assembly.py, protected_model_invocation.py, protected_draft_adjudication.py, and
protected_answer_presentation.py -- is real, permission-wired via app.py's
GovernedProtectedModelContextService/GovernedProtectedModelInvocationService/
GovernedProtectedDraftAdjudicationService/GovernedProtectedAnswerPresentationService chain
(each `source=`-wired to the previous stage's service, confirmed by reading app.py's
construction order), and tested at the service layer (test_model_context_assembly.py,
test_protected_model_invocation.py, test_protected_draft_adjudication.py,
test_protected_answer_presentation.py -- including ATLAS-047 SS11/SS18/SS19's real Guardrails
enforcement inside protected_model_invocation) -- but reachable through no HTTP route call
anywhere. These tests drive all four stages through the real HTTP API in their real order
(context -> invocation -> draft adjudication -> answer presentation), not just the service layer
directly, to prove the wiring genuinely closes that gap.

Reaching the first stage over HTTP needs a real, already-retrieved `OperationalKnowledgeRetrieval`
record: model_context_assembly.py's create() route fetches it from
`app.state.operational_knowledge_protected_retrieval_service` and verifies its canonical_digest
and browser-session binding before assembling anything. Building one from scratch over HTTP would
require walking eight more upstream knowledge-ingestion routes (publication-preparations,
source-materializations, chunk-sets, embedding-sets, index-stages, retrieval-publications, and
their own upstream final-resolution/document stages) that are outside this pass's ten-file audit
scope and have their own, separate wiring status. Instead, this module reuses
test_protected_retrieval.py's own `retrieval_fixture()`/`create_retrieval()` -- the same chained
fixture helpers test_model_context_assembly.py's own service-layer tests already rely on -- to
build one real, synthetic-backed retrieval, then swaps it into the running app's
`protected_model_context_service._retrieval_source` the same way test_model_context_assembly.py's
own `StaticRetrievalSource` test double does. This does not touch any of the four routes under
test; it only substitutes a synthetic upstream retrieval for a synthetic downstream one, matching
how every other stage below already gets its upstream by real HTTP object, not by a double.

Settings use `environment="development"` rather than this repo's usual wiring-test
`environment="test"` purely so this reused retrieval's organization/environment IDs
("organization.development"/"environment.development", rooted in test_package_acquisition.py's
`actor()` default and propagated through the whole fixture chain) line up with the running app's
own `development_organization_id`/`environment_id` scope checks; `environment` only ever gates a
`is_production` branch in app.py, so this has no other behavioral effect.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_protected_retrieval import create_retrieval, retrieval_fixture

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.ai.application.protected_answer_presentation import (
    build_development_protected_answer_presentation_policy,
)
from atlas.modules.ai.application.protected_draft_adjudication import (
    build_development_protected_draft_adjudication_policy,
)
from atlas.modules.ai.application.protected_model_invocation import (
    build_development_protected_model_invocation_policy,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.model_context_assembly import (
    GovernedProtectedModelContextService,
    build_development_protected_model_context_policy,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    ProtectedModelContextError,
)
from atlas.modules.knowledge.domain.protected_retrieval import OperationalKnowledgeRetrievalResult

POLICY_ISSUED_AT = datetime(2026, 8, 1, tzinfo=UTC)
POLICY_EXPIRES_AT = datetime(2030, 1, 1, tzinfo=UTC)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "development",
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


async def _build_retrieval() -> OperationalKnowledgeRetrievalResult:
    """Builds one real retrieval via the same chained synthetic fixture helpers
    test_model_context_assembly.py's own service-layer tests use, then re-dates its
    `expires_at` to expire tomorrow and recomputes its canonical_digest with the same digest
    function GovernedProtectedModelContextService uses to verify it. The upstream fixture chain
    is rooted in fixed 2026-08-05 timestamps, which are already in the past relative to the real
    wall clock the HTTP-facing services below use; without this, every stage's
    `now >= record.expires_at` source-freshness check would fail immediately. Recomputing the
    digest after the edit mirrors `_signed_context_policy`/`_signed_invocation_policy` in
    test_model_context_assembly.py/test_protected_model_invocation.py, which do the same thing to
    a policy's signature.
    """
    service, _, publication, policy, actor, *_ = await retrieval_fixture()
    retrieval = await create_retrieval(service, publication, policy, actor)
    future_expiry = datetime.now(UTC) + timedelta(days=1)
    patched = replace(retrieval.record, expires_at=future_expiry, canonical_digest="0" * 64)
    patched = replace(
        patched,
        canonical_digest=GovernedProtectedModelContextService._digest(
            GovernedProtectedModelContextService._payload(patched)
        ),
    )
    return replace(retrieval, record=patched)


class _StaticRetrievalSource:
    """A retrieval_source double returning one fixed retrieval regardless of browser session,
    mirroring `StaticRetrievalSource` in test_model_context_assembly.py. Each of the four routes
    under test independently re-derives its own browser-session binding from the real
    authenticated HTTP session at its own stage, so this double does not need to replicate that
    check to prove those four routes reach their real, wired services.
    """

    def __init__(self, result: OperationalKnowledgeRetrievalResult) -> None:
        self._result = result

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        retrieval_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult:
        del actor, browser_session_id, correlation_id
        if retrieval_id != self._result.record.retrieval_id:
            raise ProtectedModelContextError("protected_model_context_source_not_found")
        return self._result


@dataclass(frozen=True)
class ProtectedAnswerPresentationOutcome:
    """The fields test_recommendation_protected_adjudication_pipeline_wiring_api.py needs to
    continue this same pipeline into the recommendation protected-adjudication chain."""

    presentation_id: str
    presentation_digest: str
    presentation_purpose: str


def run_protected_invocation_pipeline_via_http(
    app: FastAPI, client: TestClient, csrf: str
) -> ProtectedAnswerPresentationOutcome:
    """Drives one real retrieval through all four AI protected-invocation routes over HTTP, in
    their real stage order, asserting real status codes and real response fields at each stage.
    Reused by test_recommendation_protected_adjudication_pipeline_wiring_api.py, which chains its
    own recommendation-candidate generation off this same presentation, matching how
    app.py wires `protected_recommendation_candidate_service`'s `presentation_source=` directly
    to `protected_answer_presentation_service`.
    """
    settings = _settings()
    organization_id = settings.development_organization_id
    environment_id = f"environment.{settings.environment}"

    retrieval = asyncio.run(_build_retrieval())
    assert retrieval.record.organization_id == organization_id
    assert retrieval.record.environment_id == environment_id
    app.state.protected_model_context_service._retrieval_source = _StaticRetrievalSource(retrieval)

    context_policy = build_development_protected_model_context_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    context_response = client.post(
        f"/api/v1/ai/retrievals/{retrieval.record.retrieval_id}/model-contexts",
        json={
            "retrieval_digest": retrieval.record.canonical_digest,
            "context_policy_id": context_policy.policy_id,
            "context_policy_digest": context_policy.canonical_digest,
            "objective": "Analyze the retrieved controller warning evidence with citations.",
            "purpose": retrieval.record.purpose,
            "acknowledged_untrusted_intent": True,
            "acknowledged_citation_boundaries": True,
            "acknowledged_no_model_or_operational_authority": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-model-context-0001"},
    )
    assert context_response.status_code == 201, context_response.text
    context = context_response.json()["data"]["context"]
    assert context["outcome"] == "context-outcome.assembled"
    assert context["included_evidence_count"] == 1
    assert context["knowledge_retrieved"] is True
    assert context["model_invoked"] is False

    context_get = client.get(
        f"/api/v1/ai/retrievals/{retrieval.record.retrieval_id}/model-contexts/{context['context_id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert context_get.status_code == 200
    assert context_get.json()["data"]["context"]["reused"] is True

    invocation_policy = build_development_protected_model_invocation_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    invocation_response = client.post(
        f"/api/v1/ai/model-contexts/{context['context_id']}/invocations",
        json={
            "context_digest": context["canonical_digest"],
            "invocation_policy_id": invocation_policy.policy_id,
            "invocation_policy_digest": invocation_policy.canonical_digest,
            "purpose": context["purpose"],
            "acknowledged_draft_is_untrusted": True,
            "acknowledged_citations_and_unknowns_require_validation": True,
            "acknowledged_no_answer_or_operational_authority": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-model-invocation-0001"},
    )
    assert invocation_response.status_code == 201, invocation_response.text
    invocation = invocation_response.json()["data"]["invocation"]
    assert invocation["outcome"] == "invocation-outcome.completed"
    assert invocation["protected_draft_available"] is True
    assert invocation["answer_generated"] is False
    assert invocation["context_id"] == context["context_id"]

    invocation_get = client.get(
        f"/api/v1/ai/model-contexts/{context['context_id']}/invocations/{invocation['invocation_id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert invocation_get.status_code == 200
    assert (
        invocation_get.json()["data"]["invocation"]["invocation_id"] == invocation["invocation_id"]
    )

    adjudication_policy = build_development_protected_draft_adjudication_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    adjudication_response = client.post(
        f"/api/v1/ai/model-invocations/{invocation['invocation_id']}/adjudications",
        json={
            "invocation_digest": invocation["canonical_digest"],
            "adjudication_policy_id": adjudication_policy.policy_id,
            "adjudication_policy_digest": adjudication_policy.canonical_digest,
            "purpose": invocation["purpose"],
            "acknowledged_draft_is_untrusted": True,
            "acknowledged_no_content_presentation": True,
            "acknowledged_no_answer_or_operational_authority": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-draft-adjudication-0001"},
    )
    assert adjudication_response.status_code == 201, adjudication_response.text
    adjudication = adjudication_response.json()["data"]["adjudication"]
    assert adjudication["outcome"] == "adjudication-outcome.eligible"
    assert adjudication["model_draft_adjudicated"] is True
    assert adjudication["answer_generated"] is False
    assert adjudication["invocation_id"] == invocation["invocation_id"]

    adjudication_get = client.get(
        f"/api/v1/ai/model-invocations/{invocation['invocation_id']}/adjudications/{adjudication['adjudication_id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert adjudication_get.status_code == 200
    assert (
        adjudication_get.json()["data"]["adjudication"]["adjudication_id"]
        == adjudication["adjudication_id"]
    )

    presentation_policy = build_development_protected_answer_presentation_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    presentation_response = client.post(
        f"/api/v1/ai/draft-adjudications/{adjudication['adjudication_id']}/presentations",
        json={
            "adjudication_digest": adjudication["canonical_digest"],
            "presentation_policy_id": presentation_policy.policy_id,
            "presentation_policy_digest": presentation_policy.canonical_digest,
            "purpose": adjudication["purpose"],
            "acknowledged_bounded_decision_support": True,
            "acknowledged_citations_and_unknowns_are_material": True,
            "acknowledged_no_recommendation_or_operational_authority": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-answer-presentation-0001"},
    )
    assert presentation_response.status_code == 201, presentation_response.text
    presentation_data = presentation_response.json()["data"]
    presentation = presentation_data["presentation"]
    answer = presentation_data["answer"]
    assert presentation["recommendation_generated"] is False
    assert presentation["adjudication_id"] == adjudication["adjudication_id"]
    assert answer["summary"]
    assert len(answer["citation_references"]) == 1
    assert len(answer["unknowns"]) == 2

    presentation_get = client.get(
        f"/api/v1/ai/draft-adjudications/{adjudication['adjudication_id']}/presentations/{presentation['presentation_id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert presentation_get.status_code == 200
    assert (
        presentation_get.json()["data"]["presentation"]["presentation_id"]
        == presentation["presentation_id"]
    )

    return ProtectedAnswerPresentationOutcome(
        presentation_id=presentation["presentation_id"],
        presentation_digest=presentation["canonical_digest"],
        presentation_purpose=presentation["purpose"],
    )


def test_protected_invocation_pipeline_is_reachable_through_the_api() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        outcome = run_protected_invocation_pipeline_via_http(app, client, csrf)
        assert outcome.presentation_id.startswith("protected-answer-presentation.")


def test_protected_model_context_creation_is_idempotent_through_the_api() -> None:
    """ATLAS-047's protected-invocation chain claims idempotency by (subject, idempotency key)
    before ever assembling anything (see GovernedProtectedModelContextService.create()'s claim
    step) -- a replayed create request with the same Idempotency-Key must return the exact same
    context, marked `reused`, rather than assembling a second one. This is real, HTTP-observable
    behavior distinct from the plain happy-path test above.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        settings = _settings()
        organization_id = settings.development_organization_id
        environment_id = f"environment.{settings.environment}"

        retrieval = asyncio.run(_build_retrieval())
        app.state.protected_model_context_service._retrieval_source = _StaticRetrievalSource(
            retrieval
        )
        context_policy = build_development_protected_model_context_policy(
            organization_id=organization_id,
            environment_id=environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )
        payload = {
            "retrieval_digest": retrieval.record.canonical_digest,
            "context_policy_id": context_policy.policy_id,
            "context_policy_digest": context_policy.canonical_digest,
            "objective": "Analyze the retrieved controller warning evidence with citations.",
            "purpose": retrieval.record.purpose,
            "acknowledged_untrusted_intent": True,
            "acknowledged_citation_boundaries": True,
            "acknowledged_no_model_or_operational_authority": True,
        }
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-model-context-replay-0001"}

        first = client.post(
            f"/api/v1/ai/retrievals/{retrieval.record.retrieval_id}/model-contexts",
            json=payload,
            headers=headers,
        )
        assert first.status_code == 201, first.text
        first_context = first.json()["data"]["context"]
        assert first_context["reused"] is False

        replay = client.post(
            f"/api/v1/ai/retrievals/{retrieval.record.retrieval_id}/model-contexts",
            json=payload,
            headers=headers,
        )
        assert replay.status_code == 201, replay.text
        replay_context = replay.json()["data"]["context"]
        assert replay_context["reused"] is True
        assert replay_context["context_id"] == first_context["context_id"]
        assert replay_context["canonical_digest"] == first_context["canonical_digest"]
