from atlas.modules.platform.application.service import PlatformStatusService
from atlas.modules.platform.domain.status import ComponentHealth, ComponentState


class FailingRequiredProbe:
    name = "required-service"
    required = True

    async def check(self) -> ComponentHealth:
        return ComponentHealth(
            name=self.name,
            status=ComponentState.UNAVAILABLE,
            required=self.required,
            code="required_service_unavailable",
        )


async def test_required_component_failure_blocks_readiness() -> None:
    service = PlatformStatusService(
        service_name="atlas-test",
        service_version="0.1.0",
        environment="test",
        probes=(FailingRequiredProbe(),),
    )

    status = await service.get_status()

    assert status.ready is False
    assert status.status is ComponentState.UNAVAILABLE
    assert status.warnings == ("required_service_unavailable",)
