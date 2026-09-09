"""Pass 25 of this session's standing audit loop found five more route files --
``protected_recommendation_presentations.py``, ``recommendation_promotions.py``,
``recommendation_readiness.py``, ``recommendation_review_requests.py``, and
``recommendation_reviewer_assignments.py`` -- with real ``browser_session_subject`` and
``authorize_*`` permission dependencies whose only HTTP-level interaction with the real running
app in their own test files is a schema-registration check against ``/openapi.json``. Every
behavior/permission test in those five files instantiates the service class directly with a mock
``RecordingPermissionAuthorizer``, so the real ``create_app()`` wiring -- permission decorators,
RBAC resolution, request/response schema validation -- had never actually been exercised for these
routes over HTTP.

Reading ``atlas/api/app.py``'s construction order (``presentation_source=``,
``RecommendationReadinessPromotionSourceRouter(primary=...)``, ``promotion_source=``,
``readiness_source=``, ``review_request_source=``) confirms these five form one real chain, in
this exact order:

    protected_recommendation_presentations (adjudication -> presentation)
    -> recommendation_promotions (presentation -> draft recommendation)
    -> recommendation_readiness (recommendation -> review-readiness assessment)
    -> recommendation_review_requests (recommendation + readiness assessment -> review request)
    -> recommendation_reviewer_assignments (recommendation + review request -> reviewer
       assignment)

and that this chain continues directly off the real, already-HTTP-proven protected-adjudication
chain in ``test_recommendation_protected_adjudication_pipeline_wiring_api.py``:
``protected_recommendation_presentation_service`` is built with
``adjudication_source=resolved_protected_recommendation_adjudication_service`` -- the exact
service that module's tests already drive to a real, HTTP-created adjudication. This module reuses
that module's (transitively, ``test_ai_protected_invocation_pipeline_wiring_api.py``'s) real HTTP
sequence to reach one real adjudication, then attempts to continue into this pass's own five
routes.

That attempt surfaced a genuine, confirmed authorization-wiring gap, not an ambiguity: none of the
five scope-builder functions these routes' ``authorize_*`` dependencies and permission-authorizer
adapters call -- ``ai_protected_recommendation_presentation_scope``,
``recommendation_promotion_scope``, ``recommendation_readiness_scope``,
``recommendation_review_request_scope``, and ``recommendation_reviewer_assignment_scope``, all
defined in ``atlas/modules/authorization/application/bootstrap.py`` -- is ever invoked by any
``RoleAssignment`` in that file (each has exactly one occurrence in the whole file: its own
``def``, confirmed by grep). ``AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE/READ``,
``RECOMMENDATION_PROMOTION_CREATE/READ``, ``RECOMMENDATION_READINESS_CREATE/READ``,
``RECOMMENDATION_REVIEW_REQUEST_CREATE/READ``, and
``RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE/READ`` are all defined as permissions and are all
included in ``DEVELOPMENT_ROLE_ID``'s permission set --
but with no ``RoleAssignment`` binding any of them to a scope, ``AuthorizationService.evaluate``
(which requires an *active, scope-matching* assignment, not merely a role that lists the
permission) can never return ``allowed`` for any of these ten permissions, for any identity,
including the "atlas-demo" development identity every other wiring test in this repo relies on.
This was confirmed empirically, not just by reading: a fully logged-in, fully-privileged
development identity receives a real ``403 authorization_denied`` on every one of these ten
routes, identical to what an explicitly zero-permission identity receives.

This is the exact same missing-``RoleAssignment`` bug class
``test_recommendation_protected_adjudication_pipeline_wiring_api.py``'s own docstring already
documents for ``final_recommendation_dispositions.py`` and
``recommendation_correction_resubmissions.py`` two stages further downstream in this same overall
human-review pipeline -- except this pass's audit found it also blocks these five *earlier*
stages, not just those two later ones. Consistent with that module's precedent (and outside a
test-writing pass's scope), this module does not add or repair the missing ``RoleAssignment``
entries. Instead, since a genuine happy path is not achievable through these five routes today,
every test below proves each route is really registered, requires real authentication, and reaches
the real, wired ``AuthorizationService`` -- receiving the current, real ``403 authorization_denied``
on a fully valid, schema-passing request (including, for the first stage, a request built from a
*real* upstream adjudication obtained by driving the real protected-adjudication chain over HTTP)
-- so each denial is provably not a validation error, a 404, or a CSRF-missing 403. See the
accompanying report for a suggested follow-up to add the missing ``RoleAssignment`` entries for
all ten permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_ai_protected_invocation_pipeline_wiring_api import (
    POLICY_EXPIRES_AT,
    POLICY_ISSUED_AT,
    _settings,
    run_protected_invocation_pipeline_via_http,
)

from atlas.api.app import create_app
from atlas.core.config import Settings
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
from atlas.modules.ai.application.protected_recommendation_presentation import (
    build_development_protected_recommendation_presentation_policy,
)
from atlas.modules.recommendations.application.promotion import (
    build_development_recommendation_promotion_policy,
)
from atlas.modules.recommendations.application.readiness import (
    build_development_recommendation_readiness_policy,
)
from atlas.modules.recommendations.application.review_request import (
    build_development_recommendation_review_request_policy,
)
from atlas.modules.recommendations.application.reviewer_assignment import (
    build_development_recommendation_reviewer_assignment_policy,
)

_DENIED = "review-promo-pipeline-denied"


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


@dataclass(frozen=True)
class _RealAdjudicationOutcome:
    """The fields this module needs to attempt a real, schema-valid protected recommendation
    presentation create -- obtained from a real HTTP-driven protected-adjudication chain, not
    fabricated."""

    adjudication_id: str
    adjudication_digest: str
    purpose: str


def _build_real_adjudication_via_http(
    app: FastAPI, client: TestClient, csrf: str
) -> _RealAdjudicationOutcome:
    """Drives one real recommendation candidate-generation -> impact-analysis ->
    risk-recovery-completion -> adjudication chain over HTTP -- the same real sequence
    ``test_recommendation_protected_adjudication_pipeline_wiring_api.py`` already proves --
    purely to obtain one real, schema-valid ``adjudication_id``/``adjudication_digest`` pair for
    this module's own presentation-create reachability test below.
    """
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
        f"/api/v1/ai/answer-presentations/{presentation.presentation_id}/"
        "recommendation-candidate-sets",
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
            "Idempotency-Key": "review-promo-pipeline-candidate-0001",
        },
    )
    assert candidate_response.status_code == 201, candidate_response.text
    candidate_set = candidate_response.json()["data"]["candidate_set"]

    impact_policy = build_development_protected_candidate_impact_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    impact_response = client.post(
        f"/api/v1/ai/recommendation-candidate-sets/{candidate_set['candidate_set_id']}/"
        "impact-analyses",
        json={
            "candidate_set_digest": candidate_set["candidate_content_digest"],
            "impact_policy_id": impact_policy.policy_id,
            "impact_policy_digest": impact_policy.canonical_digest,
            "purpose": candidate_set["purpose"],
            "acknowledged_reachability_is_not_outage_evidence": True,
            "acknowledged_impact_remains_provisional": True,
            "acknowledged_no_recommendation_or_operational_authority": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "review-promo-pipeline-impact-0001"},
    )
    assert impact_response.status_code == 201, impact_response.text
    impact_analysis = impact_response.json()["data"]["impact_analysis"]

    risk_policy = build_development_protected_candidate_risk_recovery_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    risk_response = client.post(
        f"/api/v1/ai/candidate-impact-analyses/{impact_analysis['impact_analysis_id']}/"
        "risk-recovery-completions",
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
            "Idempotency-Key": "review-promo-pipeline-risk-recovery-0001",
        },
    )
    assert risk_response.status_code == 201, risk_response.text
    completion = risk_response.json()["data"]["completion"]

    adjudication_policy = build_development_protected_recommendation_adjudication_policy(
        organization_id=organization_id,
        environment_id=environment_id,
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    adjudication_response = client.post(
        f"/api/v1/ai/candidate-risk-recovery-completions/{completion['completion_id']}/"
        "adjudications",
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
            "Idempotency-Key": "review-promo-pipeline-adjudication-0001",
        },
    )
    assert adjudication_response.status_code == 201, adjudication_response.text
    adjudication = adjudication_response.json()["data"]["adjudication"]
    assert adjudication["recommendation_complete"] is True

    return _RealAdjudicationOutcome(
        adjudication_id=adjudication["adjudication_id"],
        adjudication_digest=adjudication["canonical_digest"],
        purpose=adjudication["purpose"],
    )


def test_protected_recommendation_presentation_route_is_wired_to_real_authorization() -> None:
    """``protected_recommendation_presentations.py``'s create and read routes are registered,
    require a real authenticated session, and reach the real
    ``authorize_protected_recommendation_presentation_create``/``_read`` dependencies against
    ``app.state.authorization_service`` -- confirmed here with a fully valid, schema-passing
    request built from a REAL upstream adjudication (obtained by driving the real
    protected-adjudication chain over HTTP), receiving the real, current ``403
    authorization_denied`` documented in this module's docstring, not a validation error and not
    a 404.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        adjudication = _build_real_adjudication_via_http(app, client, csrf)

        settings = _settings()
        presentation_policy = build_development_protected_recommendation_presentation_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/ai/recommendation-adjudications/{adjudication.adjudication_id}/presentations",
            json={
                "adjudication_digest": adjudication.adjudication_digest,
                "presentation_policy_id": presentation_policy.policy_id,
                "presentation_policy_digest": presentation_policy.canonical_digest,
                "purpose": adjudication.purpose,
                "acknowledged_decision_support_only": True,
                "acknowledged_tie_or_no_support_is_valid": True,
                "acknowledged_no_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-presentation-0001",
            },
        )
        assert created.status_code == 403, created.text
        assert created.json()["code"] == "authorization_denied"

        fetched = client.get(
            f"/api/v1/ai/recommendation-adjudications/{adjudication.adjudication_id}/"
            f"presentations/presentation.{_DENIED}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 403, fetched.text
        assert fetched.json()["code"] == "authorization_denied"


def test_recommendation_promotion_route_is_wired_to_real_authorization() -> None:
    """``recommendation_promotions.py``'s create and read routes are registered, require a real
    authenticated session, and reach the real ``authorize_recommendation_promotion_create``/
    ``_read`` dependencies -- confirmed with a fully valid, schema-passing request receiving the
    real, current ``403 authorization_denied``.
    """
    settings = _settings()
    with TestClient(create_app(settings)) as client:
        csrf = _login(client)
        policy = build_development_recommendation_promotion_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendation-presentations/presentation.{_DENIED}/promotions",
            json={
                "presentation_digest": _digest("review-promo-pipeline-presentation"),
                "promotion_policy_id": policy.policy_id,
                "promotion_policy_digest": policy.canonical_digest,
                "purpose": (
                    "Promote a protected presentation into a draft recommendation as a real "
                    "wiring proof."
                ),
                "acknowledged_draft_only": True,
                "acknowledged_no_review_or_approval": True,
                "acknowledged_no_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-promotion-0001",
            },
        )
        assert created.status_code == 403, created.text
        assert created.json()["code"] == "authorization_denied"

        fetched = client.get(
            f"/api/v1/recommendation-presentations/presentation.{_DENIED}/"
            f"promotions/recommendation.{_DENIED}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 403, fetched.text
        assert fetched.json()["code"] == "authorization_denied"


def test_recommendation_readiness_route_is_wired_to_real_authorization() -> None:
    """``recommendation_readiness.py``'s create and read routes are registered, require a real
    authenticated session, and reach the real ``authorize_recommendation_readiness_create``/
    ``_read`` dependencies -- confirmed with a fully valid, schema-passing request receiving the
    real, current ``403 authorization_denied``.
    """
    settings = _settings()
    with TestClient(create_app(settings)) as client:
        csrf = _login(client)
        policy = build_development_recommendation_readiness_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendations/recommendation.{_DENIED}/review-readiness-assessments",
            json={
                "recommendation_digest": _digest("review-promo-pipeline-recommendation"),
                "readiness_policy_id": policy.policy_id,
                "readiness_policy_digest": policy.canonical_digest,
                "purpose": (
                    "Assess a draft recommendation for human-review readiness as a real wiring "
                    "proof."
                ),
                "acknowledged_readiness_is_not_review": True,
                "acknowledged_blocked_requires_new_version": True,
                "acknowledged_no_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-readiness-0001",
            },
        )
        assert created.status_code == 403, created.text
        assert created.json()["code"] == "authorization_denied"

        fetched = client.get(
            f"/api/v1/recommendations/recommendation.{_DENIED}/"
            f"review-readiness-assessments/assessment.{_DENIED}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 403, fetched.text
        assert fetched.json()["code"] == "authorization_denied"


def test_recommendation_review_request_route_is_wired_to_real_authorization() -> None:
    """``recommendation_review_requests.py``'s create and read routes are registered, require a
    real authenticated session, and reach the real
    ``authorize_recommendation_review_request_create``/``_read`` dependencies -- confirmed with a
    fully valid, schema-passing request receiving the real, current ``403 authorization_denied``.
    """
    settings = _settings()
    with TestClient(create_app(settings)) as client:
        csrf = _login(client)
        policy = build_development_recommendation_review_request_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendations/recommendation.{_DENIED}/human-review-requests",
            json={
                "recommendation_digest": _digest("review-promo-pipeline-recommendation"),
                "readiness_assessment_id": f"assessment.{_DENIED}",
                "readiness_assessment_digest": _digest("review-promo-pipeline-assessment"),
                "review_request_policy_id": policy.policy_id,
                "review_request_policy_digest": policy.canonical_digest,
                "purpose": (
                    "Request policy-owned human review for a ready recommendation as a real "
                    "wiring proof."
                ),
                "acknowledged_request_is_not_assignment_or_review": True,
                "acknowledged_routing_is_policy_owned": True,
                "acknowledged_no_approval_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-review-request-0001",
            },
        )
        assert created.status_code == 403, created.text
        assert created.json()["code"] == "authorization_denied"

        fetched = client.get(
            f"/api/v1/recommendations/recommendation.{_DENIED}/"
            f"human-review-requests/review-request.{_DENIED}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 403, fetched.text
        assert fetched.json()["code"] == "authorization_denied"


def test_recommendation_reviewer_assignment_route_is_wired_to_real_authorization() -> None:
    """``recommendation_reviewer_assignments.py``'s create and read routes are registered,
    require a real authenticated session, and reach the real
    ``authorize_recommendation_reviewer_assignment_create``/``_read`` dependencies -- confirmed
    with a fully valid, schema-passing request receiving the real, current ``403
    authorization_denied``.
    """
    settings = _settings()
    with TestClient(create_app(settings)) as client:
        csrf = _login(client)
        policy = build_development_recommendation_reviewer_assignment_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendations/recommendation.{_DENIED}/reviewer-assignments",
            json={
                "review_request_id": f"review-request.{_DENIED}",
                "review_request_digest": _digest("review-promo-pipeline-review-request"),
                "assignment_policy_id": policy.policy_id,
                "assignment_policy_digest": policy.canonical_digest,
                "purpose": (
                    "Request policy-controlled reviewer assignment for a review request as a "
                    "real wiring proof."
                ),
                "acknowledged_caller_cannot_select_reviewers": True,
                "acknowledged_distinct_reviewers_required": True,
                "acknowledged_no_inspection_decision_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-reviewer-assignment-0001",
            },
        )
        assert created.status_code == 403, created.text
        assert created.json()["code"] == "authorization_denied"

        fetched = client.get(
            f"/api/v1/recommendations/recommendation.{_DENIED}/"
            f"reviewer-assignments/assignment-set.{_DENIED}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 403, fetched.text
        assert fetched.json()["code"] == "authorization_denied"


def test_recommendation_review_promotion_pipeline_wiring_requires_authentication() -> None:
    """No session cookie and development identity disabled: every one of these five routes'
    create endpoints must fail closed at authentication, not merely at authorization -- proving
    ``browser_session_subject`` really runs ahead of every ``authorize_*`` dependency this module
    covers.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = (
            f"/api/v1/ai/recommendation-adjudications/adjudication.{_DENIED}/presentations",
            f"/api/v1/recommendation-presentations/presentation.{_DENIED}/promotions",
            f"/api/v1/recommendations/recommendation.{_DENIED}/review-readiness-assessments",
            f"/api/v1/recommendations/recommendation.{_DENIED}/human-review-requests",
            f"/api/v1/recommendations/recommendation.{_DENIED}/reviewer-assignments",
        )
        for path in paths:
            response = client.post(path, json={})
            assert response.status_code == 401, f"POST {path}: {response.text}"
            assert response.json()["code"] == "authentication_required", path


def test_recommendation_review_promotion_pipeline_wiring_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions is denied by the real
    ``AuthorizationService``, not a faked dependency override, for every one of the ten
    permissions (create + read) this module covers.

    FastAPI resolves each route's ``Depends(authorize_...)`` sub-dependency (which itself depends
    on ``browser_session_subject``) before parsing the request body, so an empty body deliberately
    proves the denial fires before any of these placeholder, intentionally-nonexistent path
    identifiers would ever reach real service logic.

    Note this denial is presently indistinguishable in status/code from what the FULLY privileged
    "atlas-demo" development identity also receives on these same ten routes -- see this module's
    docstring for the confirmed missing-``RoleAssignment`` gap that makes that true today. This
    test still independently proves the explicitly-zero-permission case is denied by the real
    authorization service.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        post_paths = (
            f"/api/v1/ai/recommendation-adjudications/adjudication.{_DENIED}/presentations",
            f"/api/v1/recommendation-presentations/presentation.{_DENIED}/promotions",
            f"/api/v1/recommendations/recommendation.{_DENIED}/review-readiness-assessments",
            f"/api/v1/recommendations/recommendation.{_DENIED}/human-review-requests",
            f"/api/v1/recommendations/recommendation.{_DENIED}/reviewer-assignments",
        )
        for path in post_paths:
            response = client.post(path, json={}, headers={"X-CSRF-Token": csrf})
            assert response.status_code == 403, f"POST {path}: {response.text}"
            assert response.json()["code"] == "authorization_denied", path

        get_paths = (
            f"/api/v1/ai/recommendation-adjudications/adjudication.{_DENIED}/"
            f"presentations/presentation.{_DENIED}",
            f"/api/v1/recommendation-presentations/presentation.{_DENIED}/"
            f"promotions/recommendation.{_DENIED}",
            f"/api/v1/recommendations/recommendation.{_DENIED}/"
            f"review-readiness-assessments/assessment.{_DENIED}",
            f"/api/v1/recommendations/recommendation.{_DENIED}/"
            f"human-review-requests/review-request.{_DENIED}",
            f"/api/v1/recommendations/recommendation.{_DENIED}/"
            f"reviewer-assignments/assignment-set.{_DENIED}",
        )
        for path in get_paths:
            response = client.get(path, headers={"X-CSRF-Token": csrf})
            assert response.status_code == 403, f"GET {path}: {response.text}"
            assert response.json()["code"] == "authorization_denied", path
