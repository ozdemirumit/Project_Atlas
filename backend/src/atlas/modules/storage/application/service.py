from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.storage.domain.models import StorageOverview


@dataclass(frozen=True, slots=True)
class StorageReadContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    resource_id: str
    correlation_id: str
    decision_id: str
    requested_at: datetime


class StorageOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class StorageOperationsService:
    def __init__(self, *, overview: StorageOverview, audit_sink: AuditSink) -> None:
        self._overview = overview
        self._audit_sink = audit_sink

    async def get_overview(self, context: StorageReadContext) -> StorageOverview:
        expected = (
            self._overview.organization_id,
            self._overview.environment_id,
            self._overview.site_id,
        )
        actual = (context.organization_id, context.environment_id, context.site_id)
        if actual != expected or context.resource_id != "resource.storage.lab-overview":
            raise StorageOperationsError(
                "storage_scope_mismatch", "The storage overview is outside the authorized scope."
            )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.storage.overview.read",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id="storage.overview.read",
                resource_type="resource.storage.overview",
                scope_reference="/".join((*actual, context.resource_id)),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code="storage_overview_returned",
            )
        )
        return self._overview
