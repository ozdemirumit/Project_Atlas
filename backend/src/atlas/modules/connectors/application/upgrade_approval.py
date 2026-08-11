from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeApprovalError,
    ConnectorUpgradeApprovalPolicySource,
    ConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalPolicySnapshot,
    ConnectorUpgradeApprovalRequest,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

UPGRADE_APPROVAL_POLICY_SCHEMA = "atlas.connector-upgrade-approval-policy.v1"
UPGRADE_APPROVAL_REQUEST_SCHEMA = "atlas.connector-upgrade-approval-request.v1"
UPGRADE_APPROVAL_CREATE_PERMISSION = "connectors.upgrade-approval-requests.create"
UPGRADE_APPROVAL_READ_PERMISSION = "connectors.upgrade-approval-requests.read"


class ConnectorUpgradeApprovalService:
    def __init__(
        self,
        *,
        repository: ConnectorUpgradeApprovalRepository,
        policy_source: ConnectorUpgradeApprovalPolicySource,
        upgrade_service: ConnectorUpgradeReadinessService,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._policy_source = policy_source
        self._upgrade_service = upgrade_service
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        candidate_receipt_id: str,
        source_plan_digest: str,
        purpose: str,
        acknowledged_request_is_not_approval_and_grants_no_execution_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRequest:
        self._require_enterprise_human(actor)
        if not acknowledged_request_is_not_approval_and_grants_no_execution_authority:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_invalid")
        plan = await self._upgrade_service.plan(
            actor=actor,
            record_id=record_id,
            candidate_receipt_id=candidate_receipt_id,
            correlation_id=correlation_id,
        )
        now = self._clock()
        if (
            plan.canonical_digest != source_plan_digest
            or plan.source_record_id != record_id
            or plan.candidate_receipt_id != candidate_receipt_id
            or plan.plan_state != "ready_for_human_review"
            or not plan.plan_eligible
            or plan.target_configured
            or plan.blockers
            or now >= plan.expires_at
            or not plan.approval_required
            or not plan.decision_support_only
            or plan.execution_authorized
            or plan.infrastructure_mutation_performed
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_plan_not_eligible")
        policy = await self._active_policy(actor=actor, now=now)
        fingerprint = self._digest(
            {
                "plan_digest": plan.canonical_digest,
                "approval_policy_digest": policy.canonical_digest,
                "requested_by": actor.subject_id,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        seed = self._digest(
            [
                actor.organization_id,
                self._environment_id,
                plan.canonical_digest,
                policy.canonical_digest,
            ]
        )
        request = ConnectorUpgradeApprovalRequest(
            request_id=f"connector-upgrade-approval-request.{seed[:24]}",
            schema_version=UPGRADE_APPROVAL_REQUEST_SCHEMA,
            version=1,
            source_record_id=plan.source_record_id,
            source_record_version=plan.source_record_version,
            instance_id=plan.instance_id,
            connector_id=plan.connector_id,
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            readiness_digest=plan.readiness_digest,
            current_release_version=plan.current_release_version,
            current_receipt_id=plan.current_receipt_id,
            current_receipt_digest=plan.current_receipt_digest,
            candidate_release_version=plan.candidate_release_version,
            candidate_receipt_id=plan.candidate_receipt_id,
            candidate_receipt_digest=plan.candidate_receipt_digest,
            candidate_digest=plan.candidate_digest,
            risk_level=plan.risk_level,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            requested_by=actor.subject_id,
            purpose=purpose,
            approval_policy_id=policy.policy_id,
            approval_policy_digest=policy.canonical_digest,
            approval_policy_version=policy.policy_version,
            created_at=now,
            expires_at=now + timedelta(minutes=policy.request_lifetime_minutes),
            state="pending",
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        request = replace(
            request,
            canonical_digest=self._digest(self._request_payload(request)),
        )
        async with self._mutation_lock:
            prior = await self._repository.get_by_plan(plan_digest=plan.canonical_digest)
            if prior is not None:
                if (
                    prior.requested_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=UPGRADE_APPROVAL_CREATE_PERMISSION,
                result_code="connector_upgrade_approval_request_created",
                request=request,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.add(request):
                raced = await self._repository.get_by_create_key(
                    requested_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorUpgradeApprovalError(
                        "connector_upgrade_approval_request_conflict"
                    )
                self._verify_request(raced)
                return replace(raced, reused=True)
        return request

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        request_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeApprovalRequest:
        self._require_enterprise_human(actor)
        request = await self._repository.get(request_id=request_id)
        if request is None or request.source_record_id != record_id:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        self._verify_request(request)
        if (
            request.organization_id != actor.organization_id
            or request.environment_id != self._environment_id
        ):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_request_not_found")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=UPGRADE_APPROVAL_READ_PERMISSION,
            result_code="connector_upgrade_approval_request_read",
            request=request,
            idempotency_key=None,
        )
        return request

    async def close(self) -> None:
        await self._repository.close()

    async def _active_policy(
        self, *, actor: AuthenticatedSubject, now: datetime
    ) -> ConnectorUpgradeApprovalPolicySnapshot:
        policies = await self._policy_source.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        active: list[ConnectorUpgradeApprovalPolicySnapshot] = []
        for policy in policies:
            self._verify_policy(policy)
            if policy.issued_at <= now < policy.expires_at:
                active.append(policy)
        if len(active) != 1:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_policy_unavailable")
        policy = active[0]
        if not self._assurance_satisfies(actor.assurance_level, policy.required_assurance_level):
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_assurance_insufficient")
        return policy

    def _reuse(
        self,
        request: ConnectorUpgradeApprovalRequest,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorUpgradeApprovalRequest:
        if request.requested_by != actor.subject_id or request.request_fingerprint != fingerprint:
            raise ConnectorUpgradeApprovalError("connector_upgrade_approval_idempotency_conflict")
        self._verify_request(request)
        return replace(request, reused=True)

    @classmethod
    def _verify_policy(cls, policy: ConnectorUpgradeApprovalPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_policy_integrity_failed"
            )

    @classmethod
    def _verify_request(cls, request: ConnectorUpgradeApprovalRequest) -> None:
        if cls._digest(cls._request_payload(request)) != request.canonical_digest:
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_request_integrity_failed"
            )

    @classmethod
    def _request_payload(cls, request: ConnectorUpgradeApprovalRequest) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(request))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        request: ConnectorUpgradeApprovalRequest,
        idempotency_key: str | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.upgrade-approval-request",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.connector.upgrade-approval-request",
                scope_reference=request.request_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("plan_id", request.plan_id),
                    ("candidate_receipt_id", request.candidate_receipt_id),
                ),
            )
        )

    @staticmethod
    def _assurance_satisfies(actual: AssuranceLevel, required: AssuranceLevel) -> bool:
        order = {
            AssuranceLevel.DEVELOPMENT: 0,
            AssuranceLevel.SINGLE_FACTOR: 1,
            AssuranceLevel.MULTI_FACTOR: 2,
            AssuranceLevel.HARDWARE_BACKED: 3,
        }
        return order[actual] >= order[required]

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise ConnectorUpgradeApprovalError(
                "connector_upgrade_approval_enterprise_human_mfa_required"
            )

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()


def build_development_connector_upgrade_approval_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorUpgradeApprovalPolicySnapshot:
    policy = ConnectorUpgradeApprovalPolicySnapshot(
        policy_id="connector-upgrade-approval-policy.development",
        schema_version=UPGRADE_APPROVAL_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        request_lifetime_minutes=120,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        signed_by="subject.security-architecture",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=ConnectorUpgradeApprovalService._digest(
            ConnectorUpgradeApprovalService._normalize(payload)
        ),
    )
