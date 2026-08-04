from __future__ import annotations

from atlas.modules.platform.domain.bootstrap_data_initialization import (
    BootstrapMigrationSpec,
    MigrationCompatibility,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class SyntheticBootstrapDataCatalog:
    def load(
        self, *, profile: DeploymentProfile, environment_id: str
    ) -> tuple[str, str, str, tuple[BootstrapMigrationSpec, ...]]:
        if profile not in {DeploymentProfile.DEVELOPER, DeploymentProfile.LINUX_LAB}:
            raise ValueError(
                "synthetic data initialization is restricted to non-production profiles"
            )
        if environment_id != "environment.test":
            raise ValueError("synthetic data initialization requires the test environment")
        return (
            "target.atlas-synthetic-database.primary",
            "target-kind.synthetic-file-database",
            "5dedf864600818710fe066f714ebd7d596c460b713b1ecf20d7a7bb7f8764f52",
            (
                BootstrapMigrationSpec(
                    migration_id="migration.atlas-schema-metadata.v1",
                    sequence=1,
                    sha256="47f9d972badb95e88c6d15493ed64fbd2192a392886427b6d5b1d365c26abf3e",
                    from_revision="schema.none",
                    to_revision="schema.atlas-metadata.v1",
                    compatibility=MigrationCompatibility.EXPAND,
                    reversible=True,
                    destructive=False,
                    recovery_code="recovery.remove-attempt-owned-target",
                    expected_object_count=2,
                ),
                BootstrapMigrationSpec(
                    migration_id="migration.atlas-core-schema.v1",
                    sequence=2,
                    sha256="b46950d86aa13f6331498f0c96a4c63486c769165703b37c2f9a56dc11f28250",
                    from_revision="schema.atlas-metadata.v1",
                    to_revision="schema.atlas-core.v1",
                    compatibility=MigrationCompatibility.EXPAND,
                    reversible=True,
                    destructive=False,
                    recovery_code="recovery.remove-attempt-owned-target",
                    expected_object_count=8,
                ),
                BootstrapMigrationSpec(
                    migration_id="migration.atlas-bootstrap-state.v1",
                    sequence=3,
                    sha256="8be0a817582ddbc4e57bcaf27b97599822894dd98d84cb22ac95e728497fbd55",
                    from_revision="schema.atlas-core.v1",
                    to_revision="schema.atlas-bootstrap.v1",
                    compatibility=MigrationCompatibility.EXPAND,
                    reversible=True,
                    destructive=False,
                    recovery_code="recovery.remove-attempt-owned-target",
                    expected_object_count=4,
                ),
            ),
        )
