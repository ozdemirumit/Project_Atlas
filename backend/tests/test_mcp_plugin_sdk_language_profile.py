from __future__ import annotations

import pytest

from atlas.modules.mcp_plugin_sdk.domain.language_profile import (
    LanguageProfile,
    language_profile_requires_adr_before_implementation,
)


def profile(**overrides: object) -> LanguageProfile:
    defaults: dict[str, object] = {
        "profile_id": "language-profile.python",
        "supported_language": "python",
        "supported_runtime_versions": ("3.12", "3.13"),
        "project_layout_reference": "docs.connector-project-layout.v1",
        "package_manager": "uv",
        "sdk_binding_version": "1.0.0",
        "dependency_lock_requirement": "uv.lock is committed and verified in CI",
        "static_analysis_and_formatting_tools": ("ruff", "mypy"),
        "test_runner": "pytest",
        "package_format": "wheel",
        "entry_point_convention": "atlas_connector.<connector_id>.main:handle",
        "runner_base_image_or_prerequisites": "python:3.12-slim",
    }
    defaults.update(overrides)
    return LanguageProfile(**defaults)  # type: ignore[arg-type]


def test_profile_accepts_valid_state() -> None:
    assert profile().supported_language == "python"


def test_profile_requires_supported_runtime_versions() -> None:
    with pytest.raises(ValueError, match="at least one supported runtime version"):
        profile(supported_runtime_versions=())


def test_profile_requires_static_analysis_tools() -> None:
    with pytest.raises(ValueError, match="static analysis or formatting tool"):
        profile(static_analysis_and_formatting_tools=())


def test_profile_requires_test_runner() -> None:
    with pytest.raises(ValueError, match="requires a test runner"):
        profile(test_runner="")


def test_language_profile_always_requires_an_adr_before_implementation() -> None:
    assert language_profile_requires_adr_before_implementation() is True
