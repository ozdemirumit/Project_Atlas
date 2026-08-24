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
from atlas.modules.connectors.application.credential_assignment_ports import (
    ConnectorCredentialAssignmentError,
)
from atlas.modules.connectors.application.runtime_trust_ports import ConnectorRuntimeTrustError
from atlas.modules.connectors.application.secret_brokerage_ports import (
    ConnectorSecretBrokerageCredentialSource,
    ConnectorSecretBrokerageError,
    ConnectorSecretBrokeragePolicySource,
    ConnectorSecretBrokerageProfileSource,
    ConnectorSecretBrokerageRepository,
    ConnectorSecretBrokerageRuntimeTrustSource,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
    ConnectorCredentialProfileSnapshot,
)
from atlas.modules.connectors.domain.runtime_trust import (
    ENABLED_RUNTIME_TRUSTED,
    ConnectorRuntimeTrustGrantRecord,
)
from atlas.modules.connectors.domain.secret_brokerage import (
    ENABLED_SECRET_BROKERAGE_GOVERNED,
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorSecretBrokeragePolicySnapshot,
    ConnectorSecretBrokerageProfileSnapshot,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

SECRET_BROKERAGE_CREATE_PERMISSION = "connectors.secret-brokerage-authorizations.create"
SECRET_BROKERAGE_READ_PERMISSION = "connectors.secret-brokerage-authorizations.read"
SECRET_BROKERAGE_AUTHORIZATION_SCHEMA = "atlas.connector-secret-brokerage-authorization.v1"


@dataclass(frozen=True, slots=True)
class ConnectorSecretBrokerageOption:
    source_runtime_trust_grant_id: str
    source_runtime_trust_digest: str
    package_digest: str
    brokerage_profile_id: str
    brokerage_profile_digest: str
    brokerage_profile_expires_at: datetime
    delivery_policy_id: str
    lease_policy_id: str
    maximum_lease_seconds: int
    revocation_policy_id: str
    brokerage_policy_id: str
    brokerage_policy_digest: str
    brokerage_policy_version: str
    brokerage_policy_expires_at: datetime
    required_assurance_level: AssuranceLevel
    resulting_instance_state: str = ENABLED_SECRET_BROKERAGE_GOVERNED


class ConnectorSecretBrokerageService:
    def __init__(
        self,
        *,
        repository: ConnectorSecretBrokerageRepository,
        runtime_trust_source: ConnectorSecretBrokerageRuntimeTrustSource,
        credential_source: ConnectorSecretBrokerageCredentialSource,
        profile_source: ConnectorSecretBrokerageProfileSource,
        policy_source: ConnectorSecretBrokeragePolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._runtime_trust_source = runtime_trust_source
        self._credential_source = credential_source
        self._profile_source = profile_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorSecretBrokerageRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_trust_grant_id: str,
        source_runtime_trust_digest: str,
        package_digest: str,
        brokerage_profile_id: str,
        brokerage_profile_digest: str,
        brokerage_policy_id: str,
        brokerage_policy_digest: str,
        purpose: str,
        authorization_only_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord:
        self._require_human(actor)
        if not authorization_only_acknowledged:
            raise ConnectorSecretBrokerageError("secret_brokerage_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorSecretBrokerageError("secret_brokerage_request_invalid")
        fingerprint = self._digest(
            {
                "source_runtime_trust_grant_id": source_runtime_trust_grant_id,
                "source_runtime_trust_digest": source_runtime_trust_digest,
                "package_digest": package_digest,
                "brokerage_profile_id": brokerage_profile_id,
                "brokerage_profile_digest": brokerage_profile_digest,
                "brokerage_policy_id": brokerage_policy_id,
                "brokerage_policy_digest": brokerage_policy_digest,
                "purpose": purpose,
            }
        )
        (
            runtime_trust,
            runtime_actors,
            assignment,
            credential_profile,
            credential_actors,
        ) = await self._source_in_scope(
            actor=actor, source_runtime_trust_grant_id=source_runtime_trust_grant_id
        )
        existing = await self._repository.get_by_create_key_in_scope(
            authorized_by=actor.subject_id,
            idempotency_key=idempotency_key,
            organization_id=runtime_trust.organization_id,
            environment_id=runtime_trust.environment_id,
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        profile = await self._profile_source.get_by_id_in_scope(
            profile_id=brokerage_profile_id,
            organization_id=runtime_trust.organization_id,
            environment_id=runtime_trust.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=brokerage_policy_id,
            organization_id=runtime_trust.organization_id,
            environment_id=runtime_trust.environment_id,
        )
        if profile is None or policy is None:
            raise ConnectorSecretBrokerageError("secret_brokerage_evidence_not_found")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._require_scope(actor, runtime_trust.organization_id, runtime_trust.environment_id)
        now = self._clock()
        self._verify_authorization(
            actor=actor,
            runtime_trust=runtime_trust,
            assignment=assignment,
            credential_profile=credential_profile,
            profile=profile,
            policy=policy,
            source_runtime_trust_digest=source_runtime_trust_digest,
            package_digest=package_digest,
            brokerage_profile_digest=brokerage_profile_digest,
            brokerage_policy_digest=brokerage_policy_digest,
            now=now,
        )
        if actor.subject_id in (
            runtime_actors | credential_actors | {profile.signed_by, policy.signed_by}
        ):
            raise ConnectorSecretBrokerageError("secret_brokerage_separation_required")

        async with self._mutation_lock:
            prior = await self._repository.get_by_runtime_trust_in_scope(
                source_runtime_trust_grant_id=runtime_trust.grant_id,
                organization_id=runtime_trust.organization_id,
                environment_id=runtime_trust.environment_id,
            )
            if prior is not None:
                if (
                    prior.authorized_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorSecretBrokerageError("secret_brokerage_runtime_trust_conflict")
            await self._audit(
                actor,
                correlation_id,
                "connector_secret_brokerage_requested",
                runtime_trust.instance_id,
                (("brokerage_profile_digest", profile.canonical_digest),),
            )
            seed = self._digest(
                [
                    runtime_trust.organization_id,
                    runtime_trust.environment_id,
                    runtime_trust.grant_id,
                    profile.profile_id,
                    profile.canonical_digest,
                ]
            )
            record = ConnectorSecretBrokerageAuthorizationRecord(
                authorization_id=f"connector-secret-brokerage-authorization.{seed[:24]}",
                schema_version=SECRET_BROKERAGE_AUTHORIZATION_SCHEMA,
                version=1,
                source_runtime_trust_grant_id=runtime_trust.grant_id,
                source_runtime_trust_digest=runtime_trust.canonical_digest,
                organization_id=runtime_trust.organization_id,
                environment_id=runtime_trust.environment_id,
                package_digest=runtime_trust.package_digest,
                connector_id=runtime_trust.connector_id,
                release_version=runtime_trust.release_version,
                manifest_digest=runtime_trust.manifest_digest,
                instance_id=runtime_trust.instance_id,
                instance_key=runtime_trust.instance_key,
                display_name=runtime_trust.display_name,
                credential_profile_id=credential_profile.profile_id,
                credential_profile_digest=credential_profile.canonical_digest,
                credential_class=credential_profile.credential_class,
                authentication_method=credential_profile.authentication_method,
                privilege_class=credential_profile.privilege_class,
                rotation_state=credential_profile.rotation_state,
                revocation_state=credential_profile.revocation_state,
                next_rotation_at=credential_profile.next_rotation_at,
                runtime_profile_id=runtime_trust.runtime_profile_id,
                runtime_profile_digest=runtime_trust.runtime_profile_digest,
                runner_workload_identity_id=runtime_trust.runner_workload_identity_id,
                secret_delivery_policy_id=runtime_trust.secret_delivery_policy_id,
                brokerage_profile_id=profile.profile_id,
                brokerage_profile_digest=profile.canonical_digest,
                broker_id=profile.broker_id,
                secret_store_profile_id=profile.secret_store_profile_id,
                delivery_policy_id=profile.delivery_policy_id,
                lease_policy_id=profile.lease_policy_id,
                maximum_lease_seconds=profile.maximum_lease_seconds,
                revocation_policy_id=profile.revocation_policy_id,
                brokerage_policy_id=policy.policy_id,
                brokerage_policy_digest=policy.canonical_digest,
                brokerage_policy_version=policy.policy_version,
                authorization_version=1,
                instance_state=policy.required_effective_state,
                authorized_by=actor.subject_id,
                purpose=purpose,
                authorized_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_secret_brokerage_completed",
                record.authorization_id,
                (("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key_in_scope(
                    authorized_by=actor.subject_id,
                    idempotency_key=idempotency_key,
                    organization_id=runtime_trust.organization_id,
                    environment_id=runtime_trust.environment_id,
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorSecretBrokerageError("secret_brokerage_record_conflict")
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, authorization_id: str, correlation_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord:
        self._require_human(actor)
        record = await self._repository.get_in_scope(
            authorization_id=authorization_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if record is None:
            raise ConnectorSecretBrokerageError("secret_brokerage_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        current, *_ = await self.runtime_activation_source(authorization_id=record.authorization_id)
        if current.canonical_digest != record.canonical_digest:
            raise ConnectorSecretBrokerageError("secret_brokerage_source_invalid")
        await self._audit(
            actor,
            correlation_id,
            "connector_secret_brokerage_read",
            record.authorization_id,
            (),
            permission_id=SECRET_BROKERAGE_READ_PERMISSION,
        )
        return current

    async def list_authorizations(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_trust_grant_id: str | None,
        correlation_id: str,
    ) -> tuple[ConnectorSecretBrokerageAuthorizationRecord, ...]:
        self._require_human(actor)
        if source_runtime_trust_grant_id is None:
            candidates = await self._repository.list_scope(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        else:
            candidate = await self._repository.get_by_runtime_trust_in_scope(
                source_runtime_trust_grant_id=source_runtime_trust_grant_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            candidates = (candidate,) if candidate is not None else ()
        visible: list[ConnectorSecretBrokerageAuthorizationRecord] = []
        for record in candidates:
            self._verify_record(record)
            self._require_scope(actor, record.organization_id, record.environment_id)
            current, *_ = await self.runtime_activation_source(
                authorization_id=record.authorization_id
            )
            if current.canonical_digest != record.canonical_digest:
                raise ConnectorSecretBrokerageError("secret_brokerage_source_invalid")
            visible.append(current)
        visible.sort(key=lambda item: item.authorization_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_secret_brokerage_authorizations_listed",
            source_runtime_trust_grant_id or self._environment_id,
            (("count", str(len(visible))),),
            permission_id=SECRET_BROKERAGE_READ_PERMISSION,
        )
        return tuple(visible)

    async def list_options(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runtime_trust_grant_id: str,
        correlation_id: str,
    ) -> tuple[ConnectorSecretBrokerageOption, ...]:
        self._require_human(actor)
        (
            runtime_trust,
            runtime_actors,
            assignment,
            credential_profile,
            credential_actors,
        ) = await self._source_in_scope(
            actor=actor,
            source_runtime_trust_grant_id=source_runtime_trust_grant_id,
        )
        existing = await self._repository.get_by_runtime_trust_in_scope(
            source_runtime_trust_grant_id=runtime_trust.grant_id,
            organization_id=runtime_trust.organization_id,
            environment_id=runtime_trust.environment_id,
        )
        options: list[ConnectorSecretBrokerageOption] = []
        if existing is not None:
            self._verify_record(existing)
        else:
            profiles = await self._profile_source.list_scope(
                organization_id=runtime_trust.organization_id,
                environment_id=runtime_trust.environment_id,
            )
            policies = await self._policy_source.list_scope(
                organization_id=runtime_trust.organization_id,
                environment_id=runtime_trust.environment_id,
            )
            now = self._clock()
            for profile in profiles:
                for policy in policies:
                    try:
                        self._verify_snapshot(profile, "profile")
                        self._verify_snapshot(policy, "policy")
                        self._verify_authorization(
                            actor=actor,
                            runtime_trust=runtime_trust,
                            assignment=assignment,
                            credential_profile=credential_profile,
                            profile=profile,
                            policy=policy,
                            source_runtime_trust_digest=runtime_trust.canonical_digest,
                            package_digest=runtime_trust.package_digest,
                            brokerage_profile_digest=profile.canonical_digest,
                            brokerage_policy_digest=policy.canonical_digest,
                            now=now,
                        )
                    except ConnectorSecretBrokerageError:
                        continue
                    if actor.subject_id in (
                        runtime_actors | credential_actors | {profile.signed_by, policy.signed_by}
                    ):
                        continue
                    options.append(
                        ConnectorSecretBrokerageOption(
                            source_runtime_trust_grant_id=runtime_trust.grant_id,
                            source_runtime_trust_digest=runtime_trust.canonical_digest,
                            package_digest=runtime_trust.package_digest,
                            brokerage_profile_id=profile.profile_id,
                            brokerage_profile_digest=profile.canonical_digest,
                            brokerage_profile_expires_at=profile.expires_at,
                            delivery_policy_id=profile.delivery_policy_id,
                            lease_policy_id=profile.lease_policy_id,
                            maximum_lease_seconds=profile.maximum_lease_seconds,
                            revocation_policy_id=profile.revocation_policy_id,
                            brokerage_policy_id=policy.policy_id,
                            brokerage_policy_digest=policy.canonical_digest,
                            brokerage_policy_version=policy.policy_version,
                            brokerage_policy_expires_at=policy.expires_at,
                            required_assurance_level=policy.required_assurance_level,
                        )
                    )
        options.sort(
            key=lambda item: (
                item.brokerage_profile_id,
                item.brokerage_profile_digest,
                item.brokerage_policy_id,
                item.brokerage_policy_digest,
            )
        )
        await self._audit(
            actor,
            correlation_id,
            "connector_secret_brokerage_options_listed",
            runtime_trust.instance_id,
            (("count", str(len(options))),),
            permission_id=SECRET_BROKERAGE_READ_PERMISSION,
        )
        return tuple(options)

    async def _source_in_scope(
        self, *, actor: AuthenticatedSubject, source_runtime_trust_grant_id: str
    ) -> tuple[
        ConnectorRuntimeTrustGrantRecord,
        frozenset[str],
        ConnectorCredentialAssignmentRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]:
        scoped = await self._runtime_trust_source.repository.get_in_scope(
            grant_id=source_runtime_trust_grant_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if scoped is None:
            raise ConnectorSecretBrokerageError("secret_brokerage_source_not_found")
        try:
            (
                runtime_trust,
                runtime_actors,
            ) = await self._runtime_trust_source.secret_brokerage_source(
                grant_id=source_runtime_trust_grant_id
            )
            (
                assignment,
                credential_profile,
                credential_actors,
            ) = await self._credential_source.secret_brokerage_source(
                credential_profile_id=runtime_trust.credential_profile_id,
                instance_id=runtime_trust.instance_id,
            )
        except (ConnectorRuntimeTrustError, ConnectorCredentialAssignmentError) as error:
            raise ConnectorSecretBrokerageError("secret_brokerage_source_not_found") from error
        if (
            runtime_trust.grant_id != scoped.grant_id
            or runtime_trust.canonical_digest != scoped.canonical_digest
            or runtime_trust.organization_id != actor.organization_id
            or runtime_trust.environment_id != self._environment_id
        ):
            raise ConnectorSecretBrokerageError("secret_brokerage_source_not_found")
        return (
            runtime_trust,
            runtime_actors,
            assignment,
            credential_profile,
            credential_actors,
        )

    async def runtime_activation_source(
        self, *, authorization_id: str
    ) -> tuple[
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        frozenset[str],
    ]:
        record = await self._repository.get(authorization_id=authorization_id)
        if record is None:
            raise ConnectorSecretBrokerageError("secret_brokerage_record_not_found")
        self._verify_record(record)
        runtime_trust, runtime_actors = await self._runtime_trust_source.secret_brokerage_source(
            grant_id=record.source_runtime_trust_grant_id
        )
        (
            assignment,
            credential_profile,
            credential_actors,
        ) = await self._credential_source.secret_brokerage_source(
            credential_profile_id=record.credential_profile_id,
            instance_id=record.instance_id,
        )
        profile = await self._profile_source.get_by_id(profile_id=record.brokerage_profile_id)
        policy = await self._policy_source.get_by_id(policy_id=record.brokerage_policy_id)
        if profile is None or policy is None:
            raise ConnectorSecretBrokerageError("secret_brokerage_runtime_activation_invalid")
        self._verify_snapshot(profile, "profile")
        self._verify_snapshot(policy, "policy")
        self._verify_authorization(
            actor=None,
            runtime_trust=runtime_trust,
            assignment=assignment,
            credential_profile=credential_profile,
            profile=profile,
            policy=policy,
            source_runtime_trust_digest=record.source_runtime_trust_digest,
            package_digest=record.package_digest,
            brokerage_profile_digest=record.brokerage_profile_digest,
            brokerage_policy_digest=record.brokerage_policy_digest,
            now=self._clock(),
        )
        if (
            record.source_runtime_trust_digest != runtime_trust.canonical_digest
            or record.package_digest != runtime_trust.package_digest
            or record.instance_id != runtime_trust.instance_id
            or record.runtime_profile_digest != runtime_trust.runtime_profile_digest
            or record.credential_profile_digest != credential_profile.canonical_digest
            or assignment.credential_profile_digest != credential_profile.canonical_digest
            or record.instance_state != ENABLED_SECRET_BROKERAGE_GOVERNED
            or not record.eligible_for_runtime_activation
            or record.secret_lease_issued
            or record.credentials_resolved
            or record.runner_started
            or record.package_loaded
            or record.target_connection_authorized
            or record.capability_invocation_authorized
            or record.execution_authorized
            or record.deployment_approved
            or record.infrastructure_mutation_performed
        ):
            raise ConnectorSecretBrokerageError("secret_brokerage_runtime_activation_invalid")
        return (
            record,
            runtime_trust,
            credential_profile,
            runtime_actors | credential_actors | {record.authorized_by},
        )

    async def capability_invocation_source(
        self, *, authorization_id: str
    ) -> tuple[
        ConnectorSecretBrokerageAuthorizationRecord,
        ConnectorRuntimeTrustGrantRecord,
        ConnectorCredentialProfileSnapshot,
        ConnectorCapabilityEnablementRecord,
        frozenset[str],
    ]:
        record, runtime_trust, credential_profile, actors = await self.runtime_activation_source(
            authorization_id=authorization_id
        )
        (
            trusted,
            enablement,
            source_actors,
        ) = await self._runtime_trust_source.capability_invocation_source(
            grant_id=record.source_runtime_trust_grant_id
        )
        if trusted.canonical_digest != runtime_trust.canonical_digest:
            raise ConnectorSecretBrokerageError("secret_brokerage_source_invalid")
        return (
            record,
            runtime_trust,
            credential_profile,
            enablement,
            frozenset(actors | source_actors),
        )

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        record: ConnectorSecretBrokerageAuthorizationRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorSecretBrokerageAuthorizationRecord:
        if record.authorized_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorSecretBrokerageError("secret_brokerage_idempotency_conflict")
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorSecretBrokerageProfileSnapshot | ConnectorSecretBrokeragePolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorSecretBrokerageError(f"secret_brokerage_{kind}_integrity_failed")

    @staticmethod
    def _verify_authorization(
        *,
        actor: AuthenticatedSubject | None,
        runtime_trust: ConnectorRuntimeTrustGrantRecord,
        assignment: ConnectorCredentialAssignmentRecord,
        credential_profile: ConnectorCredentialProfileSnapshot,
        profile: ConnectorSecretBrokerageProfileSnapshot,
        policy: ConnectorSecretBrokeragePolicySnapshot,
        source_runtime_trust_digest: str,
        package_digest: str,
        brokerage_profile_digest: str,
        brokerage_policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            runtime_trust.canonical_digest != source_runtime_trust_digest
            or runtime_trust.package_digest != package_digest
            or profile.canonical_digest != brokerage_profile_digest
            or policy.canonical_digest != brokerage_policy_digest
            or policy.required_runtime_trust_schema != runtime_trust.schema_version
            or policy.required_profile_schema != profile.schema_version
            or policy.authorization_schema != SECRET_BROKERAGE_AUTHORIZATION_SCHEMA
            or profile.signed_by != policy.required_profile_signer_id
            or profile.organization_id != runtime_trust.organization_id
            or profile.environment_id != runtime_trust.environment_id
            or policy.organization_id != runtime_trust.organization_id
            or policy.environment_id != runtime_trust.environment_id
            or profile.package_digest != runtime_trust.package_digest
            or profile.connector_id != runtime_trust.connector_id
            or profile.release_version != runtime_trust.release_version
            or profile.manifest_digest != runtime_trust.manifest_digest
            or profile.instance_id != runtime_trust.instance_id
            or profile.source_runtime_trust_digest != runtime_trust.canonical_digest
            or profile.credential_profile_digest != runtime_trust.credential_profile_digest
            or profile.runtime_profile_digest != runtime_trust.runtime_profile_digest
            or profile.runner_workload_identity_id != runtime_trust.runner_workload_identity_id
            or profile.delivery_policy_id != runtime_trust.secret_delivery_policy_id
            or profile.broker_id not in policy.allowed_broker_ids
            or profile.secret_store_profile_id not in policy.allowed_secret_store_profile_ids
            or profile.delivery_policy_id != policy.required_delivery_policy_id
            or profile.lease_policy_id != policy.required_lease_policy_id
            or profile.maximum_lease_seconds > policy.maximum_lease_seconds
            or profile.revocation_policy_id != policy.required_revocation_policy_id
            or assignment.instance_id != runtime_trust.instance_id
            or assignment.credential_profile_id != runtime_trust.credential_profile_id
            or assignment.credential_profile_digest != runtime_trust.credential_profile_digest
            or credential_profile.canonical_digest != assignment.credential_profile_digest
            or credential_profile.secret_store_profile_id != profile.secret_store_profile_id
            or credential_profile.privilege_class != policy.required_privilege_class
            or credential_profile.privilege_class != "privilege.read-only"
            or credential_profile.rotation_state != policy.required_rotation_state
            or credential_profile.rotation_state != "rotation.current"
            or credential_profile.revocation_state != policy.required_revocation_state
            or credential_profile.revocation_state != "revocation.active"
            or credential_profile.next_rotation_at
            <= now + timedelta(hours=policy.minimum_rotation_window_hours)
            or profile.delivery_policy_id
            != "secret-delivery-policy.ephemeral-disabled-until-brokered"
            or profile.lease_policy_id != "secret-lease-policy.single-use-non-renewable"
            or profile.revocation_policy_id != "secret-revocation-policy.check-before-issue-and-use"
            or runtime_trust.instance_state != ENABLED_RUNTIME_TRUSTED
            or not runtime_trust.runtime_trust_granted
            or not runtime_trust.eligible_for_secret_brokerage
            or runtime_trust.credential_resolution_authorized
            or runtime_trust.credentials_resolved
            or runtime_trust.runner_started
            or runtime_trust.package_loaded
            or runtime_trust.target_connection_authorized
            or runtime_trust.capability_invocation_authorized
            or runtime_trust.execution_authorized
            or runtime_trust.deployment_approved
            or runtime_trust.infrastructure_mutation_performed
            or not policy.issued_at <= now < policy.expires_at
            or not profile.issued_at <= now < profile.expires_at
            or now - runtime_trust.granted_at
            > timedelta(hours=policy.maximum_runtime_trust_age_hours)
            or now - profile.issued_at > timedelta(hours=policy.maximum_profile_age_hours)
            or (
                actor is not None
                and not assurance_satisfies_policy(
                    actor.assurance_level, policy.required_assurance_level
                )
            )
        ):
            raise ConnectorSecretBrokerageError("secret_brokerage_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorSecretBrokerageAuthorizationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorSecretBrokerageError("secret_brokerage_record_integrity_failed")

    @classmethod
    def _record_payload(
        cls, record: ConnectorSecretBrokerageAuthorizationRecord
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
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
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorSecretBrokerageError("secret_brokerage_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorSecretBrokerageError("secret_brokerage_record_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = SECRET_BROKERAGE_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.secret-brokerage",
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
                resource_type="resource.connector.secret-brokerage-authorization",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=None,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorSecretBrokerageProfileSnapshot | ConnectorSecretBrokeragePolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorSecretBrokerageService._digest(
        ConnectorSecretBrokerageService._normalize(payload)
    )


def build_connector_secret_brokerage_profile(
    *,
    runtime_trust: ConnectorRuntimeTrustGrantRecord,
    credential_profile: ConnectorCredentialProfileSnapshot,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorSecretBrokerageProfileSnapshot:
    snapshot = ConnectorSecretBrokerageProfileSnapshot(
        profile_id="connector-secret-brokerage-profile.development-memory-only",
        schema_version="atlas.connector-secret-brokerage-profile.v1",
        version=1,
        organization_id=runtime_trust.organization_id,
        environment_id=runtime_trust.environment_id,
        package_digest=runtime_trust.package_digest,
        connector_id=runtime_trust.connector_id,
        release_version=runtime_trust.release_version,
        manifest_digest=runtime_trust.manifest_digest,
        instance_id=runtime_trust.instance_id,
        source_runtime_trust_digest=runtime_trust.canonical_digest,
        credential_profile_digest=credential_profile.canonical_digest,
        runtime_profile_digest=runtime_trust.runtime_profile_digest,
        runner_workload_identity_id=runtime_trust.runner_workload_identity_id,
        broker_id="secret-broker.enterprise",
        secret_store_profile_id=credential_profile.secret_store_profile_id,
        delivery_policy_id=runtime_trust.secret_delivery_policy_id,
        lease_policy_id="secret-lease-policy.single-use-non-renewable",
        maximum_lease_seconds=300,
        revocation_policy_id="secret-revocation-policy.check-before-issue-and-use",
        signed_by="subject.connector-secret-brokerage-security-attestor",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_secret_brokerage_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorSecretBrokeragePolicySnapshot:
    snapshot = ConnectorSecretBrokeragePolicySnapshot(
        policy_id="connector-secret-brokerage-policy.development",
        schema_version="atlas.connector-secret-brokerage-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_runtime_trust_schema="atlas.connector-runtime-trust-grant.v1",
        required_profile_schema="atlas.connector-secret-brokerage-profile.v1",
        required_profile_signer_id="subject.connector-secret-brokerage-security-attestor",
        allowed_broker_ids=("secret-broker.enterprise",),
        allowed_secret_store_profile_ids=("secret-store-profile.enterprise",),
        required_delivery_policy_id=("secret-delivery-policy.ephemeral-disabled-until-brokered"),
        required_lease_policy_id="secret-lease-policy.single-use-non-renewable",
        maximum_lease_seconds=300,
        required_revocation_policy_id=("secret-revocation-policy.check-before-issue-and-use"),
        required_privilege_class="privilege.read-only",
        required_rotation_state="rotation.current",
        required_revocation_state="revocation.active",
        minimum_rotation_window_hours=24,
        maximum_runtime_trust_age_hours=720,
        maximum_profile_age_hours=168,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_effective_state=ENABLED_SECRET_BROKERAGE_GOVERNED,
        authorization_schema=SECRET_BROKERAGE_AUTHORIZATION_SCHEMA,
        signed_by="subject.connector-secret-brokerage-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
