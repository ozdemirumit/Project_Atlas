from __future__ import annotations

from atlas.modules.platform.domain.bootstrap_service_deployment import (
    BootstrapServiceSpec,
    ServiceEndpointClass,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class SyntheticBootstrapServiceCatalog:
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[str, str, tuple[BootstrapServiceSpec, ...]]:
        if profile not in {DeploymentProfile.DEVELOPER, DeploymentProfile.LINUX_LAB}:
            raise ValueError(
                "synthetic service deployment is restricted to non-production profiles"
            )
        if environment_id != "environment.test":
            raise ValueError("synthetic service deployment requires the test environment")
        return (
            "target.atlas-synthetic-runtime.primary",
            "target-kind.synthetic-file-runtime",
            (
                BootstrapServiceSpec(
                    service_id="service.atlas-api",
                    sequence=1,
                    artifact_id="artifact.backend.image",
                    artifact_sha256=(
                        "f010f237cc478705d8a92cab6c8988c30768af405d82630408782900e93cb75f"
                    ),
                    dependencies=(),
                    workload_identity_id="workload.atlas-api.primary",
                    endpoint_class=ServiceEndpointClass.PRIVATE,
                    cpu_limit_millicores=1000,
                    memory_limit_mb=1024,
                    startup_probe_id="probe.atlas-api.startup",
                    readiness_probe_id="probe.atlas-api.readiness",
                    liveness_probe_id="probe.atlas-api.liveness",
                ),
                BootstrapServiceSpec(
                    service_id="service.atlas-web",
                    sequence=2,
                    artifact_id="artifact.frontend.image",
                    artifact_sha256=(
                        "1ed84304d7a465be45457bb43b5bb1a6dba86d1435b77cd1d168d26048536ace"
                    ),
                    dependencies=("service.atlas-api",),
                    workload_identity_id=None,
                    endpoint_class=ServiceEndpointClass.PRIVATE,
                    cpu_limit_millicores=500,
                    memory_limit_mb=256,
                    startup_probe_id="probe.atlas-web.startup",
                    readiness_probe_id="probe.atlas-web.readiness",
                    liveness_probe_id="probe.atlas-web.liveness",
                ),
            ),
        )
