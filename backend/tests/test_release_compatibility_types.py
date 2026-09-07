from __future__ import annotations

import pytest

from atlas.modules.release.domain.compatibility_types import (
    CompatibilityMatrixEntry,
    ReleaseType,
    is_production_supported,
)
from atlas.modules.release.domain.versioning import SemanticVersion


def platform_version() -> SemanticVersion:
    return SemanticVersion(
        major=1,
        minor=4,
        patch=0,
        prerelease_label=None,
        prerelease_number=None,
        build_metadata=None,
    )


def matrix_entry(**overrides: object) -> CompatibilityMatrixEntry:
    defaults: dict[str, object] = {
        "platform_version": platform_version(),
        "component_versions": (("backend", "1.4.0"), ("frontend", "1.4.0")),
        "supported_source_versions_for_upgrade": ("1.3.x",),
        "infrastructure_versions": (("postgres", "16"), ("pgvector", "0.7")),
        "api_and_event_major_versions": ("v1",),
        "connector_sdk_and_package_compatibility": ("sdk-1.0.x",),
        "supported_vendor_products": ("Example Storage 6.1",),
        "model_endpoint_protocol_and_approved_profiles": ("openai_compatible.v1",),
        "supported_platform_environment_versions": ("ubuntu-22.04",),
        "deployment_and_offline_bundle_profiles": ("linux_lab",),
        "known_incompatible_combinations": (),
        "evidence_references": ("evidence.compat-suite.2026-09-04",),
        "owner": "release-management-owner",
    }
    defaults.update(overrides)
    return CompatibilityMatrixEntry(**defaults)  # type: ignore[arg-type]


def test_matrix_entry_accepts_valid_state() -> None:
    assert matrix_entry().owner == "release-management-owner"


def test_matrix_entry_requires_evidence() -> None:
    with pytest.raises(ValueError, match="backed by test evidence"):
        matrix_entry(evidence_references=())


def test_matrix_entry_requires_owner() -> None:
    with pytest.raises(ValueError, match="has an owner"):
        matrix_entry(owner="")


def test_release_type_has_ten_members() -> None:
    assert len(ReleaseType) == 10


@pytest.mark.parametrize(
    "release_type",
    [
        ReleaseType.DEVELOPMENT_SNAPSHOT,
        ReleaseType.ALPHA,
        ReleaseType.BETA,
        ReleaseType.RELEASE_CANDIDATE,
    ],
)
def test_prerelease_types_not_production_supported_by_default(release_type: ReleaseType) -> None:
    assert is_production_supported(release_type, explicitly_stated=False) is False
    assert is_production_supported(release_type, explicitly_stated=True) is True


@pytest.mark.parametrize(
    "release_type",
    [
        ReleaseType.GENERAL_RELEASE,
        ReleaseType.SECURITY_RELEASE,
        ReleaseType.HOTFIX,
        ReleaseType.LTS_RELEASE,
        ReleaseType.CONNECTOR_RELEASE,
        ReleaseType.DOCUMENTATION_RELEASE,
    ],
)
def test_general_types_always_production_supported(release_type: ReleaseType) -> None:
    assert is_production_supported(release_type, explicitly_stated=False) is True
