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
from atlas.modules.connectors.application.package_approval_ports import PackageApprovalError
from atlas.modules.connectors.application.publisher_attestation_ports import (
    PublisherAttestationApprovalSource,
    PublisherAttestationError,
    PublisherAttestationPolicySource,
    PublisherAttestationRepository,
    PublisherClaimSource,
)
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationPolicySnapshot,
    ConnectorPublisherAttestationReport,
    ConnectorPublisherClaimSnapshot,
    PublisherAttestationOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

ATTESTATION_SCHEMA = "atlas.connector-publisher-attestation.v1"
ATTESTATION_CREATE_PERMISSION = "connectors.publisher-attestations.create"
ATTESTATION_READ_PERMISSION = "connectors.publisher-attestations.read"
CHECK_CODES = (
    "check.approval.current",
    "check.package.bound",
    "check.claim.signature",
    "check.claim.freshness",
    "check.publisher.ownership",
    "check.publisher.support",
    "check.provenance.bound",
    "check.issuer.trusted",
    "check.actor.separation",
)


class PublisherAttestationService:
    def __init__(
        self,
        *,
        repository: PublisherAttestationRepository,
        approval_source: PublisherAttestationApprovalSource,
        claim_source: PublisherClaimSource,
        policy_source: PublisherAttestationPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._approval_source = approval_source
        self._claim_source = claim_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> PublisherAttestationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_approval_request_id: str,
        source_approval_request_digest: str,
        package_digest: str,
        publisher_claim_id: str,
        publisher_claim_digest: str,
        attestation_policy_id: str,
        attestation_policy_digest: str,
        purpose: str,
        acknowledged_attestation_grants_no_lifecycle_authority: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPublisherAttestationReport:
        self._require_enterprise_human(actor)
        if not acknowledged_attestation_grants_no_lifecycle_authority:
            raise PublisherAttestationError("publisher_attestation_acknowledgement_required")
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise PublisherAttestationError("publisher_attestation_request_invalid")
        fingerprint = self._digest(
            {
                "source_approval_request_id": source_approval_request_id,
                "source_approval_request_digest": source_approval_request_digest,
                "package_digest": package_digest,
                "publisher_claim_id": publisher_claim_id,
                "publisher_claim_digest": publisher_claim_digest,
                "attestation_policy_id": attestation_policy_id,
                "attestation_policy_digest": attestation_policy_digest,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            verified_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            if (
                existing.verified_by != actor.subject_id
                or existing.request_fingerprint != fingerprint
            ):
                raise PublisherAttestationError("publisher_attestation_idempotency_conflict")
            self._verify_report(existing)
            return replace(existing, reused=True)

        try:
            approval, forbidden = await self._approval_source.publisher_attestation_source(
                request_id=source_approval_request_id
            )
        except PackageApprovalError as error:
            raise PublisherAttestationError("publisher_attestation_approval_not_found") from error
        claim = await self._claim_source.get_by_id(claim_id=publisher_claim_id)
        policy = await self._policy_source.get_by_id(policy_id=attestation_policy_id)
        if claim is None or policy is None:
            raise PublisherAttestationError("publisher_attestation_evidence_not_found")
        self._verify_claim(claim)
        self._verify_policy(policy)
        request = approval.request
        decision = approval.decision
        if decision is None:
            raise PublisherAttestationError("publisher_attestation_approval_not_eligible")
        self._require_scope(actor, request.organization_id, request.environment_id)
        now = self._clock()
        if (
            request.canonical_digest != source_approval_request_digest
            or request.package_digest != package_digest
            or claim.canonical_digest != publisher_claim_digest
            or claim.package_digest != package_digest
            or policy.canonical_digest != attestation_policy_digest
            or claim.organization_id != request.organization_id
            or policy.organization_id != request.organization_id
            or claim.environment_id != request.environment_id
            or policy.environment_id != request.environment_id
            or policy.required_approval_schema != request.schema_version
            or policy.required_claim_schema != claim.schema_version
            or not policy.issued_at <= now < policy.expires_at
            or not claim.issued_at <= now < claim.expires_at
            or request.created_at > now
            or claim.issued_at > now
            or now - request.created_at > timedelta(hours=policy.maximum_approval_age_hours)
            or now - claim.issued_at > timedelta(hours=policy.maximum_claim_age_hours)
            or not claim.signature_verified
            or not claim.grants_no_runtime_authority
            or claim.issued_by not in policy.trusted_issuer_ids
        ):
            raise PublisherAttestationError("publisher_attestation_binding_invalid")
        separated = forbidden | {
            claim.issued_by,
            claim.publisher_id,
            policy.signed_by,
        }
        if actor.subject_id in separated:
            raise PublisherAttestationError("publisher_attestation_separation_required")

        reason_codes: list[str] = []
        if not claim.ownership_asserted:
            reason_codes.append("reason.ownership.not_asserted")
        if not claim.support_responsibility_asserted:
            reason_codes.append("reason.support.not_asserted")
        if claim.support_expires_at < now + timedelta(days=policy.minimum_support_validity_days):
            reason_codes.append("reason.support.validity_insufficient")
        outcome = (
            PublisherAttestationOutcome.REJECTED
            if reason_codes
            else PublisherAttestationOutcome.VERIFIED
        )
        passed = outcome is PublisherAttestationOutcome.VERIFIED
        report_seed = self._digest(
            [
                request.request_id,
                decision.decision_id,
                claim.claim_id,
                policy.policy_id,
            ]
        )
        report = ConnectorPublisherAttestationReport(
            report_id=f"connector-publisher-attestation.{report_seed[:24]}",
            schema_version=ATTESTATION_SCHEMA,
            version=1,
            source_approval_request_id=request.request_id,
            source_approval_request_digest=request.canonical_digest,
            source_approval_decision_id=decision.decision_id,
            source_approval_decision_digest=decision.canonical_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            verified_by=actor.subject_id,
            purpose=purpose,
            package_digest=request.package_digest,
            publisher_claim_id=claim.claim_id,
            publisher_claim_digest=claim.canonical_digest,
            publisher_id=claim.publisher_id,
            publisher_display_name=claim.publisher_display_name,
            connector_id=claim.connector_id,
            release_version=claim.release_version,
            provenance_digest=claim.provenance_digest,
            support_contact_ref=claim.support_contact_ref,
            support_expires_at=claim.support_expires_at,
            claim_issued_by=claim.issued_by,
            attestation_policy_id=policy.policy_id,
            attestation_policy_digest=policy.canonical_digest,
            attestation_policy_version=policy.policy_version,
            check_codes=CHECK_CODES,
            outcome=outcome,
            reason_codes=tuple(reason_codes),
            verified_at=now,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            publisher_attested=passed,
            eligible_for_package_signing_governance=passed,
            promotion_blocked=not passed,
        )
        report = replace(report, canonical_digest=self._digest(self._report_payload(report)))
        async with self._mutation_lock:
            prior = await self._repository.get_by_approval(
                source_approval_request_id=request.request_id
            )
            if prior is not None:
                if (
                    prior.verified_by == actor.subject_id
                    and prior.request_fingerprint == fingerprint
                ):
                    return replace(prior, reused=True)
                raise PublisherAttestationError("publisher_attestation_report_exists")
            await self._audit(
                actor,
                correlation_id,
                ATTESTATION_CREATE_PERMISSION,
                f"connector_publisher_attestation_{outcome.value}",
                report,
            )
            if not await self._repository.add(report):
                raced = await self._repository.get_by_create_key(
                    verified_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PublisherAttestationError("publisher_attestation_conflict")
                report = replace(raced, reused=True)
        return report

    async def get(
        self, *, actor: AuthenticatedSubject, report_id: str, correlation_id: str
    ) -> ConnectorPublisherAttestationReport:
        self._require_enterprise_human(actor)
        report = await self._repository.get(report_id=report_id)
        if report is None:
            raise PublisherAttestationError("publisher_attestation_report_not_found")
        self._verify_report(report)
        self._require_scope(actor, report.organization_id, report.environment_id)
        await self._audit(
            actor,
            correlation_id,
            ATTESTATION_READ_PERMISSION,
            "connector_publisher_attestation_read",
            report,
        )
        return report

    async def package_signing_source(
        self, *, report_id: str
    ) -> tuple[ConnectorPublisherAttestationReport, frozenset[str]]:
        report = await self._repository.get(report_id=report_id)
        if report is None:
            raise PublisherAttestationError("publisher_attestation_report_not_found")
        self._verify_report(report)
        try:
            approval, upstream = await self._approval_source.publisher_attestation_source(
                request_id=report.source_approval_request_id
            )
        except PackageApprovalError as error:
            raise PublisherAttestationError("publisher_attestation_approval_not_found") from error
        claim = await self._claim_source.get_by_id(claim_id=report.publisher_claim_id)
        policy = await self._policy_source.get_by_id(policy_id=report.attestation_policy_id)
        now = self._clock()
        if claim is None or policy is None or approval.decision is None:
            raise PublisherAttestationError("publisher_attestation_evidence_not_found")
        self._verify_claim(claim)
        self._verify_policy(policy)
        if (
            report.source_approval_request_digest != approval.request.canonical_digest
            or report.source_approval_decision_digest != approval.decision.canonical_digest
            or report.package_digest != claim.package_digest
            or report.publisher_claim_digest != claim.canonical_digest
            or report.attestation_policy_digest != policy.canonical_digest
            or not policy.issued_at <= now < policy.expires_at
            or not claim.issued_at <= now < claim.expires_at
            or not report.publisher_attested
            or not report.eligible_for_package_signing_governance
            or report.promotion_blocked
            or report.outcome is not PublisherAttestationOutcome.VERIFIED
        ):
            raise PublisherAttestationError("publisher_attestation_not_eligible_for_signing")
        return report, upstream | {
            report.verified_by,
            claim.issued_by,
            claim.publisher_id,
            policy.signed_by,
        }

    async def close(self) -> None:
        await self._repository.close()

    @classmethod
    def _verify_claim(cls, claim: ConnectorPublisherClaimSnapshot) -> None:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != claim.canonical_digest:
            raise PublisherAttestationError("publisher_attestation_claim_integrity_failed")

    @classmethod
    def _verify_policy(cls, policy: ConnectorPublisherAttestationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise PublisherAttestationError("publisher_attestation_policy_integrity_failed")

    @classmethod
    def _verify_report(cls, report: ConnectorPublisherAttestationReport) -> None:
        if cls._digest(cls._report_payload(report)) != report.canonical_digest:
            raise PublisherAttestationError("publisher_attestation_report_integrity_failed")

    @classmethod
    def _report_payload(cls, report: ConnectorPublisherAttestationReport) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(report))
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
            return {str(k): cls._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(v) for v in value]
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
            raise PublisherAttestationError("publisher_attestation_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PublisherAttestationError("publisher_attestation_report_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        report: ConnectorPublisherAttestationReport,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.publisher-attestation",
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
                resource_type="resource.connector.publisher-attestation",
                scope_reference=report.report_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=report.idempotency_key
                if permission_id == ATTESTATION_CREATE_PERMISSION
                else None,
                target_metadata=(
                    ("publisher_id", report.publisher_id),
                    ("outcome", report.outcome.value),
                ),
            )
        )


def build_development_publisher_attestation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ConnectorPublisherAttestationPolicySnapshot:
    policy = ConnectorPublisherAttestationPolicySnapshot(
        policy_id="connector-publisher-attestation-policy.development",
        schema_version="atlas.connector-publisher-attestation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_approval_schema="atlas.connector-package-approval-request.v1",
        required_claim_schema="atlas.connector-publisher-claim.v1",
        maximum_approval_age_hours=168,
        maximum_claim_age_hours=8760,
        minimum_support_validity_days=30,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        trusted_issuer_ids=("subject.publisher-claim-authority",),
        signed_by="subject.publisher-attestation-policy-owner",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=PublisherAttestationService._digest(
            PublisherAttestationService._normalize(payload)
        ),
    )
