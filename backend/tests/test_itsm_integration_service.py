from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.itsm.adapters.memory import InMemoryItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.postgres import PostgreSQLItsmIntegrationProfileRepository
from atlas.modules.itsm.application.service import ItsmIntegrationError, ItsmIntegrationService
from atlas.modules.itsm.domain.models import (
    ItsmAllowedOperation,
    ItsmFieldMapping,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessState,
    ItsmWriteSemantics,
)

NOW = datetime(2026, 8, 13, 4, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.itsm.integration-admin",
        display_name="ITSM Integration Admin",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.itsm-integration-admin",),
    )


def mappings() -> tuple[ItsmFieldMapping, ...]:
    return (
        ItsmFieldMapping("work_notes", "work_notes", ItsmWriteSemantics.APPEND_ONLY),
        ItsmFieldMapping(
            "u_atlas_report_reference",
            "u_atlas_report_reference",
            ItsmWriteSemantics.REFERENCE_ONLY,
        ),
        ItsmFieldMapping(
            "u_atlas_review_state",
            "u_atlas_review_state",
            ItsmWriteSemantics.REFERENCE_ONLY,
        ),
    )


def create_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "profile_key": "itsm.sandbox.primary",
        "display_name": "Primary ITSM sandbox",
        "provider_family": ItsmProviderFamily.GENERIC_REST,
        "instance_reference": "itsm-instance.sandbox.primary",
        "owner_id": "team.service-management",
        "purpose": "Validate governed report handoff mappings in an isolated ITSM sandbox.",
        "endpoint_origin": "https://itsm-sandbox.example.invalid",
        "trust_boundary_reference": "trust-boundary.itsm.sandbox",
        "secret_reference_id": "secret.itsm.sandbox.writer",
        "classification_ceiling": DataClassification.INTERNAL,
        "allowed_operations": (ItsmAllowedOperation.APPEND_ANALYSIS,),
        "mapping_version": 1,
        "field_mappings": mappings(),
        "sandbox_validation_reference": None,
        "sandbox_validation_digest": None,
        "audit_profile_id": "audit-profile.itsm.sandbox",
        "acknowledged_configuration_only": True,
        "idempotency_key": "itsm-profile-create-0001",
        "correlation_id": "correlation.itsm.profile.create",
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_profile_readiness_is_deterministic_and_never_authorizes_dispatch() -> None:
    sink = CollectingAuditSink()
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=sink,
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    blocked = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    replay = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]

    assert blocked.readiness.state is ItsmReadinessState.BLOCKED
    assert replay.profile_id == blocked.profile_id
    assert replay.reused is True
    assert not any(
        (
            blocked.readiness.dispatch_authorized,
            blocked.readiness.external_record_mutation_authorized,
            blocked.readiness.workflow_approved,
            blocked.readiness.execution_authorized,
        )
    )
    assert {item.reason_code for item in blocked.readiness.checks} >= {
        "itsm.readiness.sandbox_validation_missing"
    }


@pytest.mark.asyncio
async def test_sandbox_evidence_makes_profile_ready_for_sandbox_only() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    profile = await service.create(
        actor=actor(),
        **create_values(
            sandbox_validation_reference="validation.itsm.sandbox.001",
            sandbox_validation_digest="a" * 64,
        ),  # type: ignore[arg-type]
    )

    assert profile.readiness.state is ItsmReadinessState.READY_FOR_SANDBOX
    assert all(item.state.value == "satisfied" for item in profile.readiness.checks)
    assert profile.lifecycle is ItsmProfileLifecycle.ACTIVE


@pytest.mark.asyncio
async def test_retirement_is_optimistic_and_preserves_history() -> None:
    repository = InMemoryItsmIntegrationProfileRepository()
    service = ItsmIntegrationService(
        repository=repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    with pytest.raises(ItsmIntegrationError, match="version_conflict"):
        await service.retire(
            actor=actor(),
            profile_id=profile.profile_id,
            expected_version=9,
            reason="Retire the sandbox profile after replacing its governed mapping contract.",
            acknowledged_history_preserved_and_dispatch_absent=True,
            idempotency_key="itsm-profile-retire-stale",
            correlation_id="correlation.itsm.profile.retire.stale",
        )
    retired = await service.retire(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_version=1,
        reason="Retire the sandbox profile after replacing its governed mapping contract.",
        acknowledged_history_preserved_and_dispatch_absent=True,
        idempotency_key="itsm-profile-retire-0001",
        correlation_id="correlation.itsm.profile.retire",
    )
    assert retired.lifecycle is ItsmProfileLifecycle.RETIRED
    assert retired.version == 2
    assert (await repository.get(profile_id=profile.profile_id)) == retired


def test_mapping_rejects_arbitrary_or_mutable_fields() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        ItsmFieldMapping("password", "password", ItsmWriteSemantics.REFERENCE_ONLY)
    with pytest.raises(ValueError, match="append-only"):
        ItsmFieldMapping("work_notes", "work_notes", ItsmWriteSemantics.REFERENCE_ONLY)


@pytest.mark.asyncio
async def test_postgres_payload_round_trip_preserves_readiness_and_no_authority() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    payload = ItsmIntegrationService._normalize(asdict(profile))
    assert isinstance(payload, dict)
    restored = PostgreSQLItsmIntegrationProfileRepository._to_domain(payload)

    assert restored == profile
    assert restored.readiness.canonical_digest == profile.readiness.canonical_digest
    assert restored.secret_reference_id == "secret.itsm.sandbox.writer"
    assert restored.readiness.dispatch_authorized is False
    assert restored.readiness.external_record_mutation_authorized is False
