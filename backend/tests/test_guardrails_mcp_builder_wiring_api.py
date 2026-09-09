"""Pass 12 found that GuardrailReviewService, SecurityIncidentService (both
atlas.modules.guardrails, built with 16 non-overridable invariants) and BuilderDraftService
(atlas.modules.mcp_builder) were real, tested at the service layer, but reachable through no
route anywhere. Guardrails in particular had zero API surface at all before this pass. These
tests exercise each one through the real HTTP API, not just the service layer directly, to prove
the wiring genuinely closes that gap.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings


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


def test_guardrails_require_authentication() -> None:
    """No session cookie and no development identity: both guardrail route groups (human review
    and security incidents) must fail closed at authentication, not merely at authorization --
    proving `authenticated_subject` really runs on each.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        enqueue_response = client.post(
            "/api/v1/guardrails/human-review/entries/entry.wiring-denied-0001",
            json={
                "triggered_rule_id": "rule.wiring-denied-0001",
                "safe_rationale": "Synthetic wiring-test rationale for a human reviewer.",
                "request_reference": "req.wiring-denied-0001",
                "bounded_context_reference": "context.wiring-denied-0001",
                "detected_elements": [
                    {
                        "kind": "secret",
                        "description": "A redacted synthetic value.",
                        "redacted": True,
                    }
                ],
                "proposed_disposition": "Hold pending review.",
                "proposed_impact": "No production impact expected.",
                "related_policy_reference": None,
                "related_approval_reference": None,
                "related_connector_reference": None,
                "related_audit_reference": "audit.wiring-denied-0001",
                "allowed_decisions": ["uphold", "overturn", "escalate"],
            },
        )
        open_response = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-denied-0001",
            json={
                "trigger": "suspected_exfiltration",
                "affected_references": ["asset.wiring-denied-0001"],
            },
        )

    for response in (enqueue_response, open_response):
        assert response.status_code == 401
        assert response.json()["code"] == "authentication_required"


def test_guardrails_require_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService` at each of the six guardrail permission checks (human
    review enqueue/resolve and security incident open/contain/recover/close), not by a faked
    dependency override.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        headers = {"X-CSRF-Token": csrf}

        enqueued = client.post(
            "/api/v1/guardrails/human-review/entries/entry.wiring-denied-0001",
            json={
                "triggered_rule_id": "rule.wiring-denied-0001",
                "safe_rationale": "Synthetic wiring-test rationale for a human reviewer.",
                "request_reference": "req.wiring-denied-0001",
                "bounded_context_reference": "context.wiring-denied-0001",
                "detected_elements": [
                    {
                        "kind": "secret",
                        "description": "A redacted synthetic value.",
                        "redacted": True,
                    }
                ],
                "proposed_disposition": "Hold pending review.",
                "proposed_impact": "No production impact expected.",
                "related_policy_reference": None,
                "related_approval_reference": None,
                "related_connector_reference": None,
                "related_audit_reference": "audit.wiring-denied-0001",
                "allowed_decisions": ["uphold", "overturn", "escalate"],
            },
            headers=headers,
        )
        resolved = client.post(
            "/api/v1/guardrails/human-review/entries/entry.wiring-denied-0001/resolutions",
            json={
                "decision": "uphold",
                "rationale": "Confirmed correct per policy on re-review.",
                "triggering_guardrail_class": "policy_configurable",
            },
            headers=headers,
        )
        opened = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-denied-0001",
            json={
                "trigger": "suspected_exfiltration",
                "affected_references": ["asset.wiring-denied-0001"],
            },
            headers=headers,
        )
        contained = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-denied-0001/containment",
            json={"alert_reference": "alert.wiring-denied-0001"},
            headers=headers,
        )
        recovered = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-denied-0001/recovery",
            json={
                "credentials_revoked": True,
                "scope_assessment": "Limited to one lab host; no lateral movement observed.",
                "improvement_reference": "improvement.wiring-denied-0001",
            },
            headers=headers,
        )
        closed = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-denied-0001/closure",
            headers=headers,
        )

    for response in (enqueued, resolved, opened, contained, recovered, closed):
        assert response.status_code == 403
        assert response.json()["code"] == "authorization_denied"


def test_guardrail_human_review_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        enqueued = client.post(
            "/api/v1/guardrails/human-review/entries/entry.wiring-test-0001",
            json={
                "triggered_rule_id": "rule.wiring-test-0001",
                "safe_rationale": "Synthetic wiring-test rationale for a human reviewer.",
                "request_reference": "req.wiring-test-0001",
                "bounded_context_reference": "context.wiring-test-0001",
                "detected_elements": [
                    {
                        "kind": "secret",
                        "description": "A redacted synthetic value.",
                        "redacted": True,
                    }
                ],
                "proposed_disposition": "Hold pending review.",
                "proposed_impact": "No production impact expected.",
                "related_policy_reference": None,
                "related_approval_reference": None,
                "related_connector_reference": None,
                "related_audit_reference": "audit.wiring-test-0001",
                "allowed_decisions": ["uphold", "overturn", "escalate"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert enqueued.status_code == 201
        entry = enqueued.json()["data"]
        assert entry["entry_id"] == "entry.wiring-test-0001"
        assert entry["detected_elements"][0]["redacted"] is True

        resolved = client.post(
            "/api/v1/guardrails/human-review/entries/entry.wiring-test-0001/resolutions",
            json={
                "decision": "uphold",
                "rationale": "Confirmed correct per policy on re-review.",
                "triggering_guardrail_class": "policy_configurable",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resolved.status_code == 201
        resolution = resolved.json()["data"]
        assert resolution["decision"] == "uphold"
        assert resolution["entry_id"] == "entry.wiring-test-0001"

        # A second resolution of the same entry must be refused (already resolved).
        duplicate = client.post(
            "/api/v1/guardrails/human-review/entries/entry.wiring-test-0001/resolutions",
            json={
                "decision": "uphold",
                "rationale": "Attempting to resolve twice.",
                "triggering_guardrail_class": "policy_configurable",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert duplicate.status_code == 409


def test_guardrail_security_incident_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        opened = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-test-0001",
            json={
                "trigger": "suspected_exfiltration",
                "affected_references": ["asset.wiring-test-0001"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert opened.status_code == 201
        assert opened.json()["data"]["trigger"] == "suspected_exfiltration"

        contained = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-test-0001/containment",
            json={"alert_reference": "alert.wiring-test-0001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert contained.status_code == 200
        assert contained.json()["data"]["evidence_preserved"] is True

        recovered = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-test-0001/recovery",
            json={
                "credentials_revoked": True,
                "scope_assessment": "Limited to one lab host; no lateral movement observed.",
                "improvement_reference": "improvement.wiring-test-0001",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert recovered.status_code == 200
        assert recovered.json()["data"]["credentials_revoked"] is True

        closed = client.post(
            "/api/v1/guardrails/security-incidents/incident.wiring-test-0001/closure",
            headers={"X-CSRF-Token": csrf},
        )
        assert closed.status_code == 200
        closed_data = closed.json()["data"]
        assert closed_data["closed_by"] is not None
        assert closed_data["closer_kind"] == "human"


def test_mcp_builder_draft_and_supersession_are_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        created = client.post(
            "/api/v1/mcp-builder/drafts/draft.wiring-test-0001",
            json={
                "vendor": "Acme Storage",
                "product": "Widget Array",
                "target_environment": "lab",
                "notes": "Assembling sources for a new Builder project.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert created.status_code == 201
        draft = created.json()["data"]
        assert draft["draft_id"] == "draft.wiring-test-0001"
        assert draft["analyzed_project_id"] is None

        analyzed = client.post(
            "/api/v1/mcp-builder/drafts/draft.wiring-test-0001/analysis",
            json={"analyzed_project_id": "project.wiring-test-0001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert analyzed.status_code == 200
        assert analyzed.json()["data"]["analyzed_project_id"] == "project.wiring-test-0001"

        # A second analysis of the same draft must be refused (already analyzed).
        duplicate = client.post(
            "/api/v1/mcp-builder/drafts/draft.wiring-test-0001/analysis",
            json={"analyzed_project_id": "project.wiring-test-0002"},
            headers={"X-CSRF-Token": csrf},
        )
        assert duplicate.status_code == 409

        superseded = client.post(
            "/api/v1/mcp-builder/supersessions/supersession.wiring-test-0001",
            json={
                "superseded_project_id": "project.wiring-test-old",
                "superseding_project_id": "project.wiring-test-0001",
                "reason": "A newer analyzed Builder project version replaces the older one.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert superseded.status_code == 201
        supersession = superseded.json()["data"]
        assert supersession["superseding_project_id"] == "project.wiring-test-0001"
