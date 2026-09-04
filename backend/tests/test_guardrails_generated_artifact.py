from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.guardrails.domain.generated_artifact_guardrails import (
    ArtifactControlGate,
    GeneratedArtifact,
    GeneratedArtifactType,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

_ALL_GATES = frozenset(ArtifactControlGate)


def artifact(**overrides: object) -> GeneratedArtifact:
    defaults: dict[str, object] = {
        "artifact_id": "generated-artifact.example",
        "artifact_type": GeneratedArtifactType.RUNBOOK,
        "model_lineage": "model.example@1.0",
        "version": "1.0",
        "compatibility": "environment.production",
        "owner_identity_id": "subject.example",
        "expires_at": NOW + timedelta(days=90),
        "rollback_available": True,
        "completed_gates": _ALL_GATES,
        "published_by_service_id": "service.artifact-publisher",
        "self_granted_permissions": False,
    }
    defaults.update(overrides)
    return GeneratedArtifact(**defaults)  # type: ignore[arg-type]


def test_every_gate_cleared_and_published_is_ready_for_production() -> None:
    assert artifact().is_ready_for_production is True


def test_missing_gates_reports_exactly_the_gap() -> None:
    incomplete = frozenset(_ALL_GATES - {ArtifactControlGate.SECURITY_REVIEWED})
    example = artifact(completed_gates=incomplete)
    assert example.missing_gates == frozenset({ArtifactControlGate.SECURITY_REVIEWED})
    assert example.is_ready_for_production is False


def test_a_single_missing_gate_blocks_production_readiness() -> None:
    incomplete = frozenset(_ALL_GATES - {ArtifactControlGate.MALWARE_SCAN})
    assert artifact(completed_gates=incomplete).is_ready_for_production is False


def test_unpublished_by_any_service_is_never_ready() -> None:
    assert artifact(published_by_service_id=None).is_ready_for_production is False


def test_self_granted_permissions_is_never_ready_even_with_every_gate_cleared() -> None:
    assert artifact(self_granted_permissions=True).is_ready_for_production is False


def test_every_artifact_type_can_be_modeled() -> None:
    for artifact_type in GeneratedArtifactType:
        example = artifact(artifact_type=artifact_type)
        assert example.artifact_type is artifact_type


def test_expires_at_may_be_none_for_a_non_expiring_artifact() -> None:
    example = artifact(expires_at=None)
    assert example.expires_at is None


def test_rejects_a_naive_expires_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        artifact(expires_at=datetime(2026, 12, 1, 0, 0))


def test_rejects_blank_model_lineage() -> None:
    with pytest.raises(ValueError, match="model lineage"):
        artifact(model_lineage="   ")


def test_rejects_blank_version() -> None:
    with pytest.raises(ValueError, match="version"):
        artifact(version="   ")


def test_rejects_blank_compatibility() -> None:
    with pytest.raises(ValueError, match="compatibility"):
        artifact(compatibility="   ")


def test_the_full_gate_checklist_has_seventeen_entries() -> None:
    assert len(_ALL_GATES) == 17
