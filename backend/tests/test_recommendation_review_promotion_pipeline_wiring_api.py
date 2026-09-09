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
sequence to reach one real adjudication, then continues into this pass's own five routes.

That attempt originally surfaced a genuine, confirmed authorization-wiring gap: none of the five
scope-builder functions these routes' ``authorize_*`` dependencies and permission-authorizer
adapters call -- ``ai_protected_recommendation_presentation_scope``,
``recommendation_promotion_scope``, ``recommendation_readiness_scope``,
``recommendation_review_request_scope``, and ``recommendation_reviewer_assignment_scope``, all
defined in ``atlas/modules/authorization/application/bootstrap.py`` -- was ever invoked by any
``RoleAssignment`` in that file. ``AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE/READ``,
``RECOMMENDATION_PROMOTION_CREATE/READ``, ``RECOMMENDATION_READINESS_CREATE/READ``,
``RECOMMENDATION_REVIEW_REQUEST_CREATE/READ``, and
``RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE/READ`` were all defined as permissions and were all
included in ``DEVELOPMENT_ROLE_ID``'s permission set -- but with no ``RoleAssignment`` binding any
of them to a scope, ``AuthorizationService.evaluate`` (which requires an *active, scope-matching*
assignment, not merely a role that lists the permission) could never return ``allowed`` for any of
these ten permissions, for any identity, including the "atlas-demo" development identity every
other wiring test in this repo relies on. A fully logged-in, fully-privileged development identity
received a real ``403 authorization_denied`` on every one of these ten routes, identical to what an
explicitly zero-permission identity receives.

**This bug is now fixed.** ``build_development_authorization_service()`` in
``atlas/modules/authorization/application/bootstrap.py`` now includes 24 additional
``RoleAssignment`` entries (12 create/read permission pairs, including the ten this module covers)
binding ``DEVELOPMENT_ROLE_ID`` to the matching scope for each of these permissions -- see the
``RoleAssignment`` block starting at
``assignment.development.ai-protected-recommendation-presentation-create``. Every test below now
drives its stage's route with a fully valid, schema-passing request built from real upstream data
(the first stage from a real upstream adjudication obtained by driving the real
protected-adjudication chain over HTTP; every later stage from the real, HTTP-created output of the
stage directly before it) and asserts the real ``2xx`` success this produces, with meaningful
response fields -- proving genuine end-to-end reachability through the real, wired
``AuthorizationService``, not merely that a denial is reached. The two tests at the bottom of this
module (authentication/permission boundary checks, unaffected by this fix) are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    this module's own presentation-create test below.
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


@dataclass(frozen=True)
class _RealPresentationOutcome:
    """The fields this module needs to attempt a real, schema-valid recommendation promotion
    create -- obtained from a real HTTP-created protected recommendation presentation."""

    presentation_id: str
    presentation_digest: str
    purpose: str


def _build_real_presentation_via_http(
    app: FastAPI, client: TestClient, csrf: str
) -> _RealPresentationOutcome:
    """Drives ``_build_real_adjudication_via_http`` and then creates one real protected
    recommendation presentation over HTTP, the same way
    ``test_protected_recommendation_presentation_route_is_wired_to_real_authorization`` below
    proves that route -- reused by every later stage's own builder."""
    adjudication = _build_real_adjudication_via_http(app, client, csrf)
    settings = _settings()
    presentation_policy = build_development_protected_recommendation_presentation_policy(
        organization_id=settings.development_organization_id,
        environment_id=f"environment.{settings.environment}",
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    response = client.post(
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
    assert response.status_code == 201, response.text
    presentation = response.json()["data"]["presentation"]
    return _RealPresentationOutcome(
        presentation_id=presentation["presentation_id"],
        presentation_digest=presentation["canonical_digest"],
        purpose=presentation["purpose"],
    )


@dataclass(frozen=True)
class _RealPromotionOutcome:
    """The fields this module needs to attempt a real, schema-valid recommendation
    review-readiness create -- obtained from a real HTTP-created recommendation promotion."""

    recommendation_id: str
    recommendation_digest: str
    purpose: str


def _build_real_promotion_via_http(
    app: FastAPI, client: TestClient, csrf: str
) -> _RealPromotionOutcome:
    """Drives ``_build_real_presentation_via_http`` and then creates one real recommendation
    promotion over HTTP, the same way
    ``test_recommendation_promotion_route_is_wired_to_real_authorization`` below proves that
    route -- reused by every later stage's own builder."""
    presentation = _build_real_presentation_via_http(app, client, csrf)
    settings = _settings()
    promotion_policy = build_development_recommendation_promotion_policy(
        organization_id=settings.development_organization_id,
        environment_id=f"environment.{settings.environment}",
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    response = client.post(
        f"/api/v1/recommendation-presentations/{presentation.presentation_id}/promotions",
        json={
            "presentation_digest": presentation.presentation_digest,
            "promotion_policy_id": promotion_policy.policy_id,
            "promotion_policy_digest": promotion_policy.canonical_digest,
            "purpose": presentation.purpose,
            "acknowledged_draft_only": True,
            "acknowledged_no_review_or_approval": True,
            "acknowledged_no_operational_authority": True,
        },
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "review-promo-pipeline-promotion-0001",
        },
    )
    assert response.status_code == 201, response.text
    recommendation = response.json()["data"]["recommendation"]
    return _RealPromotionOutcome(
        recommendation_id=recommendation["recommendation_id"],
        recommendation_digest=recommendation["canonical_digest"],
        purpose=recommendation["purpose"],
    )


@dataclass(frozen=True)
class _RealReadinessOutcome:
    """The fields this module needs to attempt a real, schema-valid recommendation human-review
    request create -- obtained from a real HTTP-created recommendation review-readiness
    assessment."""

    recommendation_id: str
    recommendation_digest: str
    assessment_id: str
    assessment_digest: str
    purpose: str


def _build_real_readiness_via_http(
    app: FastAPI, client: TestClient, csrf: str
) -> _RealReadinessOutcome:
    """Drives ``_build_real_promotion_via_http`` and then creates one real recommendation
    review-readiness assessment over HTTP, the same way
    ``test_recommendation_readiness_route_is_wired_to_real_authorization`` below proves that
    route -- reused by every later stage's own builder."""
    promotion = _build_real_promotion_via_http(app, client, csrf)
    settings = _settings()
    readiness_policy = build_development_recommendation_readiness_policy(
        organization_id=settings.development_organization_id,
        environment_id=f"environment.{settings.environment}",
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    response = client.post(
        f"/api/v1/recommendations/{promotion.recommendation_id}/review-readiness-assessments",
        json={
            "recommendation_digest": promotion.recommendation_digest,
            "readiness_policy_id": readiness_policy.policy_id,
            "readiness_policy_digest": readiness_policy.canonical_digest,
            "purpose": promotion.purpose,
            "acknowledged_readiness_is_not_review": True,
            "acknowledged_blocked_requires_new_version": True,
            "acknowledged_no_operational_authority": True,
        },
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "review-promo-pipeline-readiness-0001",
        },
    )
    assert response.status_code == 201, response.text
    assessment = response.json()["data"]["assessment"]
    return _RealReadinessOutcome(
        recommendation_id=promotion.recommendation_id,
        recommendation_digest=promotion.recommendation_digest,
        assessment_id=assessment["assessment_id"],
        assessment_digest=assessment["canonical_digest"],
        purpose=assessment["purpose"],
    )


@dataclass(frozen=True)
class _RealReviewRequestOutcome:
    """The fields this module needs to attempt a real, schema-valid recommendation reviewer
    assignment create -- obtained from a real HTTP-created recommendation human-review
    request."""

    recommendation_id: str
    review_request_id: str
    review_request_digest: str
    purpose: str


def _build_real_review_request_via_http(
    app: FastAPI, client: TestClient, csrf: str
) -> _RealReviewRequestOutcome:
    """Drives ``_build_real_readiness_via_http`` and then creates one real recommendation
    human-review request over HTTP, the same way
    ``test_recommendation_review_request_route_is_wired_to_real_authorization`` below proves that
    route -- reused by
    ``test_recommendation_reviewer_assignment_route_is_wired_to_real_authorization`` below."""
    readiness = _build_real_readiness_via_http(app, client, csrf)
    settings = _settings()
    review_request_policy = build_development_recommendation_review_request_policy(
        organization_id=settings.development_organization_id,
        environment_id=f"environment.{settings.environment}",
        issued_at=POLICY_ISSUED_AT,
        expires_at=POLICY_EXPIRES_AT,
    )
    response = client.post(
        f"/api/v1/recommendations/{readiness.recommendation_id}/human-review-requests",
        json={
            "recommendation_digest": readiness.recommendation_digest,
            "readiness_assessment_id": readiness.assessment_id,
            "readiness_assessment_digest": readiness.assessment_digest,
            "review_request_policy_id": review_request_policy.policy_id,
            "review_request_policy_digest": review_request_policy.canonical_digest,
            "purpose": readiness.purpose,
            "acknowledged_request_is_not_assignment_or_review": True,
            "acknowledged_routing_is_policy_owned": True,
            "acknowledged_no_approval_or_operational_authority": True,
        },
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "review-promo-pipeline-review-request-0001",
        },
    )
    assert response.status_code == 201, response.text
    request_record = response.json()["data"]["request"]
    return _RealReviewRequestOutcome(
        recommendation_id=readiness.recommendation_id,
        review_request_id=request_record["review_request_id"],
        review_request_digest=request_record["canonical_digest"],
        purpose=request_record["purpose"],
    )


def test_protected_recommendation_presentation_route_is_wired_to_real_authorization() -> None:
    """``protected_recommendation_presentations.py``'s create and read routes are registered,
    require a real authenticated session, and reach the real
    ``authorize_protected_recommendation_presentation_create``/``_read`` dependencies against
    ``app.state.authorization_service`` -- confirmed here with a fully valid, schema-passing
    request built from a REAL upstream adjudication (obtained by driving the real
    protected-adjudication chain over HTTP), now genuinely creating and reading back a real
    protected recommendation presentation now that the missing ``RoleAssignment`` documented in
    this module's docstring has been fixed.
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
        assert created.status_code == 201, created.text
        presentation = created.json()["data"]["presentation"]
        assert presentation["adjudication_id"] == adjudication.adjudication_id
        assert presentation["purpose"] == adjudication.purpose
        assert presentation["recommendation_presented"] is True
        assert presentation["recommendation_ready_for_review"] is False
        assert presentation["recommendation_approved"] is False
        assert presentation["workflow_created"] is False
        assert presentation["infrastructure_mutated"] is False
        assert presentation["option_count"] == 3
        assert presentation["preferred_count"] == 1
        assert created.json()["data"]["recommendation"]["outcome"] == "preferred"

        fetched = client.get(
            f"/api/v1/ai/recommendation-adjudications/{adjudication.adjudication_id}/"
            f"presentations/{presentation['presentation_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert (
            fetched.json()["data"]["presentation"]["presentation_id"]
            == presentation["presentation_id"]
        )


def test_recommendation_promotion_route_is_wired_to_real_authorization() -> None:
    """``recommendation_promotions.py``'s create and read routes are registered, require a real
    authenticated session, and reach the real ``authorize_recommendation_promotion_create``/
    ``_read`` dependencies -- confirmed with a fully valid, schema-passing request built from a
    real, HTTP-created protected recommendation presentation, now genuinely creating and reading
    back a real draft recommendation now that the missing ``RoleAssignment`` documented in this
    module's docstring has been fixed.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        presentation = _build_real_presentation_via_http(app, client, csrf)
        settings = _settings()
        policy = build_development_recommendation_promotion_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendation-presentations/{presentation.presentation_id}/promotions",
            json={
                "presentation_digest": presentation.presentation_digest,
                "promotion_policy_id": policy.policy_id,
                "promotion_policy_digest": policy.canonical_digest,
                "purpose": presentation.purpose,
                "acknowledged_draft_only": True,
                "acknowledged_no_review_or_approval": True,
                "acknowledged_no_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-promotion-0001",
            },
        )
        assert created.status_code == 201, created.text
        recommendation = created.json()["data"]["recommendation"]
        assert recommendation["presentation_id"] == presentation.presentation_id
        assert recommendation["purpose"] == presentation.purpose
        assert recommendation["state"] == "draft"
        assert recommendation["outcome"] == "preferred"
        assert recommendation["recommendation_promoted"] is True
        assert recommendation["recommendation_ready_for_review"] is False
        assert recommendation["human_review_completed"] is False
        assert recommendation["infrastructure_mutated"] is False

        fetched = client.get(
            f"/api/v1/recommendation-presentations/{presentation.presentation_id}/"
            f"promotions/{recommendation['recommendation_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert (
            fetched.json()["data"]["recommendation"]["recommendation_id"]
            == recommendation["recommendation_id"]
        )


def test_recommendation_readiness_route_is_wired_to_real_authorization() -> None:
    """``recommendation_readiness.py``'s create and read routes are registered, require a real
    authenticated session, and reach the real ``authorize_recommendation_readiness_create``/
    ``_read`` dependencies -- confirmed with a fully valid, schema-passing request built from a
    real, HTTP-created recommendation promotion, now genuinely creating and reading back a real
    review-readiness assessment now that the missing ``RoleAssignment`` documented in this
    module's docstring has been fixed.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        promotion = _build_real_promotion_via_http(app, client, csrf)
        settings = _settings()
        policy = build_development_recommendation_readiness_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendations/{promotion.recommendation_id}/review-readiness-assessments",
            json={
                "recommendation_digest": promotion.recommendation_digest,
                "readiness_policy_id": policy.policy_id,
                "readiness_policy_digest": policy.canonical_digest,
                "purpose": promotion.purpose,
                "acknowledged_readiness_is_not_review": True,
                "acknowledged_blocked_requires_new_version": True,
                "acknowledged_no_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-readiness-0001",
            },
        )
        assert created.status_code == 201, created.text
        assessment = created.json()["data"]["assessment"]
        assert assessment["recommendation_id"] == promotion.recommendation_id
        assert assessment["purpose"] == promotion.purpose
        assert assessment["evaluation_outcome"] == "ready"
        assert assessment["state"] == "ready_for_review"
        assert assessment["recommendation_ready_for_review"] is True
        assert assessment["passed_check_count"] == assessment["check_count"]
        assert assessment["human_review_completed"] is False
        assert assessment["infrastructure_mutated"] is False

        fetched = client.get(
            f"/api/v1/recommendations/{promotion.recommendation_id}/"
            f"review-readiness-assessments/{assessment['assessment_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["data"]["assessment"]["assessment_id"] == assessment["assessment_id"]


def test_recommendation_review_request_route_is_wired_to_real_authorization() -> None:
    """``recommendation_review_requests.py``'s create and read routes are registered, require a
    real authenticated session, and reach the real
    ``authorize_recommendation_review_request_create``/``_read`` dependencies -- confirmed with a
    fully valid, schema-passing request built from a real, HTTP-created review-readiness
    assessment, now genuinely creating and reading back a real human-review request now that the
    missing ``RoleAssignment`` documented in this module's docstring has been fixed.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        readiness = _build_real_readiness_via_http(app, client, csrf)
        settings = _settings()
        policy = build_development_recommendation_review_request_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendations/{readiness.recommendation_id}/human-review-requests",
            json={
                "recommendation_digest": readiness.recommendation_digest,
                "readiness_assessment_id": readiness.assessment_id,
                "readiness_assessment_digest": readiness.assessment_digest,
                "review_request_policy_id": policy.policy_id,
                "review_request_policy_digest": policy.canonical_digest,
                "purpose": readiness.purpose,
                "acknowledged_request_is_not_assignment_or_review": True,
                "acknowledged_routing_is_policy_owned": True,
                "acknowledged_no_approval_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-review-request-0001",
            },
        )
        assert created.status_code == 201, created.text
        request_record = created.json()["data"]["request"]
        assert request_record["recommendation_id"] == readiness.recommendation_id
        assert request_record["readiness_assessment_id"] == readiness.assessment_id
        assert request_record["purpose"] == readiness.purpose
        assert request_record["state"] == "review_requested"
        assert request_record["review_requested"] is True
        assert request_record["reviewer_assigned"] is False
        assert request_record["track_codes"] == [
            "review-track.technical",
            "review-track.service-impact",
        ]
        assert request_record["infrastructure_mutated"] is False

        fetched = client.get(
            f"/api/v1/recommendations/{readiness.recommendation_id}/"
            f"human-review-requests/{request_record['review_request_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert (
            fetched.json()["data"]["request"]["review_request_id"]
            == request_record["review_request_id"]
        )


def test_recommendation_reviewer_assignment_route_is_wired_to_real_authorization() -> None:
    """``recommendation_reviewer_assignments.py``'s create and read routes are registered,
    require a real authenticated session, and reach the real
    ``authorize_recommendation_reviewer_assignment_create``/``_read`` dependencies -- confirmed
    with a fully valid, schema-passing request built from a real, HTTP-created human-review
    request, now genuinely creating and reading back a real reviewer assignment now that the
    missing ``RoleAssignment`` documented in this module's docstring has been fixed.
    """
    app = create_app(_settings())
    with TestClient(app) as client:
        csrf = _login(client)
        review_request = _build_real_review_request_via_http(app, client, csrf)
        settings = _settings()
        policy = build_development_recommendation_reviewer_assignment_policy(
            organization_id=settings.development_organization_id,
            environment_id=f"environment.{settings.environment}",
            issued_at=POLICY_ISSUED_AT,
            expires_at=POLICY_EXPIRES_AT,
        )

        created = client.post(
            f"/api/v1/recommendations/{review_request.recommendation_id}/reviewer-assignments",
            json={
                "review_request_id": review_request.review_request_id,
                "review_request_digest": review_request.review_request_digest,
                "assignment_policy_id": policy.policy_id,
                "assignment_policy_digest": policy.canonical_digest,
                "purpose": review_request.purpose,
                "acknowledged_caller_cannot_select_reviewers": True,
                "acknowledged_distinct_reviewers_required": True,
                "acknowledged_no_inspection_decision_or_operational_authority": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "review-promo-pipeline-reviewer-assignment-0001",
            },
        )
        assert created.status_code == 201, created.text
        assignment = created.json()["data"]["assignment"]
        assert assignment["recommendation_id"] == review_request.recommendation_id
        assert assignment["review_request_id"] == review_request.review_request_id
        assert assignment["purpose"] == review_request.purpose
        assert assignment["state"] == "reviewers_assigned"
        assert assignment["review_requested"] is True
        assert assignment["reviewer_assigned"] is True
        assert assignment["content_inspection_opened"] is False
        assert len(assignment["track_assignments"]) == 2
        assigned_reviewers = {track[3] for track in assignment["track_assignments"]}
        assert len(assigned_reviewers) == 2, "reviewers across tracks must be distinct"

        fetched = client.get(
            f"/api/v1/recommendations/{review_request.recommendation_id}/"
            f"reviewer-assignments/{assignment['assignment_set_id']}",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200, fetched.text
        assert (
            fetched.json()["data"]["assignment"]["assignment_set_id"]
            == assignment["assignment_set_id"]
        )


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
