from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.modules.knowledge.adapters.source_registration_memory import (
    InMemoryKnowledgeSourceRegistrationRepository,
)
from atlas.modules.knowledge.application.source_registration import (
    KnowledgeSourceRegistrationError,
    KnowledgeSourceRegistrationService,
)
from atlas.modules.knowledge.domain.source_registration import (
    KnowledgeSourceClass,
    KnowledgeSourceLifecycleState,
    content_from_an_unregistered_source_is_eligible_for_retrieval,
    is_valid_knowledge_source_transition,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[KnowledgeSourceRegistrationService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = KnowledgeSourceRegistrationService(
        repository=InMemoryKnowledgeSourceRegistrationRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def _register_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "source_id": "source.hitachi-docs.primary",
        "display_name": "Hitachi Ops Center Documentation",
        "source_type": "vendor_documentation_site",
        "source_class": KnowledgeSourceClass.VENDOR_AUTHORITATIVE,
        "owner": "subject.knowledge-owner.primary",
        "technical_contact": "subject.knowledge-engineer.primary",
        "acquisition_method": "scheduled_crawl",
        "acquisition_endpoint": "https://docs.hitachivantara.example/ops-center",
        "secret_reference_id": "secret.knowledge.hitachi-docs",
        "organization_id": "organization.atlas.local",
        "tenant_id": "tenant.primary",
        "environment_id": "environment.production",
        "vendor": "Hitachi",
        "product": "Ops Center",
        "default_classification": DataClassification.INTERNAL,
        "access_mapping_method": "role_based_static",
        "expected_version_behavior": "Versioned by publication date; superseded on new release.",
        "authority_trust_rationale": "Vendor-authoritative published documentation.",
        "retention_policy": "Retain latest three published versions.",
        "deletion_policy": "Tombstone on retirement per ATLAS-027 SS24.",
        "license_or_usage_restrictions": "Internal use per vendor support agreement.",
        "ingestion_schedule": "Weekly, Sundays 02:00 UTC.",
        "failure_policy": "Retry twice, then quarantine and alert the owner.",
        "correlation_id": "correlation.test",
    }
    values.update(overrides)
    return values


def test_absolute_rule_is_false() -> None:
    assert content_from_an_unregistered_source_is_eligible_for_retrieval() is False


def test_registered_source_cannot_reach_active_directly() -> None:
    assert (
        is_valid_knowledge_source_transition(
            KnowledgeSourceLifecycleState.REGISTERED, KnowledgeSourceLifecycleState.ACTIVE
        )
        is False
    )
    assert (
        is_valid_knowledge_source_transition(
            KnowledgeSourceLifecycleState.REGISTERED, KnowledgeSourceLifecycleState.VALIDATING
        )
        is True
    )


@pytest.mark.asyncio
async def test_register_creates_a_registered_source() -> None:
    service, audit_sink = _service()
    registration = await service.register(**_register_kwargs())  # type: ignore[arg-type]
    assert registration.state is KnowledgeSourceLifecycleState.REGISTERED
    assert any(item.result_code == "source_registration.registered" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_register_twice_is_refused() -> None:
    service, _audit = _service()
    await service.register(**_register_kwargs())  # type: ignore[arg-type]
    with pytest.raises(
        KnowledgeSourceRegistrationError, match="knowledge_source_already_registered"
    ):
        await service.register(**_register_kwargs())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_register_requires_every_ss7_element() -> None:
    service, _audit = _service()
    with pytest.raises(
        KnowledgeSourceRegistrationError, match="knowledge_source_registration_invalid"
    ):
        await service.register(**_register_kwargs(retention_policy="   "))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_full_lifecycle_to_active_then_retired() -> None:
    service, audit_sink = _service()
    registration = await service.register(**_register_kwargs())  # type: ignore[arg-type]
    await service.transition(
        source_id=registration.source_id,
        target=KnowledgeSourceLifecycleState.VALIDATING,
        correlation_id="correlation.test",
    )
    active = await service.transition(
        source_id=registration.source_id,
        target=KnowledgeSourceLifecycleState.ACTIVE,
        correlation_id="correlation.test",
    )
    assert active.state is KnowledgeSourceLifecycleState.ACTIVE
    retiring = await service.transition(
        source_id=registration.source_id,
        target=KnowledgeSourceLifecycleState.RETIRING,
        correlation_id="correlation.test",
    )
    retired = await service.transition(
        source_id=retiring.source_id,
        target=KnowledgeSourceLifecycleState.RETIRED,
        correlation_id="correlation.test",
    )
    assert retired.state is KnowledgeSourceLifecycleState.RETIRED
    assert any(item.result_code == "source_registration.active" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_transition_rejects_an_undiagrammed_target() -> None:
    service, _audit = _service()
    registration = await service.register(**_register_kwargs())  # type: ignore[arg-type]
    with pytest.raises(
        KnowledgeSourceRegistrationError, match="knowledge_source_transition_invalid"
    ):
        await service.transition(
            source_id=registration.source_id,
            target=KnowledgeSourceLifecycleState.ACTIVE,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_transition_requires_an_existing_registration() -> None:
    service, _audit = _service()
    with pytest.raises(KnowledgeSourceRegistrationError, match="knowledge_source_unavailable"):
        await service.transition(
            source_id="source.no-such-one",
            target=KnowledgeSourceLifecycleState.VALIDATING,
            correlation_id="correlation.test",
        )


def test_retired_state_is_terminal() -> None:
    for target in KnowledgeSourceLifecycleState:
        assert (
            is_valid_knowledge_source_transition(KnowledgeSourceLifecycleState.RETIRED, target)
            is False
        )
