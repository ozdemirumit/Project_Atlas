from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.domain.bootstrap_plan import (
    BootstrapPhase,
    BootstrapPhaseState,
    BootstrapPlan,
    BootstrapPlanRequest,
    BootstrapPlanState,
)


class BootstrapPlanScopeError(RuntimeError):
    pass


PHASES: tuple[tuple[str, str, tuple[str, ...], bool, str], ...] = (
    ("phase.acquire", "Acquire and verify artifacts", (), True, "Stop without mutation."),
    (
        "phase.configure",
        "Render validated configuration",
        ("phase.acquire",),
        True,
        "Keep the prior valid plan.",
    ),
    (
        "phase.trust",
        "Provision trust and identities",
        ("phase.configure",),
        True,
        "Preserve prior trust and remove only attempt-owned temporary material.",
    ),
    (
        "phase.data",
        "Initialize or migrate data",
        ("phase.trust",),
        True,
        "Do not overwrite unknown data; resume or restore from an approved checkpoint.",
    ),
    (
        "phase.services",
        "Deploy Atlas services",
        ("phase.data",),
        True,
        "Keep the prior healthy release when available.",
    ),
    (
        "phase.identity",
        "Bootstrap administration and authentication",
        ("phase.services",),
        True,
        "Preserve the verified recovery identity path.",
    ),
    (
        "phase.integrations",
        "Validate model and core integrations",
        ("phase.identity",),
        True,
        "Leave unavailable integrations inactive.",
    ),
    (
        "phase.verify",
        "Run end-to-end verification",
        ("phase.integrations",),
        True,
        "Mark the deployment failed or degraded; do not claim readiness.",
    ),
    (
        "phase.handoff",
        "Produce operational handoff evidence",
        ("phase.verify",),
        False,
        "Do not hand off an unverified deployment.",
    ),
)


class BootstrapPlanService:
    def __init__(
        self,
        *,
        environment_id: str,
        site_id: str,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._environment_id = environment_id
        self._site_id = site_id
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def build(
        self, *, actor: AuthenticatedSubject, request: BootstrapPlanRequest, correlation_id: str
    ) -> BootstrapPlan:
        if (
            request.organization_id != actor.organization_id
            or request.environment_id != self._environment_id
            or request.site_id != self._site_id
        ):
            await self._audit_denial(actor, request, correlation_id)
            raise BootstrapPlanScopeError("bootstrap plan scope does not match actor")
        gates_ready = (
            request.preflight_state == "passed" and request.configuration_state == "passed"
        )
        phase_state = BootstrapPhaseState.READY if gates_ready else BootstrapPhaseState.BLOCKED
        input_refs = (
            f"manifest:{request.manifest_digest}",
            f"configuration:{request.configuration_digest}",
        )
        phases = tuple(
            BootstrapPhase(
                phase_id=phase_id,
                sequence=index,
                title=title,
                dependencies=dependencies,
                state=phase_state,
                resumable=resumable,
                input_references=input_refs,
                stop_guidance=guidance,
            )
            for index, (phase_id, title, dependencies, resumable, guidance) in enumerate(PHASES, 1)
        )
        canonical = json.dumps(
            {
                "schema_version": "atlas.bootstrap-plan.v1",
                "release_id": request.release_id,
                "profile": request.profile.value,
                "organization_id": request.organization_id,
                "environment_id": request.environment_id,
                "site_id": request.site_id,
                "manifest_digest": request.manifest_digest,
                "configuration_digest": request.configuration_digest,
                "preflight_state": request.preflight_state,
                "configuration_state": request.configuration_state,
                "phases": [(item.phase_id, item.dependencies, item.resumable) for item in phases],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = sha256(canonical).hexdigest()
        plan = BootstrapPlan(
            plan_id=f"bootstrap-plan.{uuid4().hex}",
            schema_version="atlas.bootstrap-plan.v1",
            release_id=request.release_id,
            profile=request.profile,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            site_id=request.site_id,
            state=BootstrapPlanState.READY if gates_ready else BootstrapPlanState.BLOCKED,
            plan_digest=digest,
            resume_key=f"resume.{digest[:32]}",
            phases=phases,
            generated_at=self._clock(),
            correlation_id=correlation_id,
        )
        await self._audit(actor, plan)
        return plan

    async def _audit(self, actor: AuthenticatedSubject, plan: BootstrapPlan) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.bootstrap-plan.read",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=plan.generated_at,
                correlation_id=plan.correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.bootstrap-plan.read",
                resource_type="resource.platform.bootstrap-plan",
                scope_reference=f"{actor.organization_id}/{self._environment_id}/{self._site_id}/domain.platform/resource.platform.bootstrap-plan/C0",
                decision_id=None,
                outcome="succeeded",
                result_code=f"bootstrap_plan_{plan.state.value}",
                target_metadata=(
                    ("release_id", plan.release_id),
                    ("plan_digest", plan.plan_digest),
                    ("phase_count", str(len(plan.phases))),
                ),
            )
        )

    async def _audit_denial(
        self, actor: AuthenticatedSubject, request: BootstrapPlanRequest, correlation_id: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.bootstrap-plan.read",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.bootstrap-plan.read",
                resource_type="resource.platform.bootstrap-plan",
                scope_reference="scope.redacted",
                decision_id=None,
                outcome="denied",
                result_code="bootstrap_plan_scope_mismatch",
                target_metadata=(("profile", request.profile.value),),
            )
        )
