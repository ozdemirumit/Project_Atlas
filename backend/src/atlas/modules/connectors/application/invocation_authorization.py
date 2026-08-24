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
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorCapabilityPermissionAuthorizer,
    ConnectorInvocationAuthorizationError,
    ConnectorInvocationAuthorizationPolicySource,
    ConnectorInvocationAuthorizationRepository,
    ConnectorInvocationAuthorizationSource,
    ConnectorInvocationEvidencePreparer,
    ConnectorInvocationInputEnvelopeSource,
    ConnectorInvocationProfileSource,
)
from atlas.modules.connectors.application.target_session_ports import ConnectorTargetSessionError
from atlas.modules.connectors.domain.capability_enablement import (
    ENABLED_CAPABILITIES_GOVERNED,
    ConnectorCapabilityEnablementRecord,
    ConnectorGovernedCapability,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ENABLED_CAPABILITY_INVOCATION_GOVERNED,
    ConnectorInvocationAuthorizationPolicySnapshot,
    ConnectorInvocationAuthorizationRecord,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationProfileSnapshot,
)
from atlas.modules.connectors.domain.target_session import (
    ENABLED_TARGET_SESSION_VERIFIED,
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

INVOCATION_AUTHORIZATION_CREATE_PERMISSION = "connectors.invocation-authorizations.create"
INVOCATION_AUTHORIZATION_READ_PERMISSION = "connectors.invocation-authorizations.read"
INVOCATION_AUTHORIZATION_SCHEMA = "atlas.connector-invocation-authorization.v1"
INVOCATION_AUTHORIZATION_REQUIRED_AUDIT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class ConnectorInvocationAuthorizationOption:
    source_target_session_verification_id: str
    source_target_session_digest: str
    package_digest: str
    capability_id: str
    capability_class: str
    required_permission: str
    invocation_profile_id: str
    invocation_profile_digest: str
    invocation_profile_expires_at: datetime
    input_envelope_id: str
    input_envelope_digest: str
    input_envelope_expires_at: datetime
    input_envelope_field_count: int
    authorization_policy_id: str
    authorization_policy_digest: str
    authorization_policy_version: str
    authorization_policy_expires_at: datetime
    required_assurance_level: AssuranceLevel
    maximum_timeout_seconds: int
    maximum_output_bytes: int


class ConnectorInvocationAuthorizationService:
    def __init__(
        self,
        *,
        repository: ConnectorInvocationAuthorizationRepository,
        source: ConnectorInvocationAuthorizationSource,
        profile_source: ConnectorInvocationProfileSource,
        envelope_source: ConnectorInvocationInputEnvelopeSource,
        policy_source: ConnectorInvocationAuthorizationPolicySource,
        evidence_preparer: ConnectorInvocationEvidencePreparer | None = None,
        permission_authorizer: ConnectorCapabilityPermissionAuthorizer,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._profile_source = profile_source
        self._envelope_source = envelope_source
        self._policy_source = policy_source
        self._evidence_preparer = evidence_preparer
        self._permission_authorizer = permission_authorizer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorInvocationAuthorizationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_target_session_verification_id: str,
        source_target_session_digest: str,
        package_digest: str,
        capability_id: str,
        invocation_profile_id: str,
        invocation_profile_digest: str,
        input_envelope_id: str,
        input_envelope_digest: str,
        authorization_policy_id: str,
        authorization_policy_digest: str,
        purpose: str,
        single_use_boundary_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorInvocationAuthorizationRecord:
        self._require_enterprise_human(actor)
        if not single_use_boundary_acknowledged:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_request_invalid")
        fingerprint = self._digest(
            {
                "source_target_session_verification_id": (source_target_session_verification_id),
                "source_target_session_digest": source_target_session_digest,
                "package_digest": package_digest,
                "capability_id": capability_id,
                "invocation_profile_id": invocation_profile_id,
                "invocation_profile_digest": invocation_profile_digest,
                "input_envelope_id": input_envelope_id,
                "input_envelope_digest": input_envelope_digest,
                "authorization_policy_id": authorization_policy_id,
                "authorization_policy_digest": authorization_policy_digest,
                "purpose": purpose,
            }
        )
        idempotency_digest = self._digest(
            [actor.organization_id, self._environment_id, actor.subject_id, idempotency_key]
        )
        replay_digest = self._digest(
            [
                actor.organization_id,
                self._environment_id,
                actor.subject_id,
                idempotency_digest,
                fingerprint,
            ]
        )
        existing = await self._repository.get_by_create_key_in_scope(
            authorized_by=actor.subject_id,
            idempotency_digest=idempotency_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if existing is not None:
            return self._reuse(existing, actor, replay_digest)
        source, enablement, source_actors = await self._source_in_scope(
            actor=actor,
            source_target_session_verification_id=source_target_session_verification_id,
        )
        profile = await self._profile_source.get_by_id_in_scope(
            profile_id=invocation_profile_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        envelope = await self._envelope_source.get_by_id_in_scope(
            envelope_id=input_envelope_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=authorization_policy_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        if profile is None or envelope is None or policy is None:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_evidence_not_found"
            )
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(envelope, "envelope")
        self._verify_snapshot(policy, "policy")
        self._require_scope(actor, source.organization_id, source.environment_id)
        capability = self._capability(enablement, capability_id)
        now = self._clock()
        self._verify_authorization(
            assurance_level=actor.assurance_level,
            source=source,
            enablement=enablement,
            capability=capability,
            profile=profile,
            envelope=envelope,
            policy=policy,
            source_digest=source_target_session_digest,
            package_digest=package_digest,
            profile_digest=invocation_profile_digest,
            envelope_digest=input_envelope_digest,
            policy_digest=authorization_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {
            profile.signed_by,
            envelope.signed_by,
            policy.signed_by,
        }:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            permission_id=capability.required_permission,
            capability_id=capability.capability_id,
            capability_class=capability.capability_class,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        async with self._mutation_lock:
            prior = await self._repository.get_by_target_session_in_scope(
                source_target_session_verification_id=source.verification_id,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            if prior is not None:
                if prior.authorized_by == actor.subject_id and prior.replay_digest == replay_digest:
                    return replace(await self._current_record(prior), reused=True)
                raise ConnectorInvocationAuthorizationError(
                    "invocation_authorization_source_conflict"
                )
            await self._audit_required(
                actor=actor,
                correlation_id=correlation_id,
                result_code="connector_invocation_authorization_requested",
                scope_reference=source.verification_id,
                idempotency_key=idempotency_key,
                metadata=(("capability_id", capability.capability_id),),
            )
            seed = self._digest(
                [
                    source.organization_id,
                    source.environment_id,
                    source.verification_id,
                    capability.capability_id,
                    envelope.canonical_digest,
                ]
            )
            record = ConnectorInvocationAuthorizationRecord(
                authorization_id=f"connector-invocation-authorization.{seed[:24]}",
                schema_version=INVOCATION_AUTHORIZATION_SCHEMA,
                version=1,
                source_target_session_verification_id=source.verification_id,
                source_target_session_digest=source.canonical_digest,
                organization_id=source.organization_id,
                environment_id=source.environment_id,
                package_digest=source.package_digest,
                connector_id=source.connector_id,
                release_version=source.release_version,
                manifest_digest=source.manifest_digest,
                instance_id=source.instance_id,
                instance_key=source.instance_key,
                display_name=source.display_name,
                target_profile_digest=source.target_profile_digest,
                target_identity_digest=source.target_identity_digest,
                capability_id=capability.capability_id,
                capability_class=capability.capability_class,
                required_permission=capability.required_permission,
                invocation_profile_id=profile.profile_id,
                invocation_profile_digest=profile.canonical_digest,
                input_envelope_id=envelope.envelope_id,
                input_envelope_digest=envelope.canonical_digest,
                input_envelope_schema=envelope.schema_version,
                normalized_input_digest=envelope.normalized_input_digest,
                input_schema_digest=profile.input_schema_digest,
                output_schema_digest=profile.output_schema_digest,
                result_policy_digest=profile.result_policy_digest,
                maximum_timeout_seconds=profile.maximum_timeout_seconds,
                maximum_output_bytes=profile.maximum_output_bytes,
                authorization_policy_id=policy.policy_id,
                authorization_policy_digest=policy.canonical_digest,
                authorization_policy_version=policy.policy_version,
                instance_state=ENABLED_CAPABILITY_INVOCATION_GOVERNED,
                authorized_by=actor.subject_id,
                purpose=purpose,
                authorized_at=now,
                expires_at=min(
                    now + timedelta(minutes=policy.authorization_lifetime_minutes),
                    profile.expires_at,
                    envelope.expires_at,
                    policy.expires_at,
                ),
                canonical_digest="0" * 64,
                replay_digest=replay_digest,
                idempotency_digest=idempotency_digest,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit_required(
                actor=actor,
                correlation_id=correlation_id,
                result_code="connector_invocation_authorization_completed",
                scope_reference=record.authorization_id,
                idempotency_key=idempotency_key,
                metadata=(("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key_in_scope(
                    authorized_by=actor.subject_id,
                    idempotency_digest=idempotency_digest,
                    organization_id=source.organization_id,
                    environment_id=source.environment_id,
                )
                if raced is None or raced.replay_digest != replay_digest:
                    raise ConnectorInvocationAuthorizationError(
                        "invocation_authorization_record_conflict"
                    )
                return replace(await self._current_record(raced), reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, authorization_id: str, correlation_id: str
    ) -> ConnectorInvocationAuthorizationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get_in_scope(
            authorization_id=authorization_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if record is None:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_record_not_found")
        record = await self._current_record(record, actor=actor, correlation_id=correlation_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_invocation_authorization_read",
            record.authorization_id,
            None,
            (),
            permission_id=INVOCATION_AUTHORIZATION_READ_PERMISSION,
        )
        return record

    async def list_authorizations(
        self,
        *,
        actor: AuthenticatedSubject,
        source_target_session_verification_id: str | None,
        correlation_id: str,
    ) -> tuple[ConnectorInvocationAuthorizationRecord, ...]:
        self._require_enterprise_human(actor)
        if source_target_session_verification_id is None:
            candidates = await self._repository.list_scope(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        else:
            candidate = await self._repository.get_by_target_session_in_scope(
                source_target_session_verification_id=source_target_session_verification_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            candidates = (candidate,) if candidate is not None else ()
        visible = [
            await self._current_record(record, actor=actor, correlation_id=correlation_id)
            for record in candidates
        ]
        visible.sort(key=lambda item: item.authorization_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_invocation_authorizations_listed",
            source_target_session_verification_id or self._environment_id,
            None,
            (("count", str(len(visible))),),
            permission_id=INVOCATION_AUTHORIZATION_READ_PERMISSION,
        )
        return tuple(visible)

    async def list_options(
        self,
        *,
        actor: AuthenticatedSubject,
        source_target_session_verification_id: str,
        correlation_id: str,
    ) -> tuple[ConnectorInvocationAuthorizationOption, ...]:
        self._require_enterprise_human(actor)
        source, enablement, source_actors = await self._source_in_scope(
            actor=actor,
            source_target_session_verification_id=source_target_session_verification_id,
        )
        existing = await self._repository.get_by_target_session_in_scope(
            source_target_session_verification_id=source.verification_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        options: list[ConnectorInvocationAuthorizationOption] = []
        if existing is not None:
            await self._current_record(existing, actor=actor, correlation_id=correlation_id)
        else:
            if self._evidence_preparer is not None:
                await self._evidence_preparer.prepare(
                    source=source,
                    enablement=enablement,
                    issued_at=source.verified_at,
                )
            profiles = await self._profile_source.list_scope(
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            envelopes = await self._envelope_source.list_scope(
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            policies = await self._policy_source.list_scope(
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            now = self._clock()
            for capability in enablement.capabilities:
                for profile in profiles:
                    for envelope in envelopes:
                        for policy in policies:
                            try:
                                self._verify_snapshot(profile, "profile")
                                self._verify_snapshot(envelope, "envelope")
                                self._verify_snapshot(policy, "policy")
                                self._verify_authorization(
                                    assurance_level=actor.assurance_level,
                                    source=source,
                                    enablement=enablement,
                                    capability=capability,
                                    profile=profile,
                                    envelope=envelope,
                                    policy=policy,
                                    source_digest=source.canonical_digest,
                                    package_digest=source.package_digest,
                                    profile_digest=profile.canonical_digest,
                                    envelope_digest=envelope.canonical_digest,
                                    policy_digest=policy.canonical_digest,
                                    now=now,
                                )
                                if actor.subject_id in source_actors | {
                                    profile.signed_by,
                                    envelope.signed_by,
                                    policy.signed_by,
                                }:
                                    continue
                                await self._permission_authorizer.authorize(
                                    actor=actor,
                                    permission_id=capability.required_permission,
                                    capability_id=capability.capability_id,
                                    capability_class=capability.capability_class,
                                    organization_id=source.organization_id,
                                    environment_id=source.environment_id,
                                    correlation_id=correlation_id,
                                )
                            except ConnectorInvocationAuthorizationError:
                                continue
                            options.append(
                                ConnectorInvocationAuthorizationOption(
                                    source_target_session_verification_id=source.verification_id,
                                    source_target_session_digest=source.canonical_digest,
                                    package_digest=source.package_digest,
                                    capability_id=capability.capability_id,
                                    capability_class=capability.capability_class,
                                    required_permission=capability.required_permission,
                                    invocation_profile_id=profile.profile_id,
                                    invocation_profile_digest=profile.canonical_digest,
                                    invocation_profile_expires_at=profile.expires_at,
                                    input_envelope_id=envelope.envelope_id,
                                    input_envelope_digest=envelope.canonical_digest,
                                    input_envelope_expires_at=envelope.expires_at,
                                    input_envelope_field_count=envelope.field_count,
                                    authorization_policy_id=policy.policy_id,
                                    authorization_policy_digest=policy.canonical_digest,
                                    authorization_policy_version=policy.policy_version,
                                    authorization_policy_expires_at=policy.expires_at,
                                    required_assurance_level=policy.required_assurance_level,
                                    maximum_timeout_seconds=profile.maximum_timeout_seconds,
                                    maximum_output_bytes=profile.maximum_output_bytes,
                                )
                            )
        options.sort(
            key=lambda item: (
                item.capability_id,
                item.invocation_profile_id,
                item.input_envelope_id,
                item.authorization_policy_id,
            )
        )
        await self._audit(
            actor,
            correlation_id,
            "connector_invocation_authorization_options_listed",
            source.verification_id,
            None,
            (("count", str(len(options))),),
            permission_id=INVOCATION_AUTHORIZATION_READ_PERMISSION,
        )
        return tuple(options)

    async def _source_in_scope(
        self,
        *,
        actor: AuthenticatedSubject,
        source_target_session_verification_id: str,
    ) -> tuple[
        ConnectorTargetSessionVerificationRecord,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]:
        scoped = await self._source.repository.get_in_scope(
            verification_id=source_target_session_verification_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if scoped is None:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_source_not_found")
        try:
            source = await self._source.capability_invocation_authorization_source(
                verification_id=source_target_session_verification_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        except ConnectorTargetSessionError as error:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_source_not_found"
            ) from error
        verification = source[0]
        if (
            verification.verification_id != scoped.verification_id
            or verification.canonical_digest != scoped.canonical_digest
            or verification.organization_id != actor.organization_id
            or verification.environment_id != self._environment_id
        ):
            raise ConnectorInvocationAuthorizationError("invocation_authorization_source_not_found")
        return source

    async def _current_record(
        self,
        record: ConnectorInvocationAuthorizationRecord,
        *,
        actor: AuthenticatedSubject | None = None,
        correlation_id: str = "connector-invocation-authorization-current",
    ) -> ConnectorInvocationAuthorizationRecord:
        self._verify_record(record)
        scoped = await self._source.repository.get_in_scope(
            verification_id=record.source_target_session_verification_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if scoped is None:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_source_invalid")
        try:
            source, enablement, _ = await self._source.capability_invocation_authorization_source(
                verification_id=record.source_target_session_verification_id,
                organization_id=record.organization_id,
                environment_id=record.environment_id,
            )
        except ConnectorTargetSessionError as error:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_source_invalid"
            ) from error
        if self._evidence_preparer is not None:
            await self._evidence_preparer.prepare(
                source=source,
                enablement=enablement,
                issued_at=source.verified_at,
            )
        profile = await self._profile_source.get_by_id_in_scope(
            profile_id=record.invocation_profile_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        envelope = await self._envelope_source.get_by_id_in_scope(
            envelope_id=record.input_envelope_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=record.authorization_policy_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if profile is None or envelope is None or policy is None:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_evidence_not_found"
            )
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(envelope, "envelope")
        self._verify_snapshot(policy, "policy")
        capability = self._capability(enablement, record.capability_id)
        self._verify_authorization(
            assurance_level=(
                actor.assurance_level if actor is not None else policy.required_assurance_level
            ),
            source=source,
            enablement=enablement,
            capability=capability,
            profile=profile,
            envelope=envelope,
            policy=policy,
            source_digest=record.source_target_session_digest,
            package_digest=record.package_digest,
            profile_digest=record.invocation_profile_digest,
            envelope_digest=record.input_envelope_digest,
            policy_digest=record.authorization_policy_digest,
            now=self._clock(),
        )
        if (
            scoped.canonical_digest != source.canonical_digest
            or record.capability_class != capability.capability_class
            or record.required_permission != capability.required_permission
            or record.input_schema_digest != profile.input_schema_digest
            or record.output_schema_digest != profile.output_schema_digest
            or record.result_policy_digest != profile.result_policy_digest
            or record.normalized_input_digest != envelope.normalized_input_digest
            or record.authorization_policy_version != policy.policy_version
            or self._clock() >= record.expires_at
        ):
            raise ConnectorInvocationAuthorizationError("invocation_authorization_invalid")
        if actor is not None:
            await self._permission_authorizer.authorize(
                actor=actor,
                permission_id=capability.required_permission,
                capability_id=capability.capability_id,
                capability_class=capability.capability_class,
                organization_id=record.organization_id,
                environment_id=record.environment_id,
                correlation_id=correlation_id,
            )
        return record

    async def bounded_invocation_source(
        self,
        *,
        authorization_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[ConnectorInvocationAuthorizationRecord, frozenset[str]]:
        record = await self._repository.get_in_scope(
            authorization_id=authorization_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if record is None:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_record_not_found")
        record = await self._current_record(record)
        try:
            (
                source,
                enablement,
                source_actors,
            ) = await self._source.capability_invocation_authorization_source(
                verification_id=record.source_target_session_verification_id,
                organization_id=record.organization_id,
                environment_id=record.environment_id,
            )
        except ConnectorTargetSessionError as error:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_source_not_found"
            ) from error
        profile = await self._profile_source.get_by_id_in_scope(
            profile_id=record.invocation_profile_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        envelope = await self._envelope_source.get_by_id_in_scope(
            envelope_id=record.input_envelope_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=record.authorization_policy_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if profile is None or envelope is None or policy is None:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_evidence_not_found"
            )
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(envelope, "envelope")
        self._verify_snapshot(policy, "policy")
        capability = self._capability(enablement, record.capability_id)
        if (
            source.canonical_digest != record.source_target_session_digest
            or source.package_digest != record.package_digest
            or source.instance_id != record.instance_id
            or capability.capability_class != record.capability_class
            or capability.required_permission != record.required_permission
            or profile.canonical_digest != record.invocation_profile_digest
            or envelope.canonical_digest != record.input_envelope_digest
            or policy.canonical_digest != record.authorization_policy_digest
            or record.instance_state != ENABLED_CAPABILITY_INVOCATION_GOVERNED
            or not record.capability_invocation_authorized
            or not record.eligible_for_bounded_capability_invocation
            or not record.single_use
            or record.renewable
            or record.consumed
            or record.target_connected
            or record.capability_invoked
            or record.scheduled
            or record.result_received
            or record.evidence_ingested
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise ConnectorInvocationAuthorizationError("invocation_authorization_invalid")
        return record, source_actors | {
            source.verified_by,
            enablement.enabled_by,
            record.authorized_by,
            profile.signed_by,
            envelope.signed_by,
            policy.signed_by,
        }

    async def close(self) -> None:
        await self._repository.close()

    @staticmethod
    def _capability(
        enablement: ConnectorCapabilityEnablementRecord, capability_id: str
    ) -> ConnectorGovernedCapability:
        matches = tuple(
            item for item in enablement.capabilities if item.capability_id == capability_id
        )
        if len(matches) != 1:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_capability_not_found"
            )
        return matches[0]

    @staticmethod
    def _verify_authorization(
        *,
        assurance_level: AssuranceLevel,
        source: ConnectorTargetSessionVerificationRecord,
        enablement: ConnectorCapabilityEnablementRecord,
        capability: ConnectorGovernedCapability,
        profile: ConnectorInvocationProfileSnapshot,
        envelope: ConnectorInvocationInputEnvelopeSnapshot,
        policy: ConnectorInvocationAuthorizationPolicySnapshot,
        source_digest: str,
        package_digest: str,
        profile_digest: str,
        envelope_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            source.canonical_digest != source_digest
            or source.package_digest != package_digest
            or profile.canonical_digest != profile_digest
            or envelope.canonical_digest != envelope_digest
            or policy.canonical_digest != policy_digest
            or policy.required_source_schema != source.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.required_envelope_schema != envelope.schema_version
            or policy.authorization_schema != INVOCATION_AUTHORIZATION_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or envelope.signed_by != policy.required_envelope_signer_id
            or profile.organization_id != source.organization_id
            or profile.environment_id != source.environment_id
            or envelope.organization_id != source.organization_id
            or envelope.environment_id != source.environment_id
            or policy.organization_id != source.organization_id
            or policy.environment_id != source.environment_id
            or profile.package_digest != source.package_digest
            or profile.connector_id != source.connector_id
            or profile.release_version != source.release_version
            or profile.manifest_digest != source.manifest_digest
            or profile.instance_id != source.instance_id
            or profile.source_target_session_digest != source.canonical_digest
            or profile.target_profile_digest != source.target_profile_digest
            or profile.target_identity_digest != source.target_identity_digest
            or profile.capability_id != capability.capability_id
            or profile.capability_class != capability.capability_class
            or profile.required_permission != capability.required_permission
            or profile.capability_class not in policy.allowed_capability_classes
            or envelope.capability_id != capability.capability_id
            or envelope.invocation_profile_digest != profile.canonical_digest
            or envelope.input_schema_digest != profile.input_schema_digest
            or profile.input_envelope_schema != envelope.schema_version
            or profile.maximum_timeout_seconds > policy.maximum_timeout_seconds
            or profile.maximum_output_bytes > policy.maximum_output_bytes
            or enablement.package_digest != source.package_digest
            or enablement.instance_id != source.instance_id
            or enablement.target_profile_digest != source.target_profile_digest
            or enablement.instance_state != ENABLED_CAPABILITIES_GOVERNED
            or not enablement.capability_governance_applied
            or not enablement.connector_enabled
            or not enablement.eligible_for_runtime_trust
            or enablement.promotion_blocked
            or enablement.execution_authorized
            or enablement.deployment_approved
            or enablement.infrastructure_mutation_performed
            or source.instance_state != ENABLED_TARGET_SESSION_VERIFIED
            or policy.required_source_state != ENABLED_TARGET_SESSION_VERIFIED
            or not source.eligible_for_capability_invocation_governance
            or source.target_connected
            or source.capability_invocation_authorized
            or source.capability_invoked
            or source.scheduled
            or source.execution_authorized
            or source.deployment_approved
            or source.infrastructure_mutation_performed
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or not envelope.issued_at <= now < envelope.expires_at
            or now - source.verified_at > timedelta(hours=policy.maximum_source_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or now - envelope.issued_at > timedelta(hours=policy.maximum_envelope_age_hours)
            or not assurance_satisfies_policy(assurance_level, policy.required_assurance_level)
        ):
            raise ConnectorInvocationAuthorizationError("invocation_authorization_invalid")

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorInvocationProfileSnapshot
        | ConnectorInvocationInputEnvelopeSnapshot
        | ConnectorInvocationAuthorizationPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise ConnectorInvocationAuthorizationError(
                f"invocation_authorization_{kind}_integrity_failed"
            )

    def _reuse(
        self,
        record: ConnectorInvocationAuthorizationRecord,
        actor: AuthenticatedSubject,
        replay_digest: str,
    ) -> ConnectorInvocationAuthorizationRecord:
        if record.authorized_by != actor.subject_id or record.replay_digest != replay_digest:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_idempotency_conflict"
            )
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        return replace(record, reused=True)

    @classmethod
    def _verify_record(cls, record: ConnectorInvocationAuthorizationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_record_integrity_failed"
            )

    @classmethod
    def _record_payload(cls, record: ConnectorInvocationAuthorizationRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "replay_digest", "idempotency_digest", "reused"):
            payload.pop(field)
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
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorInvocationAuthorizationError("invocation_authorization_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = INVOCATION_AUTHORIZATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.invocation-authorization",
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
                resource_type="resource.connector.invocation-authorization",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )

    async def _audit_required(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        try:
            await asyncio.wait_for(
                self._audit(
                    actor,
                    correlation_id,
                    result_code,
                    scope_reference,
                    idempotency_key,
                    metadata,
                ),
                timeout=INVOCATION_AUTHORIZATION_REQUIRED_AUDIT_TIMEOUT_SECONDS,
            )
        except Exception as error:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_audit_failed"
            ) from error


def _signed_snapshot(
    snapshot: ConnectorInvocationProfileSnapshot
    | ConnectorInvocationInputEnvelopeSnapshot
    | ConnectorInvocationAuthorizationPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorInvocationAuthorizationService._digest(
        ConnectorInvocationAuthorizationService._normalize(payload)
    )


def build_connector_invocation_profile(
    *,
    source: ConnectorTargetSessionVerificationRecord,
    capability: ConnectorGovernedCapability,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorInvocationProfileSnapshot:
    capability_suffix = sha256(capability.capability_id.encode("ascii")).hexdigest()[:12]
    snapshot = ConnectorInvocationProfileSnapshot(
        profile_id=(f"connector-invocation-profile.development-read-only.{capability_suffix}"),
        schema_version="atlas.connector-invocation-profile.v1",
        version=1,
        organization_id=source.organization_id,
        environment_id=source.environment_id,
        package_digest=source.package_digest,
        connector_id=source.connector_id,
        release_version=source.release_version,
        manifest_digest=source.manifest_digest,
        instance_id=source.instance_id,
        source_target_session_digest=source.canonical_digest,
        target_profile_digest=source.target_profile_digest,
        target_identity_digest=source.target_identity_digest,
        capability_id=capability.capability_id,
        capability_class=capability.capability_class,
        required_permission=capability.required_permission,
        input_schema_digest=ConnectorInvocationAuthorizationService._digest(
            [capability.capability_id, "input-schema-v1"]
        ),
        output_schema_digest=ConnectorInvocationAuthorizationService._digest(
            [capability.capability_id, "output-schema-v1"]
        ),
        input_envelope_schema="atlas.connector-invocation-input-envelope.v1",
        result_policy_digest=ConnectorInvocationAuthorizationService._digest(
            [capability.capability_id, "result-policy-v1"]
        ),
        maximum_timeout_seconds=30,
        maximum_output_bytes=262_144,
        signed_by="subject.connector-invocation-profile-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_connector_invocation_input_envelope(
    *, profile: ConnectorInvocationProfileSnapshot, issued_at: datetime, expires_at: datetime
) -> ConnectorInvocationInputEnvelopeSnapshot:
    profile_suffix = sha256(profile.canonical_digest.encode("ascii")).hexdigest()[:12]
    snapshot = ConnectorInvocationInputEnvelopeSnapshot(
        envelope_id=f"connector-invocation-input-envelope.development-empty.{profile_suffix}",
        schema_version="atlas.connector-invocation-input-envelope.v1",
        version=1,
        organization_id=profile.organization_id,
        environment_id=profile.environment_id,
        capability_id=profile.capability_id,
        invocation_profile_digest=profile.canonical_digest,
        input_schema_digest=profile.input_schema_digest,
        normalized_input_digest=ConnectorInvocationAuthorizationService._digest({}),
        field_count=0,
        signed_by="subject.connector-invocation-envelope-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_invocation_authorization_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorInvocationAuthorizationPolicySnapshot:
    snapshot = ConnectorInvocationAuthorizationPolicySnapshot(
        policy_id="connector-invocation-authorization-policy.development",
        schema_version="atlas.connector-invocation-authorization-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.connector-target-session-verification.v1",
        required_profile_schema="atlas.connector-invocation-profile.v1",
        required_envelope_schema="atlas.connector-invocation-input-envelope.v1",
        required_profile_signer_id="subject.connector-invocation-profile-signer",
        required_envelope_signer_id="subject.connector-invocation-envelope-signer",
        allowed_capability_classes=("C0", "C1"),
        maximum_timeout_seconds=60,
        maximum_output_bytes=524_288,
        maximum_source_age_hours=24,
        maximum_profile_age_hours=24,
        maximum_envelope_age_hours=24,
        authorization_lifetime_minutes=15,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_source_state=ENABLED_TARGET_SESSION_VERIFIED,
        authorization_schema=INVOCATION_AUTHORIZATION_SCHEMA,
        signed_by="subject.connector-invocation-authorization-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
