"""ATLAS-015 SS7/SS8: Knowledge Source Registration application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.knowledge.application.source_registration_ports import (
    KnowledgeSourceRegistrationRepository,
)
from atlas.modules.knowledge.domain.source_registration import (
    KnowledgeSourceClass,
    KnowledgeSourceLifecycleState,
    KnowledgeSourceRegistration,
    is_valid_knowledge_source_transition,
)


class KnowledgeSourceRegistrationError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class KnowledgeSourceRegistrationService:
    def __init__(
        self,
        *,
        repository: KnowledgeSourceRegistrationRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def register(
        self,
        *,
        source_id: str,
        display_name: str,
        source_type: str,
        source_class: KnowledgeSourceClass,
        owner: str,
        technical_contact: str,
        acquisition_method: str,
        acquisition_endpoint: str,
        secret_reference_id: str,
        organization_id: str,
        tenant_id: str,
        environment_id: str,
        vendor: str,
        product: str,
        default_classification: DataClassification,
        access_mapping_method: str,
        expected_version_behavior: str,
        authority_trust_rationale: str,
        retention_policy: str,
        deletion_policy: str,
        license_or_usage_restrictions: str,
        ingestion_schedule: str,
        failure_policy: str,
        correlation_id: str,
    ) -> KnowledgeSourceRegistration:
        now = self._clock()
        try:
            registration = KnowledgeSourceRegistration(
                source_id=source_id,
                display_name=display_name,
                source_type=source_type,
                source_class=source_class,
                owner=owner,
                technical_contact=technical_contact,
                acquisition_method=acquisition_method,
                acquisition_endpoint=acquisition_endpoint,
                secret_reference_id=secret_reference_id,
                organization_id=organization_id,
                tenant_id=tenant_id,
                environment_id=environment_id,
                vendor=vendor,
                product=product,
                default_classification=default_classification,
                access_mapping_method=access_mapping_method,
                expected_version_behavior=expected_version_behavior,
                authority_trust_rationale=authority_trust_rationale,
                retention_policy=retention_policy,
                deletion_policy=deletion_policy,
                license_or_usage_restrictions=license_or_usage_restrictions,
                ingestion_schedule=ingestion_schedule,
                failure_policy=failure_policy,
                state=KnowledgeSourceLifecycleState.REGISTERED,
                registered_at=now,
                updated_at=now,
            )
        except ValueError as error:
            raise KnowledgeSourceRegistrationError(
                "knowledge_source_registration_invalid"
            ) from error
        if not await self._repository.create(registration):
            raise KnowledgeSourceRegistrationError("knowledge_source_already_registered")
        await self._audit(
            correlation_id=correlation_id,
            source_id=source_id,
            outcome=KnowledgeSourceLifecycleState.REGISTERED.value,
        )
        return registration

    async def transition(
        self,
        *,
        source_id: str,
        target: KnowledgeSourceLifecycleState,
        correlation_id: str,
    ) -> KnowledgeSourceRegistration:
        current = await self._repository.get(source_id)
        if current is None:
            raise KnowledgeSourceRegistrationError("knowledge_source_unavailable")
        if not is_valid_knowledge_source_transition(current.state, target):
            raise KnowledgeSourceRegistrationError("knowledge_source_transition_invalid")
        updated = replace(current, state=target, updated_at=self._clock())
        await self._repository.update(updated)
        await self._audit(correlation_id=correlation_id, source_id=source_id, outcome=target.value)
        return updated

    async def _audit(self, *, correlation_id: str, source_id: str, outcome: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.source-registration",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=None,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.knowledge.source",
                scope_reference=source_id,
                decision_id=None,
                outcome="succeeded",
                result_code=f"source_registration.{outcome}",
            )
        )
