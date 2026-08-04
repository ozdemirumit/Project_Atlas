from __future__ import annotations

from atlas.modules.platform.domain.bootstrap_identity_handoff import (
    BootstrapIdentityGroupMapping,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class SyntheticBootstrapIdentityCatalog:
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[str, str, str, str, str, str, str, tuple[BootstrapIdentityGroupMapping, ...]]:
        if profile not in {DeploymentProfile.DEVELOPER, DeploymentProfile.LINUX_LAB}:
            raise ValueError("synthetic identity handoff is restricted to non-production profiles")
        if environment_id != "environment.test":
            raise ValueError("synthetic identity handoff requires the test environment")
        return (
            "target.atlas-synthetic-identity.primary",
            "target-kind.synthetic-file-identity",
            "subject.bootstrap-administrator.primary",
            "secret-reference.bootstrap-administrator.verifier",
            "identity.recovery-administrator.primary",
            "provider.ldap.enterprise",
            "subject.pilot.platform-administrator",
            (
                BootstrapIdentityGroupMapping(
                    mapping_id="mapping.platform-administrators",
                    directory_group_reference="directory-group.platform-administrators",
                    role_ids=("role.platform-administrator",),
                ),
                BootstrapIdentityGroupMapping(
                    mapping_id="mapping.security-administrators",
                    directory_group_reference="directory-group.security-administrators",
                    role_ids=("role.security-administrator",),
                ),
            ),
        )
