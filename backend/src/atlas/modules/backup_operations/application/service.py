from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.backup_operations.application.ports import BackupOverviewProvider
from atlas.modules.backup_operations.domain.models import BackupOverview


@dataclass(frozen=True, slots=True)
class BackupReadContext:
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


class BackupOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class BackupOperationsService:
    def __init__(
        self,
        *,
        provider: BackupOverviewProvider,
        organization_id: str,
        environment_id: str,
        site_id: str,
        audit_sink: AuditSink,
        resource_id: str = "resource.backup.lab-overview",
    ) -> None:
        self._provider = provider
        self._organization_id = organization_id
        self._environment_id = environment_id
        self._site_id = site_id
        self._resource_id = resource_id
        self._audit_sink = audit_sink

    async def get_overview(self, context: BackupReadContext) -> BackupOverview:
        expected = (self._organization_id, self._environment_id, self._site_id)
        actual = (context.organization_id, context.environment_id, context.site_id)
        if actual != expected or context.resource_id != self._resource_id:
            raise BackupOperationsError(
                "backup_scope_mismatch", "The backup overview is outside the authorized scope."
            )
        overview = await self._provider.get_overview(requested_at=context.requested_at)
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.backup.overview.read",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id="backup.overview.read",
                resource_type="resource.backup.overview",
                scope_reference="/".join((*actual, context.resource_id)),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code="backup_overview_returned",
            )
        )
        return overview
