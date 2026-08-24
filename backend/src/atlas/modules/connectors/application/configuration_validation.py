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
from atlas.modules.connectors.application.configuration_validation_ports import (
    ConnectorConfigurationAssignmentSource,
    ConnectorConfigurationEvidenceSource,
    ConnectorConfigurationValidationError,
    ConnectorConfigurationValidationPolicySource,
    ConnectorConfigurationValidationRepository,
)
from atlas.modules.connectors.application.credential_assignment_ports import (
    ConnectorCredentialAssignmentError,
)
from atlas.modules.connectors.domain.configuration_validation import (
    DISABLED_CONFIGURATION_VALIDATED,
    ConnectorConfigurationEvidenceSnapshot,
    ConnectorConfigurationValidationPolicySnapshot,
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.connectors.domain.credential_assignment import (
    DISABLED_CREDENTIALS_ASSIGNED,
    ConnectorCredentialAssignmentRecord,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

CONFIGURATION_VALIDATION_CREATE_PERMISSION = "connectors.configuration-validations.create"
CONFIGURATION_VALIDATION_READ_PERMISSION = "connectors.configuration-validations.read"
CONFIGURATION_VALIDATION_SCHEMA = "atlas.connector-configuration-validation.v1"


@dataclass(frozen=True, slots=True)
class ConnectorConfigurationValidationOption:
    source_assignment_id: str
    source_assignment_digest: str
    package_digest: str
    evidence_id: str
    evidence_digest: str
    evidence_observed_at: datetime
    evidence_expires_at: datetime
    configuration_result: str
    connectivity_result: str
    tls_result: str
    endpoint_identity_result: str
    authentication_result: str
    authorization_result: str
    product_identity_result: str
    latency_band: str
    completed_checks: tuple[str, ...]
    validation_policy_id: str
    validation_policy_digest: str
    validation_policy_version: str
    validation_policy_expires_at: datetime
    required_assurance_level: AssuranceLevel
    resulting_instance_state: str = DISABLED_CONFIGURATION_VALIDATED


class ConnectorConfigurationValidationService:
    def __init__(
        self,
        *,
        repository: ConnectorConfigurationValidationRepository,
        assignment_source: ConnectorConfigurationAssignmentSource,
        evidence_source: ConnectorConfigurationEvidenceSource,
        policy_source: ConnectorConfigurationValidationPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._assignment_source = assignment_source
        self._evidence_source = evidence_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> ConnectorConfigurationValidationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_assignment_id: str,
        source_assignment_digest: str,
        package_digest: str,
        evidence_id: str,
        evidence_digest: str,
        validation_policy_id: str,
        validation_policy_digest: str,
        purpose: str,
        acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorConfigurationValidationRecord:
        self._require_human(actor)
        if not acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ConnectorConfigurationValidationError("configuration_validation_request_invalid")
        fingerprint = self._digest(
            {
                "source_assignment_id": source_assignment_id,
                "source_assignment_digest": source_assignment_digest,
                "package_digest": package_digest,
                "evidence_id": evidence_id,
                "evidence_digest": evidence_digest,
                "validation_policy_id": validation_policy_id,
                "validation_policy_digest": validation_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key_in_scope(
            validated_by=actor.subject_id,
            idempotency_key=idempotency_key,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)
        try:
            (
                assignment,
                _registration,
                source_actors,
            ) = await self._assignment_source.configuration_validation_source(
                assignment_id=source_assignment_id
            )
        except ConnectorCredentialAssignmentError as error:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_source_not_found"
            ) from error
        self._require_source_scope(actor, assignment.organization_id, assignment.environment_id)
        evidence = await self._evidence_source.get_by_id_in_scope(
            evidence_id=evidence_id,
            organization_id=assignment.organization_id,
            environment_id=assignment.environment_id,
        )
        policy = await self._policy_source.get_by_id_in_scope(
            policy_id=validation_policy_id,
            organization_id=assignment.organization_id,
            environment_id=assignment.environment_id,
        )
        if evidence is None or policy is None:
            raise ConnectorConfigurationValidationError("configuration_validation_invalid")
        self._verify_snapshot(evidence, "evidence")
        self._verify_snapshot(policy, "policy")
        now = self._clock()
        self._verify_validation(
            actor=actor,
            assignment=assignment,
            evidence=evidence,
            policy=policy,
            source_assignment_digest=source_assignment_digest,
            package_digest=package_digest,
            evidence_digest=evidence_digest,
            validation_policy_digest=validation_policy_digest,
            now=now,
        )
        if actor.subject_id in source_actors | {evidence.signed_by, policy.signed_by}:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_separation_required"
            )

        async with self._mutation_lock:
            prior = await self._repository.get_by_assignment_in_scope(
                source_assignment_id=assignment.assignment_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            if prior is not None:
                if (
                    prior.validated_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise ConnectorConfigurationValidationError(
                    "configuration_validation_assignment_conflict"
                )
            await self._audit(
                actor,
                correlation_id,
                "connector_configuration_validation_requested",
                assignment.instance_id,
                idempotency_key,
                (("evidence_digest", evidence.canonical_digest),),
            )
            seed = self._digest(
                [assignment.assignment_id, evidence.evidence_id, evidence.canonical_digest]
            )
            record = ConnectorConfigurationValidationRecord(
                validation_id=f"connector-configuration-validation.{seed[:24]}",
                schema_version=CONFIGURATION_VALIDATION_SCHEMA,
                version=1,
                source_assignment_id=assignment.assignment_id,
                source_assignment_digest=assignment.canonical_digest,
                organization_id=assignment.organization_id,
                environment_id=assignment.environment_id,
                package_digest=assignment.package_digest,
                connector_id=assignment.connector_id,
                release_version=assignment.release_version,
                manifest_digest=assignment.manifest_digest,
                instance_id=assignment.instance_id,
                instance_key=assignment.instance_key,
                display_name=assignment.display_name,
                owner_id=assignment.owner_id,
                target_profile_id=assignment.target_profile_id,
                target_profile_digest=assignment.target_profile_digest,
                site_id=assignment.site_id,
                target_type=assignment.target_type,
                target_product=assignment.target_product,
                credential_profile_id=assignment.credential_profile_id,
                credential_profile_digest=assignment.credential_profile_digest,
                credential_class=assignment.credential_class,
                authentication_method=assignment.authentication_method,
                privilege_class=assignment.privilege_class,
                evidence_id=evidence.evidence_id,
                evidence_digest=evidence.canonical_digest,
                probe_runner_id=evidence.probe_runner_id,
                probe_runner_version=evidence.probe_runner_version,
                network_zone_id=evidence.network_zone_id,
                configuration_result=evidence.configuration_result,
                connectivity_result=evidence.connectivity_result,
                tls_result=evidence.tls_result,
                endpoint_identity_result=evidence.endpoint_identity_result,
                authentication_result=evidence.authentication_result,
                authorization_result=evidence.authorization_result,
                product_identity_result=evidence.product_identity_result,
                latency_band=evidence.latency_band,
                completed_checks=evidence.completed_checks,
                evidence_observed_at=evidence.observed_at,
                validation_policy_id=policy.policy_id,
                validation_policy_digest=policy.canonical_digest,
                validation_policy_version=policy.policy_version,
                validation_version=1,
                instance_state=policy.required_effective_state,
                validated_by=actor.subject_id,
                purpose=purpose,
                validated_at=now,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
            await self._audit(
                actor,
                correlation_id,
                "connector_configuration_validation_completed",
                record.validation_id,
                idempotency_key,
                (("instance_state", record.instance_state),),
            )
            if not await self._repository.add(record):
                raced = await self._repository.get_by_create_key_in_scope(
                    validated_by=actor.subject_id,
                    idempotency_key=idempotency_key,
                    organization_id=actor.organization_id,
                    environment_id=self._environment_id,
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ConnectorConfigurationValidationError(
                        "configuration_validation_record_conflict"
                    )
                self._verify_record(raced)
                return replace(raced, reused=True)
        return record

    async def capability_enablement_source(
        self, *, validation_id: str
    ) -> tuple[
        ConnectorConfigurationValidationRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        record = await self._repository.get(validation_id=validation_id)
        if record is None:
            raise ConnectorConfigurationValidationError("configuration_validation_record_not_found")
        self._verify_record(record)
        try:
            (
                assignment,
                registration,
                source_actors,
            ) = await self._assignment_source.configuration_validation_source(
                assignment_id=record.source_assignment_id
            )
        except ConnectorCredentialAssignmentError as error:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_source_not_found"
            ) from error
        evidence = await self._evidence_source.get_by_id(evidence_id=record.evidence_id)
        policy = await self._policy_source.get_by_id(policy_id=record.validation_policy_id)
        if evidence is None or policy is None:
            raise ConnectorConfigurationValidationError("configuration_validation_source_not_found")
        self._verify_snapshot(evidence, "evidence")
        self._verify_snapshot(policy, "policy")
        self._verify_validation(
            actor=None,
            assignment=assignment,
            evidence=evidence,
            policy=policy,
            source_assignment_digest=record.source_assignment_digest,
            package_digest=record.package_digest,
            evidence_digest=record.evidence_digest,
            validation_policy_digest=record.validation_policy_digest,
            now=self._clock(),
        )
        if (
            record.source_assignment_digest != assignment.canonical_digest
            or record.package_digest != assignment.package_digest
            or record.evidence_digest != evidence.canonical_digest
            or record.validation_policy_digest != policy.canonical_digest
            or record.manifest_digest != registration.manifest.manifest_digest
        ):
            raise ConnectorConfigurationValidationError("configuration_validation_source_invalid")
        return (
            record,
            registration,
            frozenset(source_actors | {record.validated_by, evidence.signed_by, policy.signed_by}),
        )

    async def capability_enablement_source_in_scope(
        self,
        *,
        validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        ConnectorConfigurationValidationRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        record = await self._repository.get_in_scope(
            validation_id=validation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if record is None:
            raise ConnectorConfigurationValidationError("configuration_validation_record_not_found")
        return await self.capability_enablement_source(validation_id=record.validation_id)

    async def get(
        self, *, actor: AuthenticatedSubject, validation_id: str, correlation_id: str
    ) -> ConnectorConfigurationValidationRecord:
        self._require_human(actor)
        record = await self._repository.get_in_scope(
            validation_id=validation_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if record is None:
            raise ConnectorConfigurationValidationError("configuration_validation_record_not_found")
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_configuration_validation_read",
            record.validation_id,
            None,
            (),
            permission_id=CONFIGURATION_VALIDATION_READ_PERMISSION,
        )
        return record

    async def list_validations(
        self,
        *,
        actor: AuthenticatedSubject,
        source_assignment_id: str | None,
        correlation_id: str,
    ) -> tuple[ConnectorConfigurationValidationRecord, ...]:
        self._require_human(actor)
        if source_assignment_id is None:
            candidates = await self._repository.list_scope(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        else:
            candidate = await self._repository.get_by_assignment_in_scope(
                source_assignment_id=source_assignment_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            candidates = (candidate,) if candidate is not None else ()
        visible: list[ConnectorConfigurationValidationRecord] = []
        for record in candidates:
            self._verify_record(record)
            self._require_scope(actor, record.organization_id, record.environment_id)
            visible.append(record)
        visible.sort(key=lambda item: item.validation_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_configuration_validations_listed",
            source_assignment_id or self._environment_id,
            None,
            (("count", str(len(visible))),),
            permission_id=CONFIGURATION_VALIDATION_READ_PERMISSION,
        )
        return tuple(visible)

    async def list_options(
        self,
        *,
        actor: AuthenticatedSubject,
        source_assignment_id: str,
        correlation_id: str,
    ) -> tuple[ConnectorConfigurationValidationOption, ...]:
        self._require_human(actor)
        try:
            (
                assignment,
                _registration,
                source_actors,
            ) = await self._assignment_source.configuration_validation_source(
                assignment_id=source_assignment_id
            )
        except ConnectorCredentialAssignmentError as error:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_source_not_found"
            ) from error
        self._require_source_scope(actor, assignment.organization_id, assignment.environment_id)
        existing = await self._repository.get_by_assignment_in_scope(
            source_assignment_id=assignment.assignment_id,
            organization_id=assignment.organization_id,
            environment_id=assignment.environment_id,
        )
        if existing is not None:
            self._verify_record(existing)
            options: list[ConnectorConfigurationValidationOption] = []
        else:
            evidence_snapshots = await self._evidence_source.list_scope(
                organization_id=assignment.organization_id,
                environment_id=assignment.environment_id,
            )
            policies = await self._policy_source.list_scope(
                organization_id=assignment.organization_id,
                environment_id=assignment.environment_id,
            )
            now = self._clock()
            options = []
            for evidence in evidence_snapshots:
                for policy in policies:
                    try:
                        self._verify_snapshot(evidence, "evidence")
                        self._verify_snapshot(policy, "policy")
                        self._verify_validation(
                            actor=actor,
                            assignment=assignment,
                            evidence=evidence,
                            policy=policy,
                            source_assignment_digest=assignment.canonical_digest,
                            package_digest=assignment.package_digest,
                            evidence_digest=evidence.canonical_digest,
                            validation_policy_digest=policy.canonical_digest,
                            now=now,
                        )
                    except ConnectorConfigurationValidationError:
                        continue
                    if actor.subject_id in source_actors | {evidence.signed_by, policy.signed_by}:
                        continue
                    options.append(
                        ConnectorConfigurationValidationOption(
                            source_assignment_id=assignment.assignment_id,
                            source_assignment_digest=assignment.canonical_digest,
                            package_digest=assignment.package_digest,
                            evidence_id=evidence.evidence_id,
                            evidence_digest=evidence.canonical_digest,
                            evidence_observed_at=evidence.observed_at,
                            evidence_expires_at=evidence.expires_at,
                            configuration_result=evidence.configuration_result,
                            connectivity_result=evidence.connectivity_result,
                            tls_result=evidence.tls_result,
                            endpoint_identity_result=evidence.endpoint_identity_result,
                            authentication_result=evidence.authentication_result,
                            authorization_result=evidence.authorization_result,
                            product_identity_result=evidence.product_identity_result,
                            latency_band=evidence.latency_band,
                            completed_checks=evidence.completed_checks,
                            validation_policy_id=policy.policy_id,
                            validation_policy_digest=policy.canonical_digest,
                            validation_policy_version=policy.policy_version,
                            validation_policy_expires_at=policy.expires_at,
                            required_assurance_level=policy.required_assurance_level,
                        )
                    )
        options.sort(
            key=lambda item: (
                item.evidence_id,
                item.evidence_digest,
                item.validation_policy_id,
                item.validation_policy_digest,
            )
        )
        await self._audit(
            actor,
            correlation_id,
            "connector_configuration_validation_options_listed",
            assignment.instance_id,
            None,
            (("count", str(len(options))),),
            permission_id=CONFIGURATION_VALIDATION_READ_PERMISSION,
        )
        return tuple(options)

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        record: ConnectorConfigurationValidationRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorConfigurationValidationRecord:
        if record.validated_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_idempotency_conflict"
            )
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: ConnectorConfigurationEvidenceSnapshot
        | ConnectorConfigurationValidationPolicySnapshot,
        kind: str,
    ) -> None:
        payload = cast(dict[str, object], asdict(snapshot))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != snapshot.canonical_digest:
            raise ConnectorConfigurationValidationError(
                f"configuration_validation_{kind}_integrity_failed"
            )

    @staticmethod
    def _verify_validation(
        *,
        actor: AuthenticatedSubject | None,
        assignment: ConnectorCredentialAssignmentRecord,
        evidence: ConnectorConfigurationEvidenceSnapshot,
        policy: ConnectorConfigurationValidationPolicySnapshot,
        source_assignment_digest: str,
        package_digest: str,
        evidence_digest: str,
        validation_policy_digest: str,
        now: datetime,
    ) -> None:
        if (
            assignment.canonical_digest != source_assignment_digest
            or assignment.package_digest != package_digest
            or evidence.canonical_digest != evidence_digest
            or policy.canonical_digest != validation_policy_digest
            or policy.required_assignment_schema != assignment.schema_version
            or policy.required_evidence_schema != evidence.schema_version
            or policy.validation_record_schema != CONFIGURATION_VALIDATION_SCHEMA
            or evidence.signed_by != policy.required_evidence_signer_id
            or evidence.organization_id != assignment.organization_id
            or evidence.environment_id != assignment.environment_id
            or policy.organization_id != assignment.organization_id
            or policy.environment_id != assignment.environment_id
            or evidence.source_assignment_id != assignment.assignment_id
            or evidence.source_assignment_digest != assignment.canonical_digest
            or evidence.package_digest != assignment.package_digest
            or evidence.instance_id != assignment.instance_id
            or evidence.target_profile_id != assignment.target_profile_id
            or evidence.credential_profile_id != assignment.credential_profile_id
            or evidence.target_type != assignment.target_type
            or evidence.target_product != assignment.target_product
            or evidence.probe_runner_id not in policy.allowed_probe_runner_ids
            or evidence.network_zone_id not in policy.allowed_network_zone_ids
            or not set(policy.required_checks).issubset(evidence.completed_checks)
            or evidence.configuration_result != policy.required_configuration_result
            or evidence.connectivity_result != policy.required_connectivity_result
            or evidence.tls_result != policy.required_tls_result
            or evidence.endpoint_identity_result != policy.required_endpoint_identity_result
            or evidence.authentication_result != policy.required_authentication_result
            or evidence.authorization_result != policy.required_authorization_result
            or evidence.product_identity_result != policy.required_product_identity_result
            or assignment.instance_state != DISABLED_CREDENTIALS_ASSIGNED
            or not assignment.eligible_for_configuration_validation
            or assignment.credentials_resolved
            or not policy.issued_at <= now < policy.expires_at
            or not evidence.issued_at <= now < evidence.expires_at
            or now - assignment.assigned_at > timedelta(hours=policy.maximum_assignment_age_hours)
            or now - evidence.observed_at
            > timedelta(minutes=policy.maximum_observation_age_minutes)
            or (
                actor is not None
                and not assurance_satisfies_policy(
                    actor.assurance_level, policy.required_assurance_level
                )
            )
        ):
            raise ConnectorConfigurationValidationError("configuration_validation_invalid")

    @classmethod
    def _verify_record(cls, record: ConnectorConfigurationValidationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorConfigurationValidationError(
                "configuration_validation_record_integrity_failed"
            )

    @classmethod
    def _record_payload(cls, record: ConnectorConfigurationValidationRecord) -> dict[str, object]:
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
            raise ConnectorConfigurationValidationError("configuration_validation_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorConfigurationValidationError("configuration_validation_record_not_found")

    def _require_source_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise ConnectorConfigurationValidationError("configuration_validation_source_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = CONFIGURATION_VALIDATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.configuration-validation",
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
                resource_type="resource.connector.configuration-validation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def _signed_snapshot(
    snapshot: ConnectorConfigurationEvidenceSnapshot
    | ConnectorConfigurationValidationPolicySnapshot,
) -> str:
    payload = cast(dict[str, object], asdict(snapshot))
    payload.pop("canonical_digest")
    return ConnectorConfigurationValidationService._digest(
        ConnectorConfigurationValidationService._normalize(payload)
    )


def build_development_connector_configuration_evidence(
    *,
    organization_id: str,
    environment_id: str,
    source_assignment_id: str,
    source_assignment_digest: str,
    package_digest: str,
    instance_id: str,
    target_profile_id: str,
    credential_profile_id: str,
    target_type: str,
    target_product: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ConnectorConfigurationEvidenceSnapshot:
    snapshot = ConnectorConfigurationEvidenceSnapshot(
        evidence_id="connector-configuration-evidence.development-read-only-probe",
        schema_version="atlas.connector-configuration-evidence.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        source_assignment_id=source_assignment_id,
        source_assignment_digest=source_assignment_digest,
        package_digest=package_digest,
        instance_id=instance_id,
        target_profile_id=target_profile_id,
        credential_profile_id=credential_profile_id,
        target_type=target_type,
        target_product=target_product,
        probe_runner_id="connector-probe-runner.isolated-read-only",
        probe_runner_version="runner-v1",
        network_zone_id="network-zone.development-management",
        configuration_result="configuration.valid",
        connectivity_result="connectivity.reachable",
        tls_result="tls.trusted",
        endpoint_identity_result="endpoint-identity.matched",
        authentication_result="authentication.succeeded",
        authorization_result="authorization.read-only-confirmed",
        product_identity_result="product-identity.matched",
        latency_band="latency.normal",
        completed_checks=(
            "check.configuration",
            "check.connectivity",
            "check.tls",
            "check.endpoint-identity",
            "check.authentication",
            "check.read-only-authorization",
            "check.product-identity",
        ),
        signed_by="workload.connector-probe-attestor",
        signature_verified=True,
        observed_at=issued_at,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))


def build_development_connector_configuration_validation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorConfigurationValidationPolicySnapshot:
    snapshot = ConnectorConfigurationValidationPolicySnapshot(
        policy_id="connector-configuration-validation-policy.development",
        schema_version="atlas.connector-configuration-validation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_assignment_schema="atlas.connector-credential-assignment.v1",
        required_evidence_schema="atlas.connector-configuration-evidence.v1",
        required_evidence_signer_id="workload.connector-probe-attestor",
        allowed_probe_runner_ids=("connector-probe-runner.isolated-read-only",),
        allowed_network_zone_ids=("network-zone.development-management",),
        required_checks=(
            "check.configuration",
            "check.connectivity",
            "check.tls",
            "check.endpoint-identity",
            "check.authentication",
            "check.read-only-authorization",
            "check.product-identity",
        ),
        maximum_assignment_age_hours=8760,
        maximum_observation_age_minutes=10080,
        required_configuration_result="configuration.valid",
        required_connectivity_result="connectivity.reachable",
        required_tls_result="tls.trusted",
        required_endpoint_identity_result="endpoint-identity.matched",
        required_authentication_result="authentication.succeeded",
        required_authorization_result="authorization.read-only-confirmed",
        required_product_identity_result="product-identity.matched",
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        required_effective_state=DISABLED_CONFIGURATION_VALIDATED,
        validation_record_schema=CONFIGURATION_VALIDATION_SCHEMA,
        signed_by="human.configuration-validation-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=_signed_snapshot(snapshot))
