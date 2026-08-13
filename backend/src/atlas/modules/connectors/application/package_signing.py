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
from atlas.modules.connectors.application.package_signing_ports import (
    PackageSigner,
    PackageSigningAttestationSource,
    PackageSigningError,
    PackageSigningPolicySource,
    PackageSigningRepository,
)
from atlas.modules.connectors.application.publisher_attestation_ports import (
    PublisherAttestationError,
)
from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSignatureResult,
    ConnectorPackageSigningEnvelope,
    ConnectorPackageSigningPolicySnapshot,
    ConnectorPackageSigningReceipt,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

SIGNING_CREATE_PERMISSION = "connectors.package-signing-receipts.create"
SIGNING_READ_PERMISSION = "connectors.package-signing-receipts.read"
ENVELOPE_SCHEMA = "atlas.connector-package-signing-envelope.v1"
RECEIPT_SCHEMA = "atlas.connector-package-signing-receipt.v1"


class PackageSigningService:
    def __init__(
        self,
        *,
        repository: PackageSigningRepository,
        attestation_source: PackageSigningAttestationSource,
        policy_source: PackageSigningPolicySource,
        signer: PackageSigner,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._attestation_source = attestation_source
        self._policy_source = policy_source
        self._signer = signer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> PackageSigningRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_attestation_report_id: str,
        source_attestation_report_digest: str,
        package_digest: str,
        signing_policy_id: str,
        signing_policy_digest: str,
        purpose: str,
        acknowledged_signing_grants_no_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageSigningReceipt:
        self._require_enterprise_human(actor)
        if not acknowledged_signing_grants_no_runtime_authority:
            raise PackageSigningError("package_signing_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise PackageSigningError("package_signing_request_invalid")
        fingerprint = self._digest(
            {
                "source_attestation_report_id": source_attestation_report_id,
                "source_attestation_report_digest": source_attestation_report_digest,
                "package_digest": package_digest,
                "signing_policy_id": signing_policy_id,
                "signing_policy_digest": signing_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)

        try:
            attestation, forbidden = await self._attestation_source.package_signing_source(
                report_id=source_attestation_report_id
            )
        except PublisherAttestationError as error:
            raise PackageSigningError("package_signing_attestation_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=signing_policy_id)
        if policy is None:
            raise PackageSigningError("package_signing_policy_not_found")
        self._verify_policy(policy)
        self._require_scope(actor, attestation.organization_id, attestation.environment_id)
        now = self._clock()
        if (
            attestation.canonical_digest != source_attestation_report_digest
            or attestation.package_digest != package_digest
            or not attestation.publisher_attested
            or not attestation.eligible_for_package_signing_governance
            or attestation.promotion_blocked
            or policy.canonical_digest != signing_policy_digest
            or policy.organization_id != attestation.organization_id
            or policy.environment_id != attestation.environment_id
            or policy.required_attestation_schema != attestation.schema_version
            or policy.envelope_schema != ENVELOPE_SCHEMA
            or policy.receipt_schema != RECEIPT_SCHEMA
            or not policy.issued_at <= now < policy.expires_at
            or attestation.verified_at > now
            or now - attestation.verified_at > timedelta(hours=policy.maximum_attestation_age_hours)
            or not assurance_satisfies_policy(
                actor.assurance_level, policy.required_assurance_level
            )
        ):
            raise PackageSigningError("package_signing_binding_invalid")
        if actor.subject_id in forbidden | {
            policy.signed_by,
            policy.signer_workload_id,
            policy.key_custodian_id,
        }:
            raise PackageSigningError("package_signing_separation_required")

        envelope_seed = self._digest(
            [
                attestation.report_id,
                attestation.canonical_digest,
                policy.canonical_digest,
                actor.subject_id,
                purpose,
            ]
        )
        envelope = ConnectorPackageSigningEnvelope(
            envelope_id=f"connector-package-signing-envelope.{envelope_seed[:24]}",
            schema_version=ENVELOPE_SCHEMA,
            version=1,
            source_attestation_report_id=attestation.report_id,
            source_attestation_report_digest=attestation.canonical_digest,
            source_approval_request_id=attestation.source_approval_request_id,
            source_approval_request_digest=attestation.source_approval_request_digest,
            source_approval_decision_id=attestation.source_approval_decision_id,
            source_approval_decision_digest=attestation.source_approval_decision_digest,
            organization_id=attestation.organization_id,
            environment_id=attestation.environment_id,
            package_digest=attestation.package_digest,
            publisher_id=attestation.publisher_id,
            connector_id=attestation.connector_id,
            release_version=attestation.release_version,
            provenance_digest=attestation.provenance_digest,
            publisher_claim_id=attestation.publisher_claim_id,
            publisher_claim_digest=attestation.publisher_claim_digest,
            attestation_policy_id=attestation.attestation_policy_id,
            attestation_policy_digest=attestation.attestation_policy_digest,
            signing_policy_id=policy.policy_id,
            signing_policy_digest=policy.canonical_digest,
            signing_policy_version=policy.policy_version,
            signer_profile_id=policy.signer_profile_id,
            requested_by=actor.subject_id,
            purpose=purpose,
            created_at=now,
            canonical_digest="0" * 64,
        )
        envelope = replace(
            envelope, canonical_digest=self._digest(self._envelope_payload(envelope))
        )

        async with self._mutation_lock:
            prior = await self._repository.get_by_attestation(
                source_attestation_report_id=attestation.report_id
            )
            if prior is not None:
                if (
                    prior.requested_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise PackageSigningError("package_signing_receipt_exists")
            await self._audit(
                actor,
                correlation_id,
                "connector_package_signing_requested",
                envelope.envelope_id,
                idempotency_key,
                (("envelope_digest", envelope.canonical_digest),),
            )
            try:
                signature = await self._signer.sign(
                    envelope=envelope,
                    policy=policy,
                    idempotency_key=idempotency_key,
                )
            except PackageSigningError:
                raise
            except Exception as error:
                raise PackageSigningError("package_signing_signer_unavailable") from error
            self._verify_signature(signature, envelope, policy, now)
            receipt_seed = self._digest([envelope.envelope_id, signature.signature_digest])
            receipt = ConnectorPackageSigningReceipt(
                receipt_id=f"connector-package-signing-receipt.{receipt_seed[:24]}",
                schema_version=RECEIPT_SCHEMA,
                version=1,
                envelope=envelope,
                signature=signature,
                organization_id=envelope.organization_id,
                environment_id=envelope.environment_id,
                requested_by=actor.subject_id,
                signing_policy_id=policy.policy_id,
                signing_policy_digest=policy.canonical_digest,
                signed_at=signature.issued_at,
                canonical_digest="0" * 64,
                request_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            receipt = replace(
                receipt, canonical_digest=self._digest(self._receipt_payload(receipt))
            )
            await self._audit(
                actor,
                correlation_id,
                "connector_package_signing_completed",
                receipt.receipt_id,
                idempotency_key,
                (
                    ("signature_digest", signature.signature_digest),
                    ("signer_workload_id", signature.signer_workload_id),
                ),
            )
            if not await self._repository.add(receipt):
                raced = await self._repository.get_by_create_key(
                    requested_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageSigningError("package_signing_receipt_conflict")
                self._verify_receipt(raced)
                receipt = replace(raced, reused=True)
        return receipt

    async def get(
        self, *, actor: AuthenticatedSubject, receipt_id: str, correlation_id: str
    ) -> ConnectorPackageSigningReceipt:
        self._require_enterprise_human(actor)
        receipt = await self._repository.get(receipt_id=receipt_id)
        if receipt is None:
            raise PackageSigningError("package_signing_receipt_not_found")
        self._verify_receipt(receipt)
        self._require_scope(actor, receipt.organization_id, receipt.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_package_signing_read",
            receipt.receipt_id,
            None,
            (),
            permission_id=SIGNING_READ_PERMISSION,
        )
        return receipt

    async def registry_publication_source(
        self, *, receipt_id: str
    ) -> tuple[
        ConnectorPackageSigningReceipt,
        ConnectorPackageSigningPolicySnapshot,
        frozenset[str],
    ]:
        """Reverify the complete signing lineage for internal registry governance."""
        receipt = await self._repository.get(receipt_id=receipt_id)
        if receipt is None:
            raise PackageSigningError("package_signing_receipt_not_found")
        self._verify_receipt(receipt)
        try:
            attestation, upstream = await self._attestation_source.package_signing_source(
                report_id=receipt.envelope.source_attestation_report_id
            )
        except PublisherAttestationError as error:
            raise PackageSigningError("package_signing_attestation_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=receipt.signing_policy_id)
        if policy is None:
            raise PackageSigningError("package_signing_policy_not_found")
        self._verify_policy(policy)
        now = self._clock()
        self._verify_signature(receipt.signature, receipt.envelope, policy, receipt.signed_at)
        if (
            receipt.envelope.source_attestation_report_digest != attestation.canonical_digest
            or receipt.envelope.package_digest != attestation.package_digest
            or receipt.signing_policy_digest != policy.canonical_digest
            or receipt.envelope.signing_policy_digest != policy.canonical_digest
            or receipt.envelope.signing_policy_id != policy.policy_id
            or receipt.envelope.signer_profile_id != policy.signer_profile_id
            or not (
                receipt.organization_id == attestation.organization_id == policy.organization_id
            )
            or not (receipt.environment_id == attestation.environment_id == policy.environment_id)
            or not policy.issued_at <= now < policy.expires_at
            or not receipt.signature.issued_at <= now < receipt.signature.expires_at
            or not receipt.package_signed
            or not receipt.publisher_attested
            or not receipt.eligible_for_registry_governance
            or receipt.promotion_blocked
        ):
            raise PackageSigningError("package_signing_not_eligible_for_registry")
        return (
            receipt,
            policy,
            upstream
            | {
                receipt.requested_by,
                policy.signed_by,
                policy.signer_workload_id,
                policy.key_custodian_id,
            },
        )

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        receipt: ConnectorPackageSigningReceipt,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorPackageSigningReceipt:
        if receipt.requested_by != actor.subject_id or receipt.request_fingerprint != fingerprint:
            raise PackageSigningError("package_signing_idempotency_conflict")
        self._verify_receipt(receipt)
        return replace(receipt, reused=True)

    @classmethod
    def _verify_policy(cls, policy: ConnectorPackageSigningPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise PackageSigningError("package_signing_policy_integrity_failed")

    @staticmethod
    def _verify_signature(
        signature: ConnectorPackageSignatureResult,
        envelope: ConnectorPackageSigningEnvelope,
        policy: ConnectorPackageSigningPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            signature.signer_profile_id != policy.signer_profile_id
            or signature.signer_workload_id != policy.signer_workload_id
            or signature.key_id != policy.key_id
            or signature.algorithm != policy.algorithm
            or signature.envelope_digest != envelope.canonical_digest
            or signature.issued_at != now
            or signature.expires_at != now + timedelta(hours=policy.signature_lifetime_hours)
            or not signature.signature_verified
        ):
            raise PackageSigningError("package_signing_signature_invalid")

    @classmethod
    def _verify_receipt(cls, receipt: ConnectorPackageSigningReceipt) -> None:
        if (
            cls._digest(cls._envelope_payload(receipt.envelope))
            != receipt.envelope.canonical_digest
            or cls._digest(cls._receipt_payload(receipt)) != receipt.canonical_digest
            or sha256(cls._signature_bytes(receipt.signature.signature_value)).hexdigest()
            != receipt.signature.signature_digest
        ):
            raise PackageSigningError("package_signing_receipt_integrity_failed")

    @staticmethod
    def _signature_bytes(value: str) -> bytes:
        import base64

        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    @classmethod
    def _envelope_payload(cls, envelope: ConnectorPackageSigningEnvelope) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(envelope))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_payload(cls, receipt: ConnectorPackageSigningReceipt) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(receipt))
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
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise PackageSigningError("package_signing_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageSigningError("package_signing_receipt_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = SIGNING_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-signing",
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
                resource_type="resource.connector.package-signing-receipt",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_development_package_signing_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorPackageSigningPolicySnapshot:
    policy = ConnectorPackageSigningPolicySnapshot(
        policy_id="connector-package-signing-policy.development",
        schema_version="atlas.connector-package-signing-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_attestation_schema="atlas.connector-publisher-attestation.v1",
        maximum_attestation_age_hours=168,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signer_profile_id="signer-profile.nonproduction-hmac",
        signer_workload_id="workload.connector-package-signer",
        key_id="key.connector-package-signing.nonproduction",
        key_custodian_id="subject.connector-signing-key-custodian",
        algorithm="algorithm.hmac-sha256-nonproduction",
        envelope_schema=ENVELOPE_SCHEMA,
        receipt_schema=RECEIPT_SCHEMA,
        signature_lifetime_hours=168,
        signed_by="subject.package-signing-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=PackageSigningService._digest(PackageSigningService._normalize(payload)),
    )
