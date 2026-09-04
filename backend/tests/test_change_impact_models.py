from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.change_impact.domain.models import (
    ChangeCategory,
    ChangeParameter,
    ChangeRequest,
    ChangeStepSpec,
    is_ambiguous_or_materially_incomplete,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def step(**overrides: object) -> ChangeStepSpec:
    defaults: dict[str, object] = {
        "step_id": "change-step.example",
        "order": 1,
        "description": "Fail over controller B to controller A.",
        "connector_capability_id": "capability.controller.failover",
        "manual_procedure_reference": None,
        "capability_class": "C2",
    }
    defaults.update(overrides)
    return ChangeStepSpec(**defaults)  # type: ignore[arg-type]


def request(**overrides: object) -> ChangeRequest:
    defaults: dict[str, object] = {
        "request_id": "change-request.example",
        "proposed_change_version": 1,
        "purpose": "Apply a firmware update to controller B.",
        "expected_outcome": "Controller B runs the patched firmware with no data loss.",
        "change_category": ChangeCategory.SOFTWARE_FIRMWARE_DRIVER_OR_PATCH_UPDATE,
        "steps": (step(),),
        "target_ids": ("target.controller-b",),
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "site_id": "site.primary",
        "parameters": (),
        "proposed_start": NOW + timedelta(days=1),
        "maintenance_window_start": NOW + timedelta(days=1),
        "maintenance_window_end": NOW + timedelta(days=1, hours=2),
        "deadline": NOW + timedelta(days=2),
        "preconditions": ("Controller A is healthy.",),
        "success_criteria": ("Controller B rejoins the cluster.",),
        "stop_conditions": ("Controller A reports a fault during failover.",),
        "rollback_plan": "Fail back to controller B's prior firmware image.",
        "current_incident_or_change_reference": None,
        "allowed_data_classes": ("topology", "health"),
        "required_freshness_seconds": 300,
        "requested_scenario_kinds": ("expected", "failure"),
        "audience": "storage-operations",
    }
    defaults.update(overrides)
    return ChangeRequest(**defaults)  # type: ignore[arg-type]


def test_change_category_has_eleven_members() -> None:
    assert len(ChangeCategory) == 11


def test_step_requires_capability_or_manual_reference() -> None:
    with pytest.raises(ValueError, match="connector capability"):
        step(connector_capability_id=None, manual_procedure_reference=None)


def test_step_accepts_manual_reference_alone() -> None:
    manual_step = step(
        connector_capability_id=None,
        manual_procedure_reference="runbook.manual.controller-failover",
    )
    assert manual_step.manual_procedure_reference is not None


def test_parameter_requires_exactly_one_of_value_or_secret_reference() -> None:
    with pytest.raises(ValueError, match="exactly one of value"):
        ChangeParameter(
            name="timeout_seconds", value_type="integer", value="30", secret_reference="ref"
        )
    with pytest.raises(ValueError, match="exactly one of value"):
        ChangeParameter(
            name="timeout_seconds", value_type="integer", value=None, secret_reference=None
        )


def test_parameter_rejects_literal_secret_looking_value() -> None:
    with pytest.raises(ValueError, match="looks like a secret"):
        ChangeParameter(
            name="api_key",
            value_type="string",
            value="AKIAABCDEFGHIJKLMNOP",
            secret_reference=None,
        )


def test_parameter_accepts_secret_reference() -> None:
    parameter = ChangeParameter(
        name="api_key", value_type="string", value=None, secret_reference="secret.api-key"
    )
    assert parameter.secret_reference == "secret.api-key"


def test_change_request_requires_at_least_one_step() -> None:
    with pytest.raises(ValueError, match="at least one step"):
        request(steps=())


def test_change_request_requires_unique_increasing_step_order() -> None:
    with pytest.raises(ValueError, match="unique, strictly increasing"):
        request(steps=(step(order=1), step(step_id="change-step.other", order=1)))


def test_change_request_requires_timezone_aware_dates() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        request(deadline=datetime(2026, 9, 5, 0, 0))


def test_change_request_rejects_inverted_maintenance_window() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        request(
            maintenance_window_start=NOW + timedelta(hours=2),
            maintenance_window_end=NOW,
        )


def test_change_request_requires_success_criteria() -> None:
    with pytest.raises(ValueError, match="success criterion"):
        request(success_criteria=())


def test_is_ambiguous_or_materially_incomplete_true_without_rollback_plan() -> None:
    assert is_ambiguous_or_materially_incomplete(request(rollback_plan=None)) is True


def test_is_ambiguous_or_materially_incomplete_true_without_stop_conditions() -> None:
    assert is_ambiguous_or_materially_incomplete(request(stop_conditions=())) is True


def test_is_ambiguous_or_materially_incomplete_false_for_complete_request() -> None:
    assert is_ambiguous_or_materially_incomplete(request()) is False
