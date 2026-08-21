import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.platform.domain.advisory_posture import (
    AdvisoryOnlyBoundaryViolation,
    assert_advisory_only_component_registry,
    assert_advisory_only_composition,
    build_advisory_only_posture,
)


def test_advisory_only_posture_disables_every_operational_authority() -> None:
    posture = build_advisory_only_posture()

    assert posture.platform_mode == "advisory_only"
    assert posture.operational_execution_enabled is False
    assert posture.process_resume_consumption_enabled is False
    assert posture.dispatch_enabled is False
    assert posture.infrastructure_mutation_enabled is False
    assert posture.ai_execution_authorized is False
    assert posture.contract_digest == (
        "edfde9fc024bab918b587740e23d96e95f8dc3329e8e34f28897dad590c212c1"
    )


@pytest.mark.parametrize(
    "key",
    (
        "ATLAS_OPERATIONAL_EXECUTION_ENABLED",
        "ATLAS_PROCESS_RESUME_CONSUMPTION_ENABLED",
        "ATLAS_WORKFLOW_DISPATCH_ENABLED",
        "ATLAS_INFRASTRUCTURE_MUTATION_ENABLED",
    ),
)
def test_operational_enablement_environment_flags_fail_closed(key: str) -> None:
    with pytest.raises(AdvisoryOnlyBoundaryViolation):
        assert_advisory_only_composition(environment={key: "true"})


def test_unknown_operational_enablement_value_fails_closed() -> None:
    with pytest.raises(AdvisoryOnlyBoundaryViolation):
        assert_advisory_only_composition(
            environment={"ATLAS_OPERATIONAL_EXECUTION_ENABLED": "unexpected"}
        )


def test_actual_operational_component_registration_prevents_application_startup() -> None:
    app = create_app(Settings(environment="test"))
    app.state.protected_runtime_process_resumer_service = object()

    with pytest.raises(AdvisoryOnlyBoundaryViolation), TestClient(app):
        pass


def test_operational_marker_prevents_component_registration() -> None:
    class UndisclosedWorker:
        operational_execution_component = True

    with pytest.raises(AdvisoryOnlyBoundaryViolation):
        assert_advisory_only_component_registry({"worker": UndisclosedWorker()})
