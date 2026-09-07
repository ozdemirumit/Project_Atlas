from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.release.domain.deprecation_suspension_exceptions import (
    DeprecationNotice,
    EmergencyRetirement,
    ReleaseException,
    SuspensionEvent,
    SuspensionResponseAction,
    SuspensionTrigger,
    removal_skips_compatibility_and_release_review,
    security_is_preserved_only_until_stated_support_end,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def deprecation_notice(**overrides: object) -> DeprecationNotice:
    defaults: dict[str, object] = {
        "affected_item_reference": "api.v1.legacy-endpoint",
        "reason": "Superseded by v2 endpoint with structured errors.",
        "replacement": "api.v2.endpoint",
        "migration_guidance": "Switch to /v2/endpoint; see migration guide.",
        "first_warning_date": NOW,
        "removal_or_support_end_date": NOW + timedelta(days=180),
        "usage_monitoring_reference": "usage-monitor.legacy-endpoint",
        "offline_notice_reference": "offline-notice.legacy-endpoint",
    }
    defaults.update(overrides)
    return DeprecationNotice(**defaults)  # type: ignore[arg-type]


def test_deprecation_notice_accepts_valid_state() -> None:
    assert deprecation_notice().reason.startswith("Superseded")


def test_deprecation_notice_rejects_removal_before_first_warning() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        deprecation_notice(removal_or_support_end_date=NOW - timedelta(days=1))


def test_deprecation_notice_requires_offline_notice_reference() -> None:
    with pytest.raises(ValueError, match="release bundles and support channels"):
        deprecation_notice(offline_notice_reference="")


def test_security_always_preserved_until_stated_support_end() -> None:
    assert security_is_preserved_only_until_stated_support_end() is True


def test_removal_never_skips_compatibility_and_release_review() -> None:
    assert removal_skips_compatibility_and_release_review() is False


def test_emergency_retirement_requires_mitigation() -> None:
    with pytest.raises(ValueError, match="clear mitigation"):
        EmergencyRetirement(
            affected_item_reference="connector.legacy-vendor",
            active_security_risk_reference="cve.2026-12345",
            mitigation="",
        )


def suspension_event(**overrides: object) -> SuspensionEvent:
    defaults: dict[str, object] = {
        "release_reference": "release.1.5.0",
        "trigger": SuspensionTrigger.SIGNATURE_OR_PROVENANCE_COMPROMISE,
        "response_actions": (SuspensionResponseAction.SUSPEND_PUBLICATION,),
        "evidence_reference": "evidence.suspension.1.5.0",
        "incident_governance_reference": "incident.suspension.1.5.0",
    }
    defaults.update(overrides)
    return SuspensionEvent(**defaults)  # type: ignore[arg-type]


def test_suspension_event_requires_response_actions() -> None:
    with pytest.raises(ValueError, match="at least one response action"):
        suspension_event(response_actions=())


def test_suspension_event_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence is preserved"):
        suspension_event(evidence_reference="")


def test_suspension_event_accepts_valid_state() -> None:
    assert suspension_event().trigger is SuspensionTrigger.SIGNATURE_OR_PROVENANCE_COMPROMISE


def release_exception(**overrides: object) -> ReleaseException:
    defaults: dict[str, object] = {
        "exception_id": "release-exception.1.5.0-001",
        "affected_version": "1.5.0",
        "affected_profile": "linux_lab",
        "affected_component": "connector.example.storage",
        "scenario": "Intermittent timeout under high load.",
        "severity": "moderate",
        "realistic_impact": "Occasional retry required for inventory reads.",
        "detection": "Elevated timeout metric on capability.inventory.read.",
        "workaround": "Increase client-side retry count.",
        "implications": ("service",),
        "owner": "subject.platform-owner",
        "fix_target": "release.1.5.1",
        "expiry": NOW + timedelta(days=30),
        "blocks_deployment_or_feature_enablement": False,
        "customer_communication_reference": "known-issues.1.5.0",
        "acceptance_authority": "subject.release-manager",
        "is_atlas_003_or_047_invariant": False,
    }
    defaults.update(overrides)
    return ReleaseException(**defaults)  # type: ignore[arg-type]


def test_release_exception_accepts_valid_state() -> None:
    assert release_exception().severity == "moderate"


def test_release_exception_rejects_atlas_003_or_047_invariant() -> None:
    with pytest.raises(ValueError, match="cannot be accepted as ordinary release exceptions"):
        release_exception(is_atlas_003_or_047_invariant=True)


def test_release_exception_requires_timezone_aware_expiry() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        release_exception(expiry=datetime(2026, 10, 4, 12, 0))
