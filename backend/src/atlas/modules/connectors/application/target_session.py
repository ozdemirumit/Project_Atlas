from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
)
from atlas.modules.connectors.application.target_session_ports import (
    ConnectorTargetSessionAdapter,
    ConnectorTargetSessionError,
    ConnectorTargetSessionPolicySource,
    ConnectorTargetSessionProfileSource,
    ConnectorTargetSessionRepository,
    ConnectorTargetSessionSource,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.credential_assignment import ConnectorCredentialProfileSnapshot
from atlas.modules.connectors.domain.runtime_activation import (
    ENABLED_RUNTIME_HEALTHY,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.connectors.domain.target_session import (
    ENABLED_TARGET_SESSION_VERIFIED,
    ConnectorTargetSessionClaim,
    ConnectorTargetSessionInstruction,
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionReceipt,
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

TARGET_SESSION_CREATE_PERMISSION = "connectors.target-session-verifications.create"
TARGET_SESSION_READ_PERMISSION = "connectors.target-session-verifications.read"
TARGET_SESSION_SCHEMA = "atlas.connector-target-session-verification.v1"
TARGET_SESSION_REQUIRED_AUDIT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class ConnectorTargetSessionOption:
    source_runtime_activation_id: str
    source_runtime_activation_digest: str
    package_digest: str
    session_profile_id: str
    session_profile_digest: str
    session_profile_expires_at: datetime
    expected_target_product: str
    protocol_classification: str
    connectivity_check_ids: tuple[str, ...]
    session_policy_id: str
    session_policy_digest: str
    session_policy_version: str
    session_policy_expires_at: datetime
    required_assurance_level: AssuranceLevel


class ConnectorTargetSessionService:
    def __init__(
        self,
        *,
        repository: ConnectorTargetSessionRepository,
        source: ConnectorTargetSessionSource,
        profile_source: ConnectorTargetSessionProfileSource,
        policy_source: ConnectorTargetSessionPolicySource,
        adapter: ConnectorTargetSessionAdapter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._profile_source = profile_source
        self._policy_source = policy_source
        self._adapter = adapter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorTargetSessionRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_activation_id: str,
        source_runtime_activation_digest: str,
        package_digest: str,
        session_profile_id: str,
        session_profile_digest: str,
        session_policy_id: str,
        session_policy_digest: str,
        purpose: str,
        bounded_session_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorTargetSessionVerificationRecord:
        self._require_enterprise_human(actor)
        if not bounded_session_acknowledged:
            raise ConnectorTargetSessionError("target_session_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorTargetSessionError("target_session_request_invalid")
        (
            activation,
            brokerage,
            runtime_trust,
            credential_profile,
            source_actors,
        ) = await self._source_in_scope(
            actor=actor,
            source_runtime_activation_id=source_runtime_activation_id,
        )
        fingerprint = self._digest(
            {
                "source_runtime_activation_id": source_runtime_activation_id,
                "source_runtime_activation_digest": source_runtime_activation_digest,
                "package_digest": package_digest,
                "session_profile_id": session_profile_id,
                "session_profile_digest": session_profile_digest,
                "session_policy_id": session_policy_id,
                "session_policy_digest": session_policy_digest,
                "purpose": purpose,
            }
        )
        actor_digest = self._identifier_digest(actor.subject_id)
        idempotency_digest = self._digest(
            [
                activation.organization_id,
                activation.environment_id,
                actor.subject_id,
                idempotency_key,
            ]
        )
        replay_digest = self._digest(
            [
                activation.organization_id,
                activation.environment_id,
                actor_digest,
                idempotency_digest,
                fingerprint,
            ]
        )
        existing = await self._repository.get_by_create_key_in_scope(
            verified_by=actor.subject_id,
            idempotency_key=idempotency_key,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if existing is not None:
            return self._reuse(await self._current_record(existing), actor, replay_digest)
        profile = await self._profile_source.get_by_id_in_scope(
            profile_id=session_profile_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=session_policy_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
        )
        if profile is None or policy is None:
            raise ConnectorTargetSessionError("target_session_evidence_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._verify_session(
            actor=actor,
            activation=activation,
            brokerage=brokerage,
            runtime_trust=runtime_trust,
            credential_profile=credential_profile,
            profile=profile,
            policy=policy,
            source_digest=source_runtime_activation_digest,
            package_digest=package_digest,
            profile_digest=session_profile_digest,
            policy_digest=session_policy_digest,
            now=self._clock(),
        )
        if actor.subject_id in (
            source_actors
            | {profile.signed_by, policy.signed_by, profile.session_adapter_attestor_id}
        ):
            raise ConnectorTargetSessionError("target_session_separation_required")

        seed = self._digest(
            [activation.activation_id, profile.profile_id, profile.canonical_digest]
        )
        verification_id = f"connector-target-session-verification.{seed[:24]}"
        verification_attempt_id = f"connector-target-session-attempt.{uuid4().hex}"
        instruction = ConnectorTargetSessionInstruction(
            verification_id=verification_id,
            verification_attempt_id=verification_attempt_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
            source_runtime_activation_id=activation.activation_id,
            source_runtime_activation_digest=activation.canonical_digest,
            package_digest=activation.package_digest,
            session_profile_digest=profile.canonical_digest,
            session_policy_digest=policy.canonical_digest,
            session_adapter_id=profile.session_adapter_id,
            expected_target_identity_digest=profile.expected_target_identity_digest,
            protocol_classification=profile.protocol_classification,
            session_timeout_seconds=profile.session_timeout_seconds,
            connectivity_check_ids=profile.connectivity_check_ids,
        )
        claim_now = self._clock()
        claim = ConnectorTargetSessionClaim(
            verification_attempt_id=verification_attempt_id,
            verification_id=verification_id,
            source_runtime_activation_id=activation.activation_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
            verified_by_digest=actor_digest,
            idempotency_digest=idempotency_digest,
            replay_digest=replay_digest,
            claimed_at=claim_now,
            expires_at=claim_now
            + timedelta(seconds=max(profile.session_timeout_seconds + 60, 600)),
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        async with self._mutation_lock:
            prior = await self._repository.get_by_runtime_activation_in_scope(
                source_runtime_activation_id=activation.activation_id,
                organization_id=activation.organization_id,
                environment_id=activation.environment_id,
            )
            if prior is not None:
                if prior.verified_by == actor.subject_id and prior.replay_digest == replay_digest:
                    return replace(await self._current_record(prior), reused=True)
                raise ConnectorTargetSessionError("target_session_source_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_target_session_requested",
                activation.instance_id,
                idempotency_digest,
                (("session_profile_digest", profile.canonical_digest),),
            )
            try:
                claimed = await self._repository.claim(claim)
            except Exception as error:
                await self._audit_required_failure(
                    actor,
                    correlation_id,
                    "connector_target_session_claim_uncertain",
                    verification_id,
                    "claim_outcome_uncertain",
                )
                raise ConnectorTargetSessionError(
                    "target_session_claim_outcome_uncertain"
                ) from error
            if not claimed:
                stale_claim = await self._repository.get_claim_by_source_in_scope(
                    source_runtime_activation_id=activation.activation_id,
                    organization_id=activation.organization_id,
                    environment_id=activation.environment_id,
                )
                if stale_claim is not None and stale_claim.expires_at <= self._clock():
                    try:
                        recovery_fenced = await self._repository.fence_expired_claim(
                            claim=stale_claim,
                            recovery_attempt_id=verification_attempt_id,
                            now=self._clock(),
                        )
                    except Exception as error:
                        await self._audit_required_failure(
                            actor,
                            correlation_id,
                            "connector_target_session_stale_recovery_failed",
                            stale_claim.verification_id,
                            "recovery_fence_uncertain",
                        )
                        raise ConnectorTargetSessionError(
                            "target_session_stale_claim_recovery_failed"
                        ) from error
                    if recovery_fenced:
                        try:
                            await self._compensate(
                                stale_claim.verification_attempt_id,
                                timeout_seconds=profile.session_timeout_seconds,
                            )
                            await asyncio.wait_for(
                                self._audit(
                                    actor,
                                    correlation_id,
                                    "connector_target_session_stale_claim_recovered",
                                    stale_claim.verification_id,
                                    None,
                                    (),
                                ),
                                timeout=TARGET_SESSION_REQUIRED_AUDIT_TIMEOUT_SECONDS,
                            )
                            released = await self._repository.release_claim(
                                stale_claim,
                                now=self._clock(),
                                recovery_attempt_id=verification_attempt_id,
                            )
                            if not released:
                                raise ConnectorTargetSessionError(
                                    "target_session_stale_claim_release_conflict"
                                )
                            claimed = await self._repository.claim(claim)
                        except Exception as error:
                            await self._audit_required_failure(
                                actor,
                                correlation_id,
                                "connector_target_session_stale_recovery_failed",
                                stale_claim.verification_id,
                                "recovery_operation_failed",
                            )
                            if isinstance(error, ConnectorTargetSessionError):
                                raise
                            raise ConnectorTargetSessionError(
                                "target_session_stale_claim_recovery_failed"
                            ) from error
            if not claimed:
                raced = await self._repository.get_by_create_key_in_scope(
                    verified_by=actor.subject_id,
                    idempotency_key=idempotency_key,
                    organization_id=activation.organization_id,
                    environment_id=activation.environment_id,
                )
                if raced is not None and raced.replay_digest == replay_digest:
                    return replace(await self._current_record(raced), reused=True)
                prior = await self._repository.get_by_runtime_activation_in_scope(
                    source_runtime_activation_id=activation.activation_id,
                    organization_id=activation.organization_id,
                    environment_id=activation.environment_id,
                )
                if prior is not None:
                    raise ConnectorTargetSessionError("target_session_source_conflict")
                raise ConnectorTargetSessionError("target_session_in_progress")
            try:
                attempt_started_at = self._clock()
                try:
                    receipt = await asyncio.wait_for(
                        self._adapter.verify(instruction),
                        timeout=profile.session_timeout_seconds,
                    )
                except TimeoutError as error:
                    raise ConnectorTargetSessionError("target_session_adapter_timeout") from error
                self._verify_receipt(
                    receipt,
                    instruction,
                    profile,
                    policy,
                    attempt_started_at=attempt_started_at,
                    now=self._clock(),
                )
                record = self._record(
                    activation=activation,
                    runtime_trust=runtime_trust,
                    profile=profile,
                    policy=policy,
                    receipt=receipt,
                    actor=actor,
                    purpose=purpose,
                    replay_digest=replay_digest,
                    idempotency_digest=idempotency_digest,
                )
                try:
                    await asyncio.wait_for(
                        self._audit(
                            actor,
                            correlation_id,
                            "connector_target_session_completed",
                            record.verification_id,
                            idempotency_digest,
                            (("instance_state", record.instance_state),),
                        ),
                        timeout=TARGET_SESSION_REQUIRED_AUDIT_TIMEOUT_SECONDS,
                    )
                except Exception as audit_error:
                    raise ConnectorTargetSessionError(
                        "target_session_completion_audit_failed"
                    ) from audit_error
            except Exception as error:
                failure_class = (
                    str(error)
                    if isinstance(error, ConnectorTargetSessionError)
                    else "unexpected_target_session_failure"
                )
                try:
                    await self._compensate(
                        verification_attempt_id,
                        timeout_seconds=profile.session_timeout_seconds,
                    )
                except Exception as compensation_error:
                    await self._audit_required_failure(
                        actor,
                        correlation_id,
                        "connector_target_session_compensation_failed",
                        verification_id,
                        failure_class,
                    )
                    raise ConnectorTargetSessionError(
                        "target_session_compensation_failed"
                    ) from compensation_error
                await self._audit_required_failure(
                    actor,
                    correlation_id,
                    "connector_target_session_failed",
                    verification_id,
                    failure_class,
                )
                released = await self._repository.release_claim(claim, now=self._clock())
                if not released:
                    raise ConnectorTargetSessionError(
                        "target_session_claim_release_conflict"
                    ) from error
                if isinstance(error, ConnectorTargetSessionError):
                    raise
                raise ConnectorTargetSessionError("target_session_failed") from error
            try:
                published = await self._repository.publish(
                    claim=claim,
                    record=record,
                    now=self._clock(),
                )
            except Exception as error:
                await self._audit_required_failure(
                    actor,
                    correlation_id,
                    "connector_target_session_persistence_uncertain",
                    verification_id,
                    "persistence_outcome_uncertain",
                )
                raise ConnectorTargetSessionError(
                    "target_session_persistence_outcome_uncertain"
                ) from error
            if not published:
                try:
                    await self._compensate(
                        verification_attempt_id,
                        timeout_seconds=profile.session_timeout_seconds,
                    )
                except Exception as compensation_error:
                    await self._audit_required_failure(
                        actor,
                        correlation_id,
                        "connector_target_session_compensation_failed",
                        verification_id,
                        "publish_rejected",
                    )
                    raise ConnectorTargetSessionError(
                        "target_session_compensation_failed"
                    ) from compensation_error
                await self._audit_required_failure(
                    actor,
                    correlation_id,
                    "connector_target_session_publish_rejected",
                    verification_id,
                    "publish_rejected",
                )
                released = await self._repository.release_claim(claim, now=self._clock())
                if not released:
                    raise ConnectorTargetSessionError("target_session_claim_release_conflict")
                raced = await self._repository.get_by_create_key_in_scope(
                    verified_by=actor.subject_id,
                    idempotency_key=idempotency_key,
                    organization_id=actor.organization_id,
                    environment_id=self._environment_id,
                )
                if raced is None or raced.replay_digest != replay_digest:
                    raise ConnectorTargetSessionError("target_session_record_conflict")
                return replace(await self._current_record(raced), reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, verification_id: str, correlation_id: str
    ) -> ConnectorTargetSessionVerificationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get_in_scope(
            verification_id=verification_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if record is None:
            raise ConnectorTargetSessionError("target_session_record_not_found")
        record = await self._current_record(record)
        await self._audit(
            actor,
            correlation_id,
            "connector_target_session_read",
            record.verification_id,
            None,
            (),
            permission_id=TARGET_SESSION_READ_PERMISSION,
        )
        return record

    async def list_verifications(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_activation_id: str | None,
        correlation_id: str,
    ) -> tuple[ConnectorTargetSessionVerificationRecord, ...]:
        self._require_enterprise_human(actor)
        if source_runtime_activation_id is None:
            candidates = await self._repository.list_scope(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        else:
            candidate = await self._repository.get_by_runtime_activation_in_scope(
                source_runtime_activation_id=source_runtime_activation_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            candidates = (candidate,) if candidate is not None else ()
        visible = [await self._current_record(record) for record in candidates]
        visible.sort(key=lambda item: item.verification_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_target_sessions_listed",
            source_runtime_activation_id or self._environment_id,
            None,
            (("count", str(len(visible))),),
            permission_id=TARGET_SESSION_READ_PERMISSION,
        )
        return tuple(visible)

    async def list_options(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_activation_id: str,
        correlation_id: str,
    ) -> tuple[ConnectorTargetSessionOption, ...]:
        self._require_enterprise_human(actor)
        (
            activation,
            brokerage,
            runtime_trust,
            credential_profile,
            source_actors,
        ) = await self._source_in_scope(
            actor=actor,
            source_runtime_activation_id=source_runtime_activation_id,
        )
        existing = await self._repository.get_by_runtime_activation_in_scope(
            source_runtime_activation_id=activation.activation_id,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
        )
        options: list[ConnectorTargetSessionOption] = []
        if existing is not None:
            await self._current_record(existing)
        else:
            profiles = await self._profile_source.list_scope(
                organization_id=activation.organization_id,
                environment_id=activation.environment_id,
            )
            policies = await self._policy_source.list_scope(
                organization_id=activation.organization_id,
                environment_id=activation.environment_id,
            )
            now = self._clock()
            for profile in profiles:
                for policy in policies:
                    try:
                        self._verify_snapshot(profile, "profile")
                        self._verify_snapshot(policy, "policy")
                        self._verify_session(
                            actor=actor,
                            activation=activation,
                            brokerage=brokerage,
                            runtime_trust=runtime_trust,
                            credential_profile=credential_profile,
                            profile=profile,
                            policy=policy,
                            source_digest=activation.canonical_digest,
                            package_digest=activation.package_digest,
                            profile_digest=profile.canonical_digest,
                            policy_digest=policy.canonical_digest,
                            now=now,
                        )
                    except ConnectorTargetSessionError:
                        continue
                    if actor.subject_id in (
                        source_actors
                        | {
                            profile.signed_by,
                            policy.signed_by,
                            profile.session_adapter_attestor_id,
                        }
                    ):
                        continue
                    options.append(
                        ConnectorTargetSessionOption(
                            source_runtime_activation_id=activation.activation_id,
                            source_runtime_activation_digest=activation.canonical_digest,
                            package_digest=activation.package_digest,
                            session_profile_id=profile.profile_id,
                            session_profile_digest=profile.canonical_digest,
                            session_profile_expires_at=profile.expires_at,
                            expected_target_product=profile.expected_target_product,
                            protocol_classification=profile.protocol_classification,
                            connectivity_check_ids=profile.connectivity_check_ids,
                            session_policy_id=policy.policy_id,
                            session_policy_digest=policy.canonical_digest,
                            session_policy_version=policy.policy_version,
                            session_policy_expires_at=policy.expires_at,
                            required_assurance_level=policy.required_assurance_level,
                        )
                    )
        options.sort(
            key=lambda item: (
                item.session_profile_id,
                item.session_profile_digest,
                item.session_policy_id,
                item.session_policy_digest,
            )
        )
        await self._audit(
            actor,
            correlation_id,
            "connector_target_session_options_listed",
            activation.instance_id,
            None,
            (("count", str(len(options))),),
            permission_id=TARGET_SESSION_READ_PERMISSION,
        )
        return tuple(options)

    async def _source_in_scope(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_activation_id: str,
    ) -> tuple[
        ConnectorRuntimeActivationRecord,
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]:
        scoped = await self._source.repository.get_in_scope(
            activation_id=source_runtime_activation_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if scoped is None:
            raise ConnectorTargetSessionError("target_session_source_not_found")
        try:
            source = await self._source.target_session_source(
                activation_id=source_runtime_activation_id
            )
        except ConnectorRuntimeActivationError as error:
            raise ConnectorTargetSessionError("target_session_source_not_found") from error
        activation = source[0]
        if (
            activation.activation_id != scoped.activation_id
            or activation.canonical_digest != scoped.canonical_digest
            or activation.organization_id != actor.organization_id
            or activation.environment_id != self._environment_id
        ):
            raise ConnectorTargetSessionError("target_session_source_not_found")
        return source

    async def _current_record(
        self, record: ConnectorTargetSessionVerificationRecord
    ) -> ConnectorTargetSessionVerificationRecord:
        self._verify_record(record)
        scoped = await self._source.repository.get_in_scope(
            activation_id=record.source_runtime_activation_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if scoped is None:
            raise ConnectorTargetSessionError("target_session_source_invalid")
        try:
            (
                activation,
                brokerage,
                runtime_trust,
                credential_profile,
                _,
            ) = await self._source.target_session_source(
                activation_id=record.source_runtime_activation_id
            )
        except ConnectorRuntimeActivationError as error:
            raise ConnectorTargetSessionError("target_session_source_invalid") from error
        if (
            activation.activation_id != scoped.activation_id
            or activation.canonical_digest != scoped.canonical_digest
        ):
            raise ConnectorTargetSessionError("target_session_source_invalid")
        profile = await self._profile_source.get_by_id_in_scope(
            profile_id=record.session_profile_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=record.session_policy_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if profile is None or policy is None:
            raise ConnectorTargetSessionError("target_session_source_invalid")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        now = self._clock()
        self._verify_session(
            actor=None,
            activation=activation,
            brokerage=brokerage,
            runtime_trust=runtime_trust,
            credential_profile=credential_profile,
            profile=profile,
            policy=policy,
            source_digest=record.source_runtime_activation_digest,
            package_digest=record.package_digest,
            profile_digest=record.session_profile_digest,
            policy_digest=record.session_policy_digest,
            now=now,
        )
        expected_checks = tuple(
            (check_id, "connectivity.passed") for check_id in profile.connectivity_check_ids
        )
        actual_checks = tuple(
            (item.check_id, item.outcome) for item in record.connectivity_check_results
        )
        if (
            record.organization_id != activation.organization_id
            or record.environment_id != activation.environment_id
            or record.connector_id != activation.connector_id
            or record.release_version != activation.release_version
            or record.manifest_digest != activation.manifest_digest
            or record.instance_id != activation.instance_id
            or record.target_profile_digest != runtime_trust.target_profile_digest
            or record.target_identity_digest != profile.expected_target_identity_digest
            or record.expected_target_product != profile.expected_target_product
            or record.protocol_classification != profile.protocol_classification
            or record.tls_classification != policy.required_tls_classification
            or record.session_profile_digest != profile.canonical_digest
            or record.session_policy_digest != policy.canonical_digest
            or record.session_policy_version != policy.policy_version
            or record.session_adapter_id != profile.session_adapter_id
            or actual_checks != expected_checks
            or record.verified_at < profile.issued_at
            or record.verified_at > now
            or record.instance_state != ENABLED_TARGET_SESSION_VERIFIED
            or not record.runtime_health_verified
            or not record.secret_brokerage_governed
            or not record.target_connection_authorized
            or not record.target_connectivity_verified
            or not record.target_identity_verified
            or not record.read_only_session_verified
            or not record.target_session_established
            or not record.target_session_closed
            or not record.delivery_channel_closed
            or not record.lease_revocation_confirmed
            or not record.eligible_for_capability_invocation_governance
            or record.target_connected
            or record.capability_invocation_authorized
            or record.capability_invoked
            or record.scheduled
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise ConnectorTargetSessionError("target_session_source_invalid")
        return record

    async def close(self) -> None:
        await self._repository.close()

    async def capability_invocation_authorization_source(
        self,
        *,
        verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        ConnectorTargetSessionVerificationRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]:
        record = await self._repository.get_in_scope(
            verification_id=verification_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if record is None:
            raise ConnectorTargetSessionError("target_session_record_not_found")
        record = await self._current_record(record)
        activation, enablement, actors = await self._source.capability_invocation_source(
            activation_id=record.source_runtime_activation_id
        )
        if (
            record.source_runtime_activation_digest != activation.canonical_digest
            or record.package_digest != enablement.package_digest
            or record.instance_id != enablement.instance_id
            or record.target_profile_digest != enablement.target_profile_digest
            or record.instance_state != ENABLED_TARGET_SESSION_VERIFIED
            or not record.eligible_for_capability_invocation_governance
            or record.target_connected
            or record.capability_invocation_authorized
            or record.capability_invoked
            or record.scheduled
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise ConnectorTargetSessionError("target_session_invocation_invalid")
        return record, enablement, frozenset(actors | {record.verified_by})

    def _record(
        self,
        *,
        activation: ConnectorRuntimeActivationRecord,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        profile: ConnectorTargetSessionProfileSnapshot,
        policy: ConnectorTargetSessionPolicySnapshot,
        receipt: ConnectorTargetSessionReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
        replay_digest: str,
        idempotency_digest: str,
    ) -> ConnectorTargetSessionVerificationRecord:
        record = ConnectorTargetSessionVerificationRecord(
            verification_id=receipt.verification_id,
            verification_attempt_id=receipt.verification_attempt_id,
            schema_version=TARGET_SESSION_SCHEMA,
            version=1,
            source_runtime_activation_id=activation.activation_id,
            source_runtime_activation_digest=activation.canonical_digest,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
            package_digest=activation.package_digest,
            connector_id=activation.connector_id,
            release_version=activation.release_version,
            manifest_digest=activation.manifest_digest,
            instance_id=activation.instance_id,
            instance_key=activation.instance_key,
            display_name=activation.display_name,
            target_profile_digest=runtime_trust.target_profile_digest,
            target_identity_digest=receipt.target_identity_digest,
            expected_target_product=profile.expected_target_product,
            protocol_classification=receipt.protocol_classification,
            tls_classification=receipt.tls_classification,
            session_profile_id=profile.profile_id,
            session_profile_digest=profile.canonical_digest,
            session_policy_id=policy.policy_id,
            session_policy_digest=policy.canonical_digest,
            session_policy_version=policy.policy_version,
            session_adapter_id=profile.session_adapter_id,
            connectivity_check_results=receipt.connectivity_check_results,
            instance_state=ENABLED_TARGET_SESSION_VERIFIED,
            verified_by=actor.subject_id,
            purpose=purpose,
            verified_at=receipt.verified_at,
            canonical_digest="0" * 64,
            replay_digest=replay_digest,
            idempotency_digest=idempotency_digest,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    @staticmethod
    def _verify_session(
        *,
        actor: AuthenticatedSubject | None,
        activation: ConnectorRuntimeActivationRecord,
        brokerage: ConnectorSecretBrokerageAuthorizationRecord,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        credential_profile: ConnectorCredentialProfileSnapshot,
        profile: ConnectorTargetSessionProfileSnapshot,
        policy: ConnectorTargetSessionPolicySnapshot,
        source_digest: str,
        package_digest: str,
        profile_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        expected_identity = ConnectorTargetSessionService._digest(
            [runtime_trust.target_profile_digest, runtime_trust.target_product]
        )
        if (
            activation.canonical_digest != source_digest
            or activation.package_digest != package_digest
            or profile.canonical_digest != profile_digest
            or policy.canonical_digest != policy_digest
            or policy.required_activation_schema != activation.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.verification_schema != TARGET_SESSION_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or profile.organization_id != activation.organization_id
            or profile.environment_id != activation.environment_id
            or policy.organization_id != activation.organization_id
            or policy.environment_id != activation.environment_id
            or profile.package_digest != activation.package_digest
            or profile.connector_id != activation.connector_id
            or profile.release_version != activation.release_version
            or profile.manifest_digest != activation.manifest_digest
            or profile.instance_id != activation.instance_id
            or profile.source_runtime_activation_digest != activation.canonical_digest
            or profile.target_profile_digest != runtime_trust.target_profile_digest
            or profile.expected_target_product != runtime_trust.target_product
            or profile.expected_target_identity_digest != expected_identity
            or profile.tls_policy_digest
            != ConnectorTargetSessionService._identifier_digest("tls-policy.enterprise-validated")
            or profile.certificate_policy_digest
            != ConnectorTargetSessionService._identifier_digest(
                "certificate-policy.trusted-chain-and-identity"
            )
            or profile.network_path_policy_digest
            != ConnectorTargetSessionService._identifier_digest(runtime_trust.egress_policy_id)
            or profile.workload_identity_digest != activation.workload_identity_digest
            or profile.credential_profile_digest != brokerage.credential_profile_digest
            or profile.delivery_policy_id != brokerage.delivery_policy_id
            or profile.lease_policy_id != brokerage.lease_policy_id
            or profile.session_adapter_id not in policy.allowed_session_adapter_ids
            or profile.session_adapter_attestor_id != policy.required_session_adapter_attestor_id
            or profile.protocol_classification != policy.required_protocol_classification
            or policy.required_source_state != ENABLED_RUNTIME_HEALTHY
            or profile.delivery_policy_id != policy.required_delivery_policy_id
            or profile.lease_policy_id != policy.required_lease_policy_id
            or profile.session_timeout_seconds > policy.maximum_session_timeout_seconds
            or profile.connectivity_check_ids != policy.required_connectivity_check_ids
            or credential_profile.canonical_digest != brokerage.credential_profile_digest
            or credential_profile.rotation_state != brokerage.rotation_state
            or credential_profile.revocation_state != brokerage.revocation_state
            or credential_profile.next_rotation_at != brokerage.next_rotation_at
            or credential_profile.privilege_class != "privilege.read-only"
            or activation.instance_state != ENABLED_RUNTIME_HEALTHY
            or not activation.runtime_health_verified
            or not activation.eligible_for_target_session_authorization
            or activation.target_connected
            or activation.target_connection_authorized
            or activation.capability_invocation_authorized
            or activation.capability_invoked
            or activation.execution_authorized
            or activation.deployment_approved
            or activation.infrastructure_mutation_performed
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - activation.healthy_at > timedelta(hours=policy.maximum_activation_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or (
                actor is not None
                and not assurance_satisfies_policy(
                    actor.assurance_level, policy.required_assurance_level
                )
            )
        ):
            raise ConnectorTargetSessionError("target_session_invalid")

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorTargetSessionProfileSnapshot | ConnectorTargetSessionPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorTargetSessionError(f"target_session_{kind}_integrity_failed")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ConnectorTargetSessionReceipt,
        instruction: ConnectorTargetSessionInstruction,
        profile: ConnectorTargetSessionProfileSnapshot,
        policy: ConnectorTargetSessionPolicySnapshot,
        *,
        attempt_started_at: datetime,
        now: datetime,
    ) -> None:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest")
        if (
            cls._digest(cls._normalize(payload)) != receipt.canonical_digest
            or receipt.verification_id != instruction.verification_id
            or receipt.verification_attempt_id != instruction.verification_attempt_id
            or receipt.organization_id != instruction.organization_id
            or receipt.environment_id != instruction.environment_id
            or receipt.source_runtime_activation_digest
            != instruction.source_runtime_activation_digest
            or receipt.package_digest != instruction.package_digest
            or receipt.session_profile_digest != instruction.session_profile_digest
            or receipt.session_policy_digest != instruction.session_policy_digest
            or receipt.session_adapter_id != instruction.session_adapter_id
            or receipt.target_identity_digest != profile.expected_target_identity_digest
            or receipt.protocol_classification != profile.protocol_classification
            or receipt.tls_classification != policy.required_tls_classification
            or tuple(item.check_id for item in receipt.connectivity_check_results)
            != instruction.connectivity_check_ids
            or receipt.signed_by != profile.session_adapter_attestor_id
            or receipt.verified_at < attempt_started_at
            or receipt.verified_at > now + timedelta(seconds=5)
            or receipt.verified_at - attempt_started_at
            > timedelta(seconds=profile.session_timeout_seconds)
            or not profile.issued_at <= receipt.verified_at < profile.expires_at
            or not policy.issued_at <= receipt.verified_at < policy.expires_at
        ):
            raise ConnectorTargetSessionError("target_session_receipt_invalid")

    def _reuse(
        self,
        record: ConnectorTargetSessionVerificationRecord,
        actor: AuthenticatedSubject,
        replay_digest: str,
    ) -> ConnectorTargetSessionVerificationRecord:
        if record.verified_by != actor.subject_id or record.replay_digest != replay_digest:
            raise ConnectorTargetSessionError("target_session_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    async def _compensate(
        self,
        verification_attempt_id: str,
        *,
        timeout_seconds: int,
    ) -> None:
        await asyncio.wait_for(
            self._adapter.compensate(verification_attempt_id=verification_attempt_id),
            timeout=timeout_seconds,
        )

    @classmethod
    def _verify_record(cls, record: ConnectorTargetSessionVerificationRecord) -> None:
        if cls._digest(cls._record_payload(record)) == record.canonical_digest:
            return
        expected_legacy_attempt = (
            "connector-target-session-attempt.legacy-"
            f"{cls._identifier_digest(record.verification_id)[:24]}"
        )
        if record.verification_attempt_id == expected_legacy_attempt:
            legacy_payload = cls._record_payload(record)
            legacy_payload.pop("verification_attempt_id")
            if cls._digest(legacy_payload) == record.canonical_digest:
                return
        raise ConnectorTargetSessionError("target_session_record_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ConnectorTargetSessionVerificationRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "replay_digest", "idempotency_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(cls, claim: ConnectorTargetSessionClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

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

    @staticmethod
    def _identifier_digest(value: str) -> str:
        return sha256(value.encode("ascii")).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorTargetSessionError("target_session_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorTargetSessionError("target_session_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = TARGET_SESSION_CREATE_PERMISSION,
        outcome: str = "succeeded",
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.target-session",
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
                resource_type="resource.connector.target-session-verification",
                scope_reference=scope_reference,
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )

    async def _audit_required_failure(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        failure_class: str,
    ) -> None:
        try:
            await asyncio.wait_for(
                self._audit(
                    actor,
                    correlation_id,
                    result_code,
                    scope_reference,
                    None,
                    (("failure_class", failure_class),),
                    outcome="failed",
                ),
                timeout=TARGET_SESSION_REQUIRED_AUDIT_TIMEOUT_SECONDS,
            )
        except Exception as audit_error:
            raise ConnectorTargetSessionError(
                "target_session_failure_audit_failed"
            ) from audit_error


def _signed_snapshot(
    snapshot: ConnectorTargetSessionProfileSnapshot | ConnectorTargetSessionPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorTargetSessionService._digest(ConnectorTargetSessionService._normalize(payload))


def build_connector_target_session_profile(
    *,
    activation: ConnectorRuntimeActivationRecord,
    brokerage: ConnectorSecretBrokerageAuthorizationRecord,
    runtime_trust: ConnectorRuntimeTrustGrantRecord,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorTargetSessionProfileSnapshot:
    target_identity_digest = ConnectorTargetSessionService._digest(
        [runtime_trust.target_profile_digest, runtime_trust.target_product]
    )
    snapshot = ConnectorTargetSessionProfileSnapshot(
        profile_id="connector-target-session-profile.development-synthetic",
        schema_version="atlas.connector-target-session-profile.v1",
        version=1,
        organization_id=activation.organization_id,
        environment_id=activation.environment_id,
        package_digest=activation.package_digest,
        connector_id=activation.connector_id,
        release_version=activation.release_version,
        manifest_digest=activation.manifest_digest,
        instance_id=activation.instance_id,
        source_runtime_activation_digest=activation.canonical_digest,
        target_profile_digest=runtime_trust.target_profile_digest,
        expected_target_product=runtime_trust.target_product,
        expected_target_identity_digest=target_identity_digest,
        protocol_classification="protocol.https-read-only",
        tls_policy_digest=ConnectorTargetSessionService._identifier_digest(
            "tls-policy.enterprise-validated"
        ),
        certificate_policy_digest=ConnectorTargetSessionService._identifier_digest(
            "certificate-policy.trusted-chain-and-identity"
        ),
        network_path_policy_digest=ConnectorTargetSessionService._identifier_digest(
            runtime_trust.egress_policy_id
        ),
        workload_identity_digest=activation.workload_identity_digest,
        credential_profile_digest=brokerage.credential_profile_digest,
        delivery_policy_id=brokerage.delivery_policy_id,
        lease_policy_id=brokerage.lease_policy_id,
        session_adapter_id="connector-target-session-adapter.synthetic",
        session_adapter_attestor_id="subject.connector-target-session-adapter-attestor",
        session_timeout_seconds=30,
        connectivity_check_ids=(
            "connectivity.authentication",
            "connectivity.read-only-privilege",
            "connectivity.target-identity",
            "connectivity.tls",
        ),
        signed_by="subject.connector-target-session-profile-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_target_session_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorTargetSessionPolicySnapshot:
    snapshot = ConnectorTargetSessionPolicySnapshot(
        policy_id="connector-target-session-policy.development",
        schema_version="atlas.connector-target-session-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_activation_schema="atlas.connector-runtime-activation.v1",
        required_profile_schema="atlas.connector-target-session-profile.v1",
        required_profile_signer_id="subject.connector-target-session-profile-signer",
        allowed_session_adapter_ids=("connector-target-session-adapter.synthetic",),
        required_session_adapter_attestor_id=("subject.connector-target-session-adapter-attestor"),
        required_protocol_classification="protocol.https-read-only",
        required_tls_classification="tls.1-3-verified",
        required_delivery_policy_id="secret-delivery-policy.ephemeral-disabled-until-brokered",
        required_lease_policy_id="secret-lease-policy.single-use-non-renewable",
        maximum_session_timeout_seconds=60,
        required_connectivity_check_ids=(
            "connectivity.authentication",
            "connectivity.read-only-privilege",
            "connectivity.target-identity",
            "connectivity.tls",
        ),
        maximum_activation_age_hours=24,
        maximum_profile_age_hours=24,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_source_state=ENABLED_RUNTIME_HEALTHY,
        verification_schema=TARGET_SESSION_SCHEMA,
        signed_by="subject.connector-target-session-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
