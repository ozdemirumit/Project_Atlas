"""Pass 22's audit found ten route files with real, permission-wired services behind them but no
HTTP route call anywhere. Six of them name a "recommendation protected-adjudication chain":
protected_recommendation_candidates.py, protected_candidate_impacts.py,
protected_candidate_risk_recovery.py, protected_recommendation_adjudications.py,
final_recommendation_dispositions.py, and recommendation_correction_resubmissions.py. Reading
app.py's construction order (grep for `presentation_source=`, `candidate_source=`,
`impact_source=`, `completion_source=`, and `source=`) shows these six are actually two
*unconnected* pipelines, not one:

1. protected_recommendation_candidates.py -> protected_candidate_impacts.py ->
   protected_candidate_risk_recovery.py -> protected_recommendation_adjudications.py is real and
   does chain directly off the AI protected-invocation pipeline in
   test_ai_protected_invocation_pipeline_wiring_api.py: `protected_recommendation_candidate_service`
   is built with `presentation_source=resolved_protected_answer_presentation_service` -- the exact
   service that module's four routes already drive to a real, HTTP-created presentation. The four
   tests below reuse that module's `run_protected_invocation_pipeline_via_http()` helper and then
   walk these four further routes over HTTP in their real order, the same way that module proves
   its own four routes.

2. final_recommendation_dispositions.py and recommendation_correction_resubmissions.py do *not*
   chain from the candidate/impact/risk-recovery/adjudication pipeline above. Both are built with
   `source=resolved_recommendation_track_review_decision_service` -- a service belonging to an
   entirely separate, much deeper "human review" pipeline (promotion -> readiness -> review
   request -> reviewer assignment -> protected inspection -> human review finding -> finding
   presentation -> track review decision) that this pass's ten-file audit does not otherwise
   cover. `final_disposition_fixture()`/`correction_fixture()` in
   test_final_recommendation_disposition.py/test_recommendation_correction_resubmission.py already
   build real objects for that separate pipeline via `RecommendationTrackReviewDecisionService`'s
   own `final_disposition_source()`/`correction_resubmission_source()` methods and wrap them in a
   `StaticFinalDispositionSource` double (mirroring the same `Static*Source` pattern
   test_ai_protected_invocation_pipeline_wiring_api.py reuses for its own retrieval) -- this module
   reuses that same real, synthetic-backed pair of fixtures.

   Driving either route's create endpoint over real HTTP originally surfaced a second, independent
   gap: `RECOMMENDATION_FINAL_DISPOSITION_CREATE`/`_READ` and
   `RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE`/`_READ` were defined as permissions and were
   included in `DEVELOPMENT_ROLE_ID`'s permission set in
   backend/src/atlas/modules/authorization/application/bootstrap.py, but -- unlike every sibling
   permission in this pipeline -- neither was ever bound to a scope by any `RoleAssignment` in that
   file. So no identity, including the "atlas-demo" development identity every other wiring test in
   this repo relies on, could ever pass authorization for these two routes.

   **This bug is now fixed.** `build_development_authorization_service()` now includes
   `RoleAssignment` entries binding `DEVELOPMENT_ROLE_ID` to
   `recommendation_final_disposition_scope`/`recommendation_correction_resubmission_scope` for both
   permissions -- see `assignment.development.recommendation-final-disposition-create`/`-read` and
   `assignment.development.recommendation-correction-resubmission-create`/`-read` in bootstrap.py.
   The two tests below now drive each route to a genuine `201 Created`, proving real end-to-end
   reachability, not just that the authorization layer is reached:

   - `test_final_recommendation_disposition_route_is_wired_to_real_authorization` reuses
     `final_disposition_fixture()`'s real decisions/request/readiness/artifact chain unchanged
     (its baked-in "who consumed this recommendation" identity is only checked for *separation*
     here -- the disposition approver must NOT be that consumer -- which the real "atlas-demo"
     development identity naturally satisfies) and only re-dates each object's fixed,
     already-expired `expires_at` to the future and recomputes each object's `canonical_digest`
     with the same digest functions its own owning service uses, mirroring
     `test_ai_protected_invocation_pipeline_wiring_api.py`'s `_build_retrieval()` re-dating of a
     similarly fixed-clock fixture. It also fixes `disposition_code` to the real
     `FINAL_ACCEPTED` domain constant (`"recommendation-disposition.accepted"`, not the
     unrelated-looking string this test used before the fix was confirmed empirically -- disposition
     codes are validated against a fixed set once the route is actually reached).

   - `test_recommendation_correction_resubmission_route_is_wired_to_real_authorization` reuses
     `correction_fixture()`'s real chain the same way, but that chain's
     `PromotedRecommendationArtifact` carries a `consumer_subject_digest` baked in against one
     fixed fixture identity (`"subject.knowledge-retrieval-consumer"`), and
     `RecommendationCorrectionService._verify_source` requires the *creating* actor's subject id
     to match that consumer digest (the correction author must be the original consumer, not
     merely separated from them, unlike final disposition's approver-separation check above).
     Confirmed by direct experiment: the real "atlas-demo" development identity's subject id does
     not match, and hand-editing the fixture's `consumer_subject_digest` to force a match would
     defeat the exact identity-continuity invariant this check exists to enforce, so this test
     instead builds its own app with
     `development_subject_id="subject.knowledge-retrieval-consumer"` -- the same
     settings-override mechanism
     `test_recommendation_review_promotion_pipeline_wiring_requires_permission` already uses for
     `development_role_ids` -- so the real, live-authenticated "atlas-demo" HTTP session resolves
     to that exact subject id (`development.py`'s dev identity provider sets
     `subject_id=self._settings.development_subject_id` directly), making the match genuine
     rather than fabricated. This test also fixes a second, independent gap this pass's audit
     found: the route under test was never pointed at `correction_fixture()`'s populated
     `RecommendationTrackReviewDecisionService`
     (`app.state.recommendation_correction_service._source` was left as the app's real, empty
     production source), so even after both identity and authorization line up, the route used to
     return `404 recommendation_correction_source_not_found` instead of reaching the fixture data
     at all; this test now sets that source override, the same way
     `test_final_recommendation_disposition_route_is_wired_to_real_authorization` already did.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from test_ai_protected_invocation_pipeline_wiring_api import (
    POLICY_EXPIRES_AT,
    POLICY_ISSUED_AT,
    _settings,
    run_protected_invocation_pipeline_via_http,
)
from test_final_recommendation_disposition import (
    StaticFinalDispositionSource,
    final_disposition_fixture,
)
from test_recommendation_correction_resubmission import correction_fixture

from atlas.api.app import create_app
from atlas.modules.ai.application.protected_candidate_impact_enrichment import (
    build_development_protected_candidate_impact_policy,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion import (
    build_development_protected_candidate_risk_recovery_policy,
)
from atlas.modules.ai.application.protected_recommendation_adjudication import (
    build_development_protected_recommendation_adjudication_policy,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation import (
    build_development_protected_recommendation_candidate_policy,
)
from atlas.modules.recommendations.application.correction_resubmission import (
    RecommendationCorrectionService,
    build_development_recommendation_correction_policy,
)
from atlas.modules.recommendations.application.final_disposition import (
    build_development_final_recommendation_disposition_policy,
)
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
)
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
)
from atlas.modules.recommendations.application.review_decision import (
    RecommendationTrackReviewDecisionService,
)
from atlas.modules.recommendations.application.review_request import (
    GovernedRecommendationReviewRequestService,
)
from atlas.modules.recommendations.domain.final_disposition import FINAL_ACCEPTED


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def test_protected_recommendation_adjudication_pipeline_is_reachable_through_the_api() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        settings = _settings()
        organization_id = settings.development_organization_id
        environment_id = f"environment.{settings.environment}"

        presentation = run_protected_invocation_pipeline_via_http(app, client, csrf)

        candidate_policy = build_development_protected_recommendation_candidate_policy(
            organization_id=organization_id,
            environment_id=environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )
        candidate_response = client.post(
            f"/api/v1/ai/answer-presentations/{presentation.presentation_id}/recommendation-candidate-sets",
            json={
                "presentation_digest": presentation.presentation_digest,
                "generation_policy_id": candidate_policy.policy_id,
                "generation_policy_digest": candidate_policy.canonical_digest,
                "purpose": presentation.presentation_purpose,
                "acknowledged_candidates_are_incomplete": True,
                "acknowledged_impact_and_recovery_are_unverified": True,
                "acknowledged_no_recommendation_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "wiring-recommendation-candidate-0001",
            },
        )
        assert candidate_response.status_code == 201, candidate_response.text
        candidate_set = candidate_response.json()["data"]["candidate_set"]
        assert candidate_set["recommendation_candidates_generated"] is True
        assert candidate_set["service_impact_analyzed"] is False
        assert candidate_set["candidate_count"] == 3
        assert candidate_set["presentation_id"] == presentation.presentation_id

        candidate_get = client.get(
            f"/api/v1/ai/answer-presentations/{presentation.presentation_id}/recommendation-candidate-sets/{candidate_set['candidate_set_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert candidate_get.status_code == 200
        assert (
            candidate_get.json()["data"]["candidate_set"]["candidate_set_id"]
            == candidate_set["candidate_set_id"]
        )

        impact_policy = build_development_protected_candidate_impact_policy(
            organization_id=organization_id,
            environment_id=environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )
        impact_response = client.post(
            f"/api/v1/ai/recommendation-candidate-sets/{candidate_set['candidate_set_id']}/impact-analyses",
            json={
                # The content digest, not the wrapping record's canonical_digest -- the impact
                # service verifies this against the candidate *content* object it rehydrates, a
                # separate field from `candidate_set["canonical_digest"]` (confirmed by reading
                # `_verify_candidate_source` in protected_candidate_impact_enrichment.py).
                "candidate_set_digest": candidate_set["candidate_content_digest"],
                "impact_policy_id": impact_policy.policy_id,
                "impact_policy_digest": impact_policy.canonical_digest,
                "purpose": candidate_set["purpose"],
                "acknowledged_reachability_is_not_outage_evidence": True,
                "acknowledged_impact_remains_provisional": True,
                "acknowledged_no_recommendation_or_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-candidate-impact-0001"},
        )
        assert impact_response.status_code == 201, impact_response.text
        impact_analysis = impact_response.json()["data"]["impact_analysis"]
        assert impact_analysis["service_impact_analyzed"] is True
        assert impact_analysis["outage_confirmed"] is False
        assert impact_analysis["candidate_set_id"] == candidate_set["candidate_set_id"]

        impact_get = client.get(
            f"/api/v1/ai/recommendation-candidate-sets/{candidate_set['candidate_set_id']}/impact-analyses/{impact_analysis['impact_analysis_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert impact_get.status_code == 200
        assert (
            impact_get.json()["data"]["impact_analysis"]["impact_analysis_id"]
            == impact_analysis["impact_analysis_id"]
        )

        risk_policy = build_development_protected_candidate_risk_recovery_policy(
            organization_id=organization_id,
            environment_id=environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )
        risk_response = client.post(
            f"/api/v1/ai/candidate-impact-analyses/{impact_analysis['impact_analysis_id']}/risk-recovery-completions",
            json={
                "impact_digest": impact_analysis["canonical_digest"],
                "completion_policy_id": risk_policy.policy_id,
                "completion_policy_digest": risk_policy.canonical_digest,
                "purpose": impact_analysis["purpose"],
                "acknowledged_estimates_are_not_guarantees": True,
                "acknowledged_unknowns_cannot_lower_risk": True,
                "acknowledged_no_preference_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "wiring-candidate-risk-recovery-0001",
            },
        )
        assert risk_response.status_code == 201, risk_response.text
        completion = risk_response.json()["data"]["completion"]
        assert completion["risk_completed"] is True
        assert completion["recovery_completed"] is True
        assert completion["recommendation_complete"] is False
        assert completion["impact_analysis_id"] == impact_analysis["impact_analysis_id"]

        completion_get = client.get(
            f"/api/v1/ai/candidate-impact-analyses/{impact_analysis['impact_analysis_id']}/risk-recovery-completions/{completion['completion_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert completion_get.status_code == 200
        assert (
            completion_get.json()["data"]["completion"]["completion_id"]
            == completion["completion_id"]
        )

        adjudication_policy = build_development_protected_recommendation_adjudication_policy(
            organization_id=organization_id,
            environment_id=environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )
        adjudication_response = client.post(
            f"/api/v1/ai/candidate-risk-recovery-completions/{completion['completion_id']}/adjudications",
            json={
                "completion_digest": completion["canonical_digest"],
                "adjudication_policy_id": adjudication_policy.policy_id,
                "adjudication_policy_digest": adjudication_policy.canonical_digest,
                "purpose": completion["purpose"],
                "acknowledged_preference_is_not_approval": True,
                "acknowledged_tie_or_no_support_is_valid": True,
                "acknowledged_no_presentation_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "wiring-recommendation-adjudication-0001",
            },
        )
        assert adjudication_response.status_code == 201, adjudication_response.text
        adjudication = adjudication_response.json()["data"]["adjudication"]
        assert adjudication["recommendation_complete"] is True
        assert adjudication["eligible_count"] == 3
        assert adjudication["preferred_count"] == 1
        assert adjudication["tie"] is False
        assert adjudication["completion_id"] == completion["completion_id"]

        adjudication_get = client.get(
            f"/api/v1/ai/candidate-risk-recovery-completions/{completion['completion_id']}/adjudications/{adjudication['adjudication_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert adjudication_get.status_code == 200
        assert (
            adjudication_get.json()["data"]["adjudication"]["adjudication_id"]
            == adjudication["adjudication_id"]
        )


def test_final_recommendation_disposition_route_is_wired_to_real_authorization() -> None:
    """final_recommendation_dispositions.py's create and read routes are registered, require a
    real authenticated session, and reach the real
    `authorize_recommendation_final_disposition_create`/`_read` dependencies against
    `app.state.authorization_service` -- confirmed here by a fully valid, schema-passing request
    (built from a real `final_disposition_fixture()`, re-dated to a future `expires_at` the same
    way `test_ai_protected_invocation_pipeline_wiring_api.py`'s `_build_retrieval()` re-dates its
    own fixed-clock fixture) now genuinely creating and reading back a real final recommendation
    disposition now that the missing `RoleAssignment` documented in this module's docstring has
    been fixed.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)

        (
            _service,
            _repository,
            decisions,
            request_record,
            readiness,
            artifact,
            _policy,
            _actor,
            *_rest,
        ) = asyncio.run(final_disposition_fixture())

        future_expiry = datetime.now(UTC) + timedelta(days=1)

        artifact = replace(artifact, expires_at=future_expiry, canonical_digest="0" * 64)
        artifact = replace(
            artifact,
            canonical_digest=GovernedRecommendationPromotionService._artifact_digest(artifact),
        )

        readiness = replace(
            readiness,
            expires_at=future_expiry,
            source_artifact_digest=artifact.canonical_digest,
            canonical_digest="0" * 64,
        )
        readiness = replace(
            readiness,
            canonical_digest=GovernedRecommendationReadinessService._assessment_digest(readiness),
        )

        request_record = replace(
            request_record, expires_at=future_expiry, canonical_digest="0" * 64
        )
        request_record = replace(
            request_record,
            canonical_digest=GovernedRecommendationReviewRequestService._record_digest(
                request_record
            ),
        )

        redated_decisions = []
        for decision in decisions:
            redated = replace(
                decision,
                expires_at=future_expiry,
                recommendation_artifact_digest=artifact.canonical_digest,
                canonical_digest="0" * 64,
            )
            redated = replace(
                redated,
                canonical_digest=RecommendationTrackReviewDecisionService._digest(
                    RecommendationTrackReviewDecisionService._record_payload(redated)
                ),
            )
            redated_decisions.append(redated)
        decisions = tuple(redated_decisions)

        app.state.final_recommendation_disposition_service._source = StaticFinalDispositionSource(
            decisions=decisions,
            request=request_record,
            readiness=readiness,
            artifact=artifact,
        )
        policy = build_development_final_recommendation_disposition_policy(
            organization_id=request_record.organization_id,
            environment_id=request_record.environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        response = client.post(
            f"/api/v1/recommendations/review-requests/{request_record.review_request_id}/final-dispositions",
            json={
                "review_request_digest": request_record.canonical_digest,
                "recommendation_id": artifact.recommendation_id,
                "recommendation_digest": artifact.canonical_digest,
                "decision_ids": [decisions[0].decision_id, decisions[1].decision_id],
                "decision_digests": [decisions[0].canonical_digest, decisions[1].canonical_digest],
                "disposition_code": FINAL_ACCEPTED,
                "basis_codes": ["recommendation-final-basis.review-evidence-sufficient"],
                "disposition_policy_id": policy.policy_id,
                "disposition_policy_digest": policy.canonical_digest,
                "purpose": (
                    "Record the accountable final recommendation disposition for this review "
                    "generation."
                ),
                "acknowledged_immutable_review_generation": True,
                "acknowledged_recommendation_level_decision_only": True,
                "acknowledged_handoff_eligibility_only": True,
                "acknowledged_no_workflow_itsm_change_or_operational_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "wiring-final-disposition-0001"},
        )

        assert response.status_code == 201, response.text
        body = response.json()["data"]
        assert body["review_request_id"] == request_record.review_request_id
        assert body["recommendation_id"] == artifact.recommendation_id
        assert body["disposition_code"] == FINAL_ACCEPTED
        assert body["state"] == "recommendation_final_accepted"
        assert body["final_disposition_recorded"] is True
        assert body["technical_review_passed"] is True
        assert body["service_impact_review_passed"] is True
        assert body["recommendation_approved"] is True
        assert body["workflow_handoff_eligible"] is True
        assert body["workflow_created"] is False
        assert body["infrastructure_mutated"] is False

        fetched = client.get(
            f"/api/v1/recommendations/review-requests/{request_record.review_request_id}/"
            f"final-dispositions/{body['disposition_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["data"]["disposition_id"] == body["disposition_id"]


def test_recommendation_correction_resubmission_route_is_wired_to_real_authorization() -> None:
    """recommendation_correction_resubmissions.py's create and read routes are registered,
    require a real authenticated session, and reach the real
    `authorize_recommendation_correction_resubmission_create`/`_read` dependencies against
    `app.state.authorization_service` -- confirmed here by a fully valid, schema-passing request
    (built from a real `correction_fixture()`) now genuinely creating and reading back a real
    recommendation correction now that the missing `RoleAssignment` documented in this module's
    docstring has been fixed.

    `correction_fixture()`'s source artifact carries a `consumer_subject_digest` baked in against
    the fixed fixture identity "subject.knowledge-retrieval-consumer", and
    `RecommendationCorrectionService._verify_source` requires the real, live-authenticated actor's
    subject id to match it exactly (the correction author must be the original consumer). This app
    is therefore built with `development_subject_id="subject.knowledge-retrieval-consumer"` so the
    real "atlas-demo" HTTP session resolves to that exact subject -- see this module's docstring
    for why this is a genuine match, not a fabricated one, and why `app.state.
    recommendation_correction_service._source` must also be pointed at the fixture's populated
    decision service (a second, independent gap this pass's audit found).
    """
    settings = _settings(development_subject_id="subject.knowledge-retrieval-consumer")
    app = create_app(settings)
    with TestClient(app) as client:
        csrf = _login(client)

        (
            service,
            _repository,
            decisions,
            artifact,
            _policy,
            _actor,
            _adapter,
            *_rest,
        ) = asyncio.run(correction_fixture())

        app.state.recommendation_correction_service._source = service._source

        source = decisions[0]
        policy = build_development_recommendation_correction_policy(
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        response = client.post(
            f"/api/v1/recommendations/review-requests/{source.review_request_id}/corrections",
            json={
                "source_review_request_digest": source.source_review_request_digest,
                "source_recommendation_id": artifact.recommendation_id,
                "source_recommendation_digest": artifact.canonical_digest,
                "source_decision_ids": [decisions[0].decision_id, decisions[1].decision_id],
                "source_decision_digests": [
                    decisions[0].canonical_digest,
                    decisions[1].canonical_digest,
                ],
                "correction_submission_id": "recommendation-correction-submission.wiring-test-0001",
                "correction_submission_digest": RecommendationCorrectionService._digest(
                    "opaque-correction-submission-001"
                ),
                "correction_policy_id": policy.policy_id,
                "correction_policy_digest": policy.canonical_digest,
                "purpose": (
                    "Create a corrected immutable recommendation version for fresh readiness "
                    "review."
                ),
                "acknowledged_exact_change_requirements_addressed": True,
                "acknowledged_new_immutable_recommendation_version": True,
                "acknowledged_fresh_readiness_required": True,
                "acknowledged_no_review_approval_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "wiring-recommendation-correction-0001",
            },
        )

        assert response.status_code == 201, response.text
        body = response.json()["data"]
        assert body["source_review_request_id"] == source.review_request_id
        assert body["source_recommendation_id"] == artifact.recommendation_id
        assert body["state"] == "recommendation_correction_resubmitted"
        assert body["correction_created"] is True
        assert body["recommendation_promoted"] is True
        assert body["readiness_assessed"] is False
        assert body["review_requested"] is False
        assert body["final_disposition_recorded"] is False
        assert body["workflow_created"] is False
        assert body["infrastructure_mutated"] is False
        assert body["new_recommendation_id"] != artifact.recommendation_id

        fetched = client.get(
            f"/api/v1/recommendations/review-requests/{source.review_request_id}/"
            f"corrections/{body['correction_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["data"]["correction_id"] == body["correction_id"]
