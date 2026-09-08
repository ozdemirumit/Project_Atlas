"""ATLAS pass-17: `ConnectorUpgradeItsmChangeEvidence`/`ConnectorUpgradeMaintenanceWindowEvidence`
(`connectors/domain/upgrade_approval.py`) validated the vendor ITSM system's own record id and
version tokens (`external_record_id`, `external_record_version`, `window_version`) as strict
Atlas identifiers via `validate_stable_identifier` -- the same recurring bug class found five
times earlier this session (ITSM dispatch, idempotency/conflict, records, CMDB reconciliation).
This vertical was confirmed dormant (no route or application code ever constructs these objects
with real data today), so this is a standalone construction-level regression test, not an
end-to-end HTTP wiring test."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeItsmChangeEvidence,
    ConnectorUpgradeMaintenanceWindowEvidence,
)

NOW = datetime.now(UTC)
_DIGEST = "a" * 64


def test_itsm_change_evidence_accepts_a_real_vendor_record_id_and_version() -> None:
    evidence = ConnectorUpgradeItsmChangeEvidence(
        evidence_id="connector-upgrade-itsm-change-evidence.wiring-test",
        schema_version="atlas.connector-upgrade-itsm-change-evidence.v1",
        organization_id="organization.development",
        environment_id="environment.test",
        request_id="connector-upgrade-request.wiring-test",
        request_digest=_DIGEST,
        revalidation_id="connector-upgrade-revalidation.wiring-test",
        revalidation_digest=_DIGEST,
        plan_id="connector-upgrade-plan.wiring-test",
        plan_digest=_DIGEST,
        adapter_id="itsm-adapter.wiring-test",
        adapter_version="version.1.0.0",
        authoritative_instance_id="itsm-instance.wiring-test",
        # a real ServiceNow-style change record id and a numeric concurrency token -- exactly
        # the shape that used to crash validate_stable_identifier.
        external_record_id="CHG0010001",
        external_record_version="42",
        observed_at=NOW,
        valid_until=NOW + timedelta(minutes=8),
        canonical_digest=_DIGEST,
        adapter_validated=True,
        authoritative_source=True,
        record_accessible=True,
        source_version_current=True,
        exact_plan_binding_verified=True,
        record_active=True,
        conflict_free=True,
        revocation_absent=True,
    )
    assert evidence.external_record_id == "CHG0010001"
    assert evidence.external_record_version == "42"


def test_maintenance_window_evidence_accepts_a_real_vendor_version_token() -> None:
    evidence = ConnectorUpgradeMaintenanceWindowEvidence(
        evidence_id="connector-upgrade-maintenance-window-evidence.wiring-test",
        schema_version="atlas.connector-upgrade-maintenance-window-evidence.v1",
        organization_id="organization.development",
        environment_id="environment.test",
        request_id="connector-upgrade-request.wiring-test",
        request_digest=_DIGEST,
        revalidation_id="connector-upgrade-revalidation.wiring-test",
        revalidation_digest=_DIGEST,
        plan_id="connector-upgrade-plan.wiring-test",
        plan_digest=_DIGEST,
        itsm_change_evidence_id="connector-upgrade-itsm-change-evidence.wiring-test",
        itsm_change_evidence_digest=_DIGEST,
        # a numeric vendor concurrency token and a numeric window revision -- both previously
        # crash-prone.
        external_record_version="42",
        window_version="3",
        approved_start=NOW,
        approved_end=NOW + timedelta(hours=2),
        observed_at=NOW,
        valid_until=NOW + timedelta(minutes=8),
        canonical_digest=_DIGEST,
        authoritative_source=True,
        window_approved=True,
        source_version_current=True,
        exact_change_binding_verified=True,
        exact_plan_binding_verified=True,
        inside_approved_window=True,
        freeze_clear=True,
        conflict_free=True,
        revocation_absent=True,
    )
    assert evidence.external_record_version == "42"
    assert evidence.window_version == "3"
