"""ATLAS-036 SS13: the application service that makes `ItsmCiMappingRule` and
`ItsmCiReconciliationConflict` reachable -- versioned CI-class-to-Atlas-entity mapping rules, and
the explicit, never-silently-resolved conflict record SS13 requires whenever the CMDB and a live
observation disagree."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.cmdb_reconciliation_ports import (
    ItsmCiMappingRuleRepository,
    ItsmCiReconciliationConflictRepository,
)
from atlas.modules.itsm.application.dispatch_audit import (
    ItsmAuditEventKind,
    record_itsm_integration_event,
)
from atlas.modules.itsm.domain.cmdb_reconciliation import (
    ItsmCiConflictAuthority,
    ItsmCiConflictField,
    ItsmCiMappingRule,
    ItsmCiMatchState,
    ItsmCiReconciliationConflict,
)


class ItsmCmdbReconciliationError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ItsmCmdbReconciliationService:
    def __init__(
        self,
        *,
        rule_repository: ItsmCiMappingRuleRepository,
        conflict_repository: ItsmCiReconciliationConflictRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._rules = rule_repository
        self._conflicts = conflict_repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def register_mapping_rule(
        self,
        *,
        rule_id: str,
        version: int,
        external_ci_class: str,
        atlas_entity_type: str,
        profile_id: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmCiMappingRule:
        try:
            rule = ItsmCiMappingRule(
                rule_id=rule_id,
                version=version,
                external_ci_class=external_ci_class,
                atlas_entity_type=atlas_entity_type,
                profile_id=profile_id,
            )
        except ValueError as error:
            raise ItsmCmdbReconciliationError("itsm_ci_mapping_rule_invalid") from error
        await self._rules.save(rule)
        await self._audit(
            rule_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.CREATE,
            outcome="registered",
        )
        return rule

    async def record_conflict(
        self,
        *,
        conflict_id: str,
        external_ci_id: str,
        mapped_atlas_entity_id: str,
        field: ItsmCiConflictField,
        cmdb_value: str,
        cmdb_observed_at: datetime,
        live_value: str,
        live_observed_at: datetime,
        proposed_authority: ItsmCiConflictAuthority,
        confidence: float,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmCiReconciliationConflict:
        if await self._conflicts.get(conflict_id) is not None:
            raise ItsmCmdbReconciliationError("itsm_ci_reconciliation_conflict_already_recorded")
        try:
            conflict = ItsmCiReconciliationConflict(
                conflict_id=conflict_id,
                external_ci_id=external_ci_id,
                mapped_atlas_entity_id=mapped_atlas_entity_id,
                field=field,
                cmdb_value=cmdb_value,
                cmdb_observed_at=cmdb_observed_at,
                live_value=live_value,
                live_observed_at=live_observed_at,
                proposed_authority=proposed_authority,
                confidence=confidence,
                match_state=ItsmCiMatchState.AMBIGUOUS,
            )
        except ValueError as error:
            raise ItsmCmdbReconciliationError("itsm_ci_reconciliation_conflict_invalid") from error
        await self._conflicts.save(conflict)
        await self._audit(
            conflict_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.CONFLICT,
            outcome="detected",
        )
        return conflict

    async def update_match_state(
        self,
        *,
        conflict_id: str,
        match_state: ItsmCiMatchState,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ItsmCiReconciliationConflict:
        conflict = await self._conflicts.get(conflict_id)
        if conflict is None:
            raise ItsmCmdbReconciliationError("itsm_ci_reconciliation_conflict_not_found")
        try:
            updated = replace(conflict, match_state=match_state)
        except ValueError as error:
            raise ItsmCmdbReconciliationError("itsm_ci_reconciliation_conflict_invalid") from error
        await self._conflicts.save(updated)
        await self._audit(
            conflict_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.RECONCILIATION,
            outcome=match_state.value,
        )
        return updated

    async def close(self) -> None:
        await self._rules.close()
        await self._conflicts.close()

    async def _audit(
        self,
        reference: str,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        event_kind: ItsmAuditEventKind,
        outcome: str,
    ) -> None:
        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=event_kind,
            profile_reference=reference,
            actor_identity=actor.subject_id,
            is_automation=False,
            outcome=outcome,
            external_record_id=None,
            external_source_version=None,
            idempotency_key=None,
            detail_references=(reference,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
