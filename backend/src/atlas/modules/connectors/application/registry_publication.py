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
from atlas.modules.connectors.application.final_validation_ports import PackageFinalValidationError
from atlas.modules.connectors.application.package_approval_ports import PackageApprovalError
from atlas.modules.connectors.application.package_signing_ports import PackageSigningError
from atlas.modules.connectors.application.registry_publication_ports import (
    InternalRegistryPublisher,
    PackageSignatureVerifier,
    RegistryPublicationApprovalSource,
    RegistryPublicationError,
    RegistryPublicationFinalSource,
    RegistryPublicationPolicySource,
    RegistryPublicationRepository,
    RegistryPublicationSigningSource,
)
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.package_signing import ConnectorPackageSigningReceipt
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorInternalRegistryPublicationResult,
    ConnectorPackageSignatureVerification,
    ConnectorRegistryPublicationPolicySnapshot,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff

PUBLICATION_CREATE_PERMISSION = "connectors.registry-publication-receipts.create"
PUBLICATION_READ_PERMISSION = "connectors.registry-publication-receipts.read"
PUBLICATION_RECEIPT_SCHEMA = "atlas.connector-registry-publication-receipt.v1"


class RegistryPublicationService:
    def __init__(
        self,
        *,
        repository: RegistryPublicationRepository,
        signing_source: RegistryPublicationSigningSource,
        approval_source: RegistryPublicationApprovalSource,
        final_source: RegistryPublicationFinalSource,
        policy_source: RegistryPublicationPolicySource,
        signature_verifier: PackageSignatureVerifier,
        publisher: InternalRegistryPublisher,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._signing_source = signing_source
        self._approval_source = approval_source
        self._final_source = final_source
        self._policy_source = policy_source
        self._signature_verifier = signature_verifier
        self._publisher = publisher
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> RegistryPublicationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_signing_receipt_id: str,
        source_signing_receipt_digest: str,
        package_digest: str,
        publication_policy_id: str,
        publication_policy_digest: str,
        purpose: str,
        acknowledged_publication_grants_no_runtime_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorInternalRegistryPublicationReceipt:
        self._require_enterprise_human(actor)
        if not acknowledged_publication_grants_no_runtime_authority:
            raise RegistryPublicationError("registry_publication_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise RegistryPublicationError("registry_publication_request_invalid")
        fingerprint = self._digest(
            {
                "source_signing_receipt_id": source_signing_receipt_id,
                "source_signing_receipt_digest": source_signing_receipt_digest,
                "package_digest": package_digest,
                "publication_policy_id": publication_policy_id,
                "publication_policy_digest": publication_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            requested_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)

        try:
            (
                signing,
                signing_policy,
                signing_actors,
            ) = await self._signing_source.registry_publication_source(
                receipt_id=source_signing_receipt_id
            )
            approval, approval_actors = await self._approval_source.publisher_attestation_source(
                request_id=signing.envelope.source_approval_request_id
            )
            (
                final,
                acquisition,
                content,
                final_actors,
            ) = await self._final_source.registry_publication_source(
                validation_id=approval.request.source_final_validation_id
            )
        except (PackageSigningError, PackageApprovalError, PackageFinalValidationError) as error:
            raise RegistryPublicationError("registry_publication_source_not_found") from error
        policy = await self._policy_source.get_by_id(policy_id=publication_policy_id)
        if policy is None:
            raise RegistryPublicationError("registry_publication_policy_not_found")
        self._verify_policy(policy)
        self._require_scope(actor, signing.organization_id, signing.environment_id)
        now = self._clock()
        if (
            signing.canonical_digest != source_signing_receipt_digest
            or signing.envelope.package_digest != package_digest
            or signing.envelope.source_approval_request_digest != approval.request.canonical_digest
            or approval.request.source_final_validation_digest != final.canonical_digest
            or approval.request.package_digest != final.package_digest
            or final.package_digest != acquisition.package_digest
            or acquisition.package_digest != package_digest
            or not (
                signing.organization_id
                == approval.request.organization_id
                == final.organization_id
                == acquisition.organization_id
                == policy.organization_id
            )
            or not (
                signing.environment_id
                == approval.request.environment_id
                == final.environment_id
                == acquisition.environment_id
                == policy.environment_id
            )
            or policy.canonical_digest != publication_policy_digest
            or policy.required_signing_receipt_schema != signing.schema_version
            or policy.required_signing_envelope_schema != signing.envelope.schema_version
            or policy.required_signer_profile_id != signing.signature.signer_profile_id
            or policy.required_signer_workload_id != signing.signature.signer_workload_id
            or policy.required_key_id != signing.signature.key_id
            or policy.required_algorithm != signing.signature.algorithm
            or policy.receipt_schema != PUBLICATION_RECEIPT_SCHEMA
            or acquisition.package_size_bytes > policy.maximum_package_bytes
            or not policy.issued_at <= now < policy.expires_at
            or signing.signed_at > now
            or now - signing.signed_at > timedelta(hours=policy.maximum_signing_age_hours)
            or not signing.signature.issued_at <= now < signing.signature.expires_at
            or not approval.approval_valid
            or not final.eligible_for_human_approval
            or not acquisition.integrity_verified
            or (
                policy.required_assurance_level is AssuranceLevel.HARDWARE_BACKED
                and actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
            )
        ):
            raise RegistryPublicationError("registry_publication_binding_invalid")
        forbidden = (
            signing_actors
            | approval_actors
            | final_actors
            | {
                policy.signed_by,
                policy.verifier_workload_id,
                policy.publisher_workload_id,
                policy.registry_custodian_id,
            }
        )
        if actor.subject_id in forbidden:
            raise RegistryPublicationError("registry_publication_separation_required")

        if (
            len(content) != acquisition.package_size_bytes
            or sha256(content).hexdigest() != acquisition.package_digest
        ):
            raise RegistryPublicationError("registry_publication_archive_integrity_failed")
        verification = await self._signature_verifier.verify(
            receipt=signing,
            signing_policy=signing_policy,
            publication_policy=policy,
            verified_at=now,
        )
        self._verify_signature_verification(verification, signing, policy, now)

        async with self._mutation_lock:
            prior = await self._repository.get_by_signing_receipt(
                source_signing_receipt_id=signing.receipt_id
            )
            if prior is not None:
                if (
                    prior.requested_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise RegistryPublicationError("registry_publication_receipt_exists")
            await self._audit(
                actor,
                correlation_id,
                "connector_registry_publication_requested",
                signing.receipt_id,
                idempotency_key,
                (("package_digest", package_digest),),
            )
            publication = await self._publisher.publish(
                content=content,
                source_signing_receipt_digest=signing.canonical_digest,
                policy=policy,
                published_at=now,
                idempotency_key=idempotency_key,
            )
            self._verify_publication(publication, signing, acquisition, policy, now)
            receipt_seed = self._digest([signing.receipt_id, publication.publication_digest])
            receipt = ConnectorInternalRegistryPublicationReceipt(
                receipt_id=f"connector-registry-publication-receipt.{receipt_seed[:24]}",
                schema_version=PUBLICATION_RECEIPT_SCHEMA,
                version=1,
                source_signing_receipt_id=signing.receipt_id,
                source_signing_receipt_digest=signing.canonical_digest,
                source_approval_request_id=approval.request.request_id,
                source_approval_request_digest=approval.request.canonical_digest,
                source_final_validation_id=final.validation_id,
                source_final_validation_digest=final.canonical_digest,
                source_acquisition_id=acquisition.acquisition_id,
                source_acquisition_digest=acquisition.canonical_digest,
                organization_id=signing.organization_id,
                environment_id=signing.environment_id,
                package_digest=signing.envelope.package_digest,
                package_size_bytes=acquisition.package_size_bytes,
                publisher_id=signing.envelope.publisher_id,
                connector_id=signing.envelope.connector_id,
                release_version=signing.envelope.release_version,
                provenance_digest=signing.envelope.provenance_digest,
                publication_policy_id=policy.policy_id,
                publication_policy_digest=policy.canonical_digest,
                publication_policy_version=policy.policy_version,
                verification=verification,
                publication=publication,
                requested_by=actor.subject_id,
                purpose=purpose,
                published_at=publication.published_at,
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
                "connector_registry_publication_completed",
                receipt.receipt_id,
                idempotency_key,
                (
                    ("publication_digest", publication.publication_digest),
                    ("registry_profile_id", publication.registry_profile_id),
                ),
            )
            if not await self._repository.add(receipt):
                raced = await self._repository.get_by_create_key(
                    requested_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise RegistryPublicationError("registry_publication_receipt_conflict")
                self._verify_receipt(raced)
                return replace(raced, reused=True)
        return receipt

    async def get(
        self, *, actor: AuthenticatedSubject, receipt_id: str, correlation_id: str
    ) -> ConnectorInternalRegistryPublicationReceipt:
        self._require_enterprise_human(actor)
        receipt = await self._repository.get(receipt_id=receipt_id)
        if receipt is None:
            raise RegistryPublicationError("registry_publication_receipt_not_found")
        self._verify_receipt(receipt)
        self._require_scope(actor, receipt.organization_id, receipt.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "connector_registry_publication_read",
            receipt.receipt_id,
            None,
            (),
            permission_id=PUBLICATION_READ_PERMISSION,
        )
        return receipt

    async def package_registration_source(
        self, *, receipt_id: str
    ) -> tuple[
        ConnectorInternalRegistryPublicationReceipt,
        McpBuilderCandidateHandoff,
        frozenset[str],
    ]:
        """Reverify the complete publication lineage for package registration governance."""
        receipt = await self._repository.get(receipt_id=receipt_id)
        if receipt is None:
            raise RegistryPublicationError("registry_publication_receipt_not_found")
        self._verify_receipt(receipt)
        policy = await self._policy_source.get_by_id(policy_id=receipt.publication_policy_id)
        if policy is None:
            raise RegistryPublicationError("registry_publication_policy_not_found")
        self._verify_policy(policy)
        try:
            signing, _, signing_actors = await self._signing_source.registry_publication_source(
                receipt_id=receipt.source_signing_receipt_id
            )
            approval, approval_actors = await self._approval_source.publisher_attestation_source(
                request_id=receipt.source_approval_request_id
            )
            (
                final,
                handoff,
                acquisition,
                final_actors,
            ) = await self._final_source.package_registration_source(
                validation_id=receipt.source_final_validation_id
            )
        except (PackageSigningError, PackageApprovalError, PackageFinalValidationError) as error:
            raise RegistryPublicationError("registry_publication_source_not_found") from error
        if (
            receipt.source_signing_receipt_digest != signing.canonical_digest
            or receipt.source_approval_request_digest != approval.request.canonical_digest
            or receipt.source_final_validation_digest != final.canonical_digest
            or receipt.source_acquisition_id != acquisition.acquisition_id
            or receipt.source_acquisition_digest != acquisition.canonical_digest
            or receipt.package_digest != signing.envelope.package_digest
            or receipt.package_digest != final.package_digest
            or receipt.publisher_id != signing.envelope.publisher_id
            or receipt.connector_id != signing.envelope.connector_id
            or receipt.release_version != signing.envelope.release_version
            or receipt.provenance_digest != signing.envelope.provenance_digest
            or receipt.publication_policy_digest != policy.canonical_digest
            or receipt.publication.registry_profile_id != policy.registry_profile_id
            or receipt.publication.publisher_workload_id != policy.publisher_workload_id
            or receipt.publication.artifact_reference_schema != policy.artifact_reference_schema
            or receipt.publication.package_digest != receipt.package_digest
            or not (
                receipt.organization_id
                == signing.organization_id
                == approval.request.organization_id
                == final.organization_id
                == handoff.organization_id
                == policy.organization_id
            )
            or not (
                receipt.environment_id
                == signing.environment_id
                == approval.request.environment_id
                == final.environment_id
                == handoff.environment_id
                == policy.environment_id
            )
            or not receipt.package_published
            or not receipt.eligible_for_registration_governance
            or receipt.promotion_blocked
            or any(
                (
                    receipt.connector_registered,
                    receipt.connector_installed,
                    receipt.connector_enabled,
                    receipt.target_configured,
                    receipt.credentials_resolved,
                    receipt.runtime_trust_granted,
                    receipt.execution_authorized,
                    receipt.deployment_approved,
                    receipt.infrastructure_mutation_performed,
                )
            )
        ):
            raise RegistryPublicationError("registry_publication_not_eligible_for_registration")
        return (
            receipt,
            handoff,
            signing_actors
            | approval_actors
            | final_actors
            | {
                receipt.requested_by,
                policy.signed_by,
                policy.verifier_workload_id,
                policy.publisher_workload_id,
                policy.registry_custodian_id,
            },
        )

    async def close(self) -> None:
        await self._repository.close()

    def _reuse(
        self,
        receipt: ConnectorInternalRegistryPublicationReceipt,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorInternalRegistryPublicationReceipt:
        if receipt.requested_by != actor.subject_id or receipt.request_fingerprint != fingerprint:
            raise RegistryPublicationError("registry_publication_idempotency_conflict")
        self._verify_receipt(receipt)
        return replace(receipt, reused=True)

    @classmethod
    def _verify_policy(cls, policy: ConnectorRegistryPublicationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise RegistryPublicationError("registry_publication_policy_integrity_failed")

    @staticmethod
    def _verify_signature_verification(
        verification: ConnectorPackageSignatureVerification,
        signing: ConnectorPackageSigningReceipt,
        policy: ConnectorRegistryPublicationPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            verification.verifier_profile_id != policy.verifier_profile_id
            or verification.verifier_workload_id != policy.verifier_workload_id
            or verification.key_id != signing.signature.key_id
            or verification.algorithm != signing.signature.algorithm
            or verification.envelope_digest != signing.envelope.canonical_digest
            or verification.signature_digest != signing.signature.signature_digest
            or verification.verified_at != now
            or not verification.signature_valid
        ):
            raise RegistryPublicationError("registry_publication_signature_invalid")

    @staticmethod
    def _verify_publication(
        publication: ConnectorInternalRegistryPublicationResult,
        signing: ConnectorPackageSigningReceipt,
        acquisition: ConnectorPackageAcquisition,
        policy: ConnectorRegistryPublicationPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            publication.registry_profile_id != policy.registry_profile_id
            or publication.publisher_workload_id != policy.publisher_workload_id
            or publication.artifact_reference_schema != policy.artifact_reference_schema
            or publication.package_digest != signing.envelope.package_digest
            or publication.package_size_bytes != acquisition.package_size_bytes
            or publication.source_signing_receipt_digest != signing.canonical_digest
            or publication.published_at != now
            or not publication.integrity_verified
        ):
            raise RegistryPublicationError("registry_publication_result_invalid")

    @classmethod
    def _verify_receipt(cls, receipt: ConnectorInternalRegistryPublicationReceipt) -> None:
        if cls._digest(cls._receipt_payload(receipt)) != receipt.canonical_digest:
            raise RegistryPublicationError("registry_publication_receipt_integrity_failed")

    @classmethod
    def _receipt_payload(
        cls, receipt: ConnectorInternalRegistryPublicationReceipt
    ) -> dict[str, object]:
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
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise RegistryPublicationError("registry_publication_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise RegistryPublicationError("registry_publication_receipt_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = PUBLICATION_CREATE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.registry-publication",
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
                resource_type="resource.connector.registry-publication-receipt",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )


def build_development_registry_publication_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorRegistryPublicationPolicySnapshot:
    policy = ConnectorRegistryPublicationPolicySnapshot(
        policy_id="connector-registry-publication-policy.development",
        schema_version="atlas.connector-registry-publication-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_signing_receipt_schema="atlas.connector-package-signing-receipt.v1",
        required_signing_envelope_schema="atlas.connector-package-signing-envelope.v1",
        maximum_signing_age_hours=168,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        required_signer_profile_id="signer-profile.nonproduction-hmac",
        required_signer_workload_id="workload.connector-package-signer",
        required_key_id="key.connector-package-signing.nonproduction",
        required_algorithm="algorithm.hmac-sha256-nonproduction",
        verifier_profile_id="verifier-profile.nonproduction-hmac",
        verifier_workload_id="workload.connector-package-signature-verifier",
        registry_profile_id="registry-profile.nonproduction-internal",
        publisher_workload_id="workload.connector-registry-publisher",
        registry_custodian_id="subject.connector-registry-custodian",
        artifact_reference_schema="atlas.connector-registry-artifact-reference.v1",
        receipt_schema=PUBLICATION_RECEIPT_SCHEMA,
        maximum_package_bytes=25_000_000,
        signed_by="subject.registry-publication-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=RegistryPublicationService._digest(
            RegistryPublicationService._normalize(payload)
        ),
    )
