from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.itsm.application.ports import (
    ItsmIntegrationProfileRepository,
    ItsmSandboxConformanceAdapter,
    ItsmSandboxOnboardingEvidenceSource,
)
from atlas.modules.itsm.domain.models import (
    ItsmAllowedOperation,
    ItsmCheckState,
    ItsmFieldMapping,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessAssessment,
    ItsmReadinessCheck,
    ItsmReadinessState,
    ItsmSandboxConformanceAssessment,
    ItsmSandboxConformanceState,
    ItsmSandboxDiagnostic,
    ItsmSandboxOnboardingEvidence,
    ItsmSandboxOnboardingReadiness,
    ItsmSandboxOnboardingRequirement,
    ItsmSandboxOnboardingRequirementState,
    ItsmSandboxOnboardingState,
)

ITSM_PROFILE_SCHEMA = "atlas.itsm-integration-profile.v1"
ITSM_SANDBOX_CONFORMANCE_SCHEMA = "atlas.itsm-sandbox-conformance-assessment.v1"
ITSM_SANDBOX_DIAGNOSTIC_CONTRACT = "contract.itsm-sandbox-conformance.v1"
ITSM_READ = "itsm.integrations.read"
ITSM_CREATE = "itsm.integrations.create"
ITSM_RETIRE = "itsm.integrations.retire"
ITSM_SANDBOX_CONFORMANCE_READ = "itsm.integrations.sandbox-conformance.read"
ITSM_SANDBOX_CONFORMANCE_CREATE = "itsm.integrations.sandbox-conformance.create"
ITSM_SANDBOX_ONBOARDING_READ = "itsm.integrations.sandbox-onboarding.read"
ITSM_SANDBOX_ONBOARDING_POLICY = "policy.itsm-sandbox-onboarding.v1"


class ItsmIntegrationError(RuntimeError):
    pass


class ItsmIntegrationService:
    def __init__(
        self,
        *,
        repository: ItsmIntegrationProfileRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str = "site.local",
        sandbox_conformance_adapter: ItsmSandboxConformanceAdapter | None = None,
        sandbox_onboarding_evidence_source: ItsmSandboxOnboardingEvidenceSource | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._sandbox_conformance_adapter = sandbox_conformance_adapter
        self._sandbox_onboarding_evidence_source = sandbox_onboarding_evidence_source
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    @property
    def repository(self) -> ItsmIntegrationProfileRepository:
        return self._repository

    async def list_profiles(
        self,
        *,
        actor: AuthenticatedSubject,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
        correlation_id: str,
    ) -> tuple[ItsmIntegrationProfile, ...]:
        records = await self._repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            lifecycle=lifecycle,
            limit=limit,
        )
        for record in records:
            self._validate_record(record)
            self._require_scope(actor, record)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_READ,
            result_code="itsm_integration_inventory_read",
            scope_reference="resource.itsm.integrations",
            idempotency_key=None,
        )
        return records

    async def get(
        self, *, actor: AuthenticatedSubject, profile_id: str, correlation_id: str
    ) -> ItsmIntegrationProfile:
        record = await self._repository.get(profile_id=profile_id)
        if record is None:
            raise ItsmIntegrationError("itsm_integration_not_found")
        self._validate_record(record)
        self._require_scope(actor, record)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_READ,
            result_code="itsm_integration_read",
            scope_reference=record.profile_id,
            idempotency_key=None,
        )
        return record

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_key: str,
        display_name: str,
        provider_family: ItsmProviderFamily,
        instance_reference: str,
        owner_id: str,
        purpose: str,
        endpoint_origin: str,
        trust_boundary_reference: str,
        secret_reference_id: str,
        classification_ceiling: DataClassification,
        allowed_operations: tuple[ItsmAllowedOperation, ...],
        mapping_version: int,
        field_mappings: tuple[ItsmFieldMapping, ...],
        sandbox_validation_reference: str | None,
        sandbox_validation_digest: str | None,
        audit_profile_id: str,
        acknowledged_configuration_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmIntegrationProfile:
        self._require_human(actor)
        if not acknowledged_configuration_only:
            raise ItsmIntegrationError("itsm_integration_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise ItsmIntegrationError("itsm_integration_request_invalid")
        profile_key = profile_key.strip().lower()
        display_name = display_name.strip()
        endpoint_origin = endpoint_origin.strip().rstrip("/")
        purpose = purpose.strip()
        request_payload = {
            "profile_key": profile_key,
            "display_name": display_name,
            "provider_family": provider_family,
            "instance_reference": instance_reference,
            "owner_id": owner_id,
            "purpose": purpose,
            "endpoint_origin": endpoint_origin,
            "trust_boundary_reference": trust_boundary_reference,
            "secret_reference_id": secret_reference_id,
            "classification_ceiling": classification_ceiling,
            "allowed_operations": allowed_operations,
            "mapping_version": mapping_version,
            "field_mappings": field_mappings,
            "sandbox_validation_reference": sandbox_validation_reference,
            "sandbox_validation_digest": sandbox_validation_digest,
            "audit_profile_id": audit_profile_id,
        }
        fingerprint = self._digest(request_payload)
        replay = await self._repository.get_by_create_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.create_request_fingerprint != fingerprint:
                raise ItsmIntegrationError("itsm_integration_idempotency_conflict")
            self._validate_record(replay)
            self._require_scope(actor, replay)
            return replace(replay, reused=True)

        now = self._clock()
        readiness = self._assess(
            owner_id=owner_id,
            endpoint_origin=endpoint_origin,
            trust_boundary_reference=trust_boundary_reference,
            secret_reference_id=secret_reference_id,
            field_mappings=field_mappings,
            sandbox_validation_reference=sandbox_validation_reference,
            sandbox_validation_digest=sandbox_validation_digest,
            audit_profile_id=audit_profile_id,
            assessed_at=now,
        )
        seed = self._digest(
            [actor.organization_id, self._environment_id, self._site_id, profile_key]
        )
        record = ItsmIntegrationProfile(
            profile_id=f"itsm-integration.{seed[:24]}",
            schema_version=ITSM_PROFILE_SCHEMA,
            version=1,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            profile_key=profile_key,
            display_name=display_name,
            provider_family=provider_family,
            instance_reference=instance_reference,
            owner_id=owner_id,
            purpose=purpose,
            endpoint_origin=endpoint_origin,
            trust_boundary_reference=trust_boundary_reference,
            secret_reference_id=secret_reference_id,
            classification_ceiling=classification_ceiling,
            allowed_operations=allowed_operations,
            mapping_version=mapping_version,
            field_mappings=field_mappings,
            sandbox_validation_reference=sandbox_validation_reference,
            sandbox_validation_digest=sandbox_validation_digest,
            audit_profile_id=audit_profile_id,
            lifecycle=ItsmProfileLifecycle.ACTIVE,
            readiness=readiness,
            created_by=actor.subject_id,
            created_at=now,
            updated_by=actor.subject_id,
            updated_at=now,
            canonical_digest="0" * 64,
            create_request_fingerprint=fingerprint,
            create_idempotency_key=idempotency_key,
        )
        record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
        async with self._lock:
            prior = await self._repository.get_by_scope_key(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                profile_key=profile_key,
            )
            if prior is not None:
                raise ItsmIntegrationError("itsm_integration_key_conflict")
            await self._audit(
                actor,
                correlation_id=correlation_id,
                permission_id=ITSM_CREATE,
                result_code="itsm_integration_create_requested",
                scope_reference=record.profile_id,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.add(record):
                raise ItsmIntegrationError("itsm_integration_concurrency_conflict")
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_CREATE,
            result_code="itsm_integration_created",
            scope_reference=record.profile_id,
            idempotency_key=idempotency_key,
        )
        return record

    async def retire(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        expected_version: int,
        reason: str,
        acknowledged_history_preserved_and_dispatch_absent: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmIntegrationProfile:
        self._require_human(actor)
        if not acknowledged_history_preserved_and_dispatch_absent:
            raise ItsmIntegrationError("itsm_integration_retirement_acknowledgement_required")
        reason = reason.strip()
        if not 20 <= len(reason) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ItsmIntegrationError("itsm_integration_retirement_request_invalid")
        fingerprint = self._digest(
            {"profile_id": profile_id, "expected_version": expected_version, "reason": reason}
        )
        replay = await self._repository.get_by_retirement_key(
            retired_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.retirement_request_fingerprint != fingerprint:
                raise ItsmIntegrationError("itsm_integration_idempotency_conflict")
            self._validate_record(replay)
            self._require_scope(actor, replay)
            return replace(replay, reused=True)
        async with self._lock:
            current = await self._repository.get(profile_id=profile_id)
            if current is None:
                raise ItsmIntegrationError("itsm_integration_not_found")
            self._validate_record(current)
            self._require_scope(actor, current)
            if current.lifecycle is ItsmProfileLifecycle.RETIRED:
                raise ItsmIntegrationError("itsm_integration_already_retired")
            if current.version != expected_version:
                raise ItsmIntegrationError("itsm_integration_version_conflict")
            now = self._clock()
            retired = replace(
                current,
                version=current.version + 1,
                lifecycle=ItsmProfileLifecycle.RETIRED,
                updated_by=actor.subject_id,
                updated_at=now,
                retired_by=actor.subject_id,
                retired_at=now,
                retirement_reason=reason,
                retirement_request_fingerprint=fingerprint,
                retirement_idempotency_key=idempotency_key,
                canonical_digest="0" * 64,
            )
            retired = replace(retired, canonical_digest=self._digest(self._record_payload(retired)))
            await self._audit(
                actor,
                correlation_id=correlation_id,
                permission_id=ITSM_RETIRE,
                result_code="itsm_integration_retirement_requested",
                scope_reference=profile_id,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.update(retired, expected_version=expected_version):
                raise ItsmIntegrationError("itsm_integration_version_conflict")
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_RETIRE,
            result_code="itsm_integration_retired",
            scope_reference=profile_id,
            idempotency_key=idempotency_key,
        )
        return retired

    async def assess_sandbox_conformance(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        expected_profile_version: int,
        acknowledged_diagnostic_only_and_no_dispatch: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmSandboxConformanceAssessment:
        self._require_human(actor)
        if not acknowledged_diagnostic_only_and_no_dispatch:
            raise ItsmIntegrationError("itsm_sandbox_conformance_acknowledgement_required")
        if expected_profile_version < 1 or not 8 <= len(idempotency_key) <= 128:
            raise ItsmIntegrationError("itsm_sandbox_conformance_request_invalid")
        profile = await self._repository.get(profile_id=profile_id)
        if profile is None:
            raise ItsmIntegrationError("itsm_integration_not_found")
        self._validate_record(profile)
        self._require_scope(actor, profile)
        if profile.lifecycle is not ItsmProfileLifecycle.ACTIVE:
            raise ItsmIntegrationError("itsm_sandbox_conformance_profile_inactive")
        if profile.version != expected_profile_version:
            raise ItsmIntegrationError("itsm_sandbox_conformance_profile_version_conflict")
        fingerprint = self._digest(
            {
                "schema_version": ITSM_SANDBOX_CONFORMANCE_SCHEMA,
                "organization_id": actor.organization_id,
                "environment_id": self._environment_id,
                "site_id": self._site_id,
                "profile_id": profile.profile_id,
                "profile_version": profile.version,
                "profile_digest": profile.canonical_digest,
                "assessed_by": actor.subject_id,
                "diagnostic_contract_version": ITSM_SANDBOX_DIAGNOSTIC_CONTRACT,
                "acknowledged_no_authority": True,
            }
        )
        prior = await self._repository.get_sandbox_conformance_by_key(
            assessed_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if prior is not None:
            self._validate_sandbox_assessment(prior, profile=profile)
            if prior.request_fingerprint != fingerprint:
                raise ItsmIntegrationError("itsm_sandbox_conformance_idempotency_conflict")
            reused = replace(prior, reused=True)
            await self._audit(
                actor,
                correlation_id=correlation_id,
                permission_id=ITSM_SANDBOX_CONFORMANCE_CREATE,
                result_code="itsm_sandbox_conformance_reused",
                scope_reference=profile.profile_id,
                idempotency_key=idempotency_key,
            )
            return reused

        async with self._lock:
            raced = await self._repository.get_sandbox_conformance_by_key(
                assessed_by=actor.subject_id, idempotency_key=idempotency_key
            )
            if raced is not None:
                self._validate_sandbox_assessment(raced, profile=profile)
                if raced.request_fingerprint != fingerprint:
                    raise ItsmIntegrationError("itsm_sandbox_conformance_idempotency_conflict")
                return replace(raced, reused=True)
            now = self._clock()
            valid_until = now + timedelta(minutes=10)
            challenge_digest = self._digest(
                {
                    "schema_version": "atlas.itsm-sandbox-conformance-challenge.v1",
                    "assessment_seed": f"assessment-seed.{uuid4().hex}",
                    "organization_id": profile.organization_id,
                    "environment_id": profile.environment_id,
                    "site_id": profile.site_id,
                    "profile_id": profile.profile_id,
                    "profile_version": profile.version,
                    "profile_digest": profile.canonical_digest,
                    "mapping_version": profile.mapping_version,
                    "diagnostic_contract_version": ITSM_SANDBOX_DIAGNOSTIC_CONTRACT,
                }
            )
            diagnostic = await self._run_sandbox_diagnostic(
                profile=profile, challenge_digest=challenge_digest
            )
            self._validate_sandbox_diagnostic(
                diagnostic, profile=profile, challenge_digest=challenge_digest
            )
            payload = {
                "schema_version": ITSM_SANDBOX_CONFORMANCE_SCHEMA,
                "version": 1,
                "organization_id": profile.organization_id,
                "environment_id": profile.environment_id,
                "site_id": profile.site_id,
                "profile_id": profile.profile_id,
                "profile_version": profile.version,
                "profile_digest": profile.canonical_digest,
                "mapping_version": profile.mapping_version,
                "assessed_by": actor.subject_id,
                "adapter_id": diagnostic.adapter_id,
                "adapter_version": diagnostic.adapter_version,
                "adapter_production_eligible": diagnostic.production_eligible,
                "diagnostic_contract_version": ITSM_SANDBOX_DIAGNOSTIC_CONTRACT,
                "challenge_digest": challenge_digest,
                "observed_at": now,
                "valid_until": valid_until,
                "state": diagnostic.state,
                "reason_codes": (diagnostic.reason_code,),
                "request_fingerprint": fingerprint,
                "diagnostic_only": True,
                "sandbox_conformant": (diagnostic.state is ItsmSandboxConformanceState.CONFORMANT),
                "production_ready": False,
                "dispatch_authorized": False,
                "external_record_mutation_authorized": False,
                "workflow_approved": False,
                "execution_authorized": False,
                "infrastructure_mutation_performed": False,
            }
            digest = self._digest(payload)
            assessment = ItsmSandboxConformanceAssessment(
                assessment_id=f"itsm-sandbox-conformance.{digest[:24]}",
                idempotency_key=idempotency_key,
                canonical_digest=digest,
                **cast(dict[str, Any], payload),
            )
            await self._audit(
                actor,
                correlation_id=correlation_id,
                permission_id=ITSM_SANDBOX_CONFORMANCE_CREATE,
                result_code="itsm_sandbox_conformance_requested",
                scope_reference=profile.profile_id,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.add_sandbox_conformance(assessment):
                raced = await self._repository.get_sandbox_conformance_by_key(
                    assessed_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise ItsmIntegrationError("itsm_sandbox_conformance_idempotency_conflict")
                self._validate_sandbox_assessment(raced, profile=profile)
                assessment = replace(raced, reused=True)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_SANDBOX_CONFORMANCE_CREATE,
            result_code=f"itsm_sandbox_conformance_{assessment.state.value}",
            scope_reference=profile.profile_id,
            idempotency_key=idempotency_key,
        )
        return assessment

    async def latest_sandbox_conformance(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        correlation_id: str,
    ) -> ItsmSandboxConformanceAssessment:
        profile = await self._repository.get(profile_id=profile_id)
        if profile is None:
            raise ItsmIntegrationError("itsm_integration_not_found")
        self._validate_record(profile)
        self._require_scope(actor, profile)
        assessment = await self._repository.get_latest_sandbox_conformance(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            profile_id=profile_id,
        )
        if assessment is None:
            raise ItsmIntegrationError("itsm_sandbox_conformance_not_found")
        self._validate_sandbox_assessment(assessment, profile=profile)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_SANDBOX_CONFORMANCE_READ,
            result_code="itsm_sandbox_conformance_read",
            scope_reference=profile.profile_id,
            idempotency_key=None,
        )
        return assessment

    async def sandbox_onboarding_readiness(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        correlation_id: str,
    ) -> ItsmSandboxOnboardingReadiness:
        profile = await self._repository.get(profile_id=profile_id)
        if profile is None:
            raise ItsmIntegrationError("itsm_integration_not_found")
        self._validate_record(profile)
        self._require_scope(actor, profile)
        now = self._clock()
        assessment = await self._repository.get_latest_sandbox_conformance(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            profile_id=profile_id,
        )
        assessment_integrity_valid = True
        if assessment is not None:
            try:
                self._validate_sandbox_assessment(assessment, profile=profile)
            except ItsmIntegrationError:
                assessment_integrity_valid = False

        evidence = None
        evidence_source_failed = False
        if self._sandbox_onboarding_evidence_source is not None:
            try:
                evidence = await self._sandbox_onboarding_evidence_source.get(
                    profile=profile,
                    assessment=assessment if assessment_integrity_valid else None,
                )
            except Exception:
                evidence_source_failed = True
        if evidence_source_failed:
            evidence_valid = False
            evidence_reason = "itsm.sandbox-onboarding.evidence_source_unavailable"
        else:
            evidence_valid, evidence_reason = self._validate_onboarding_evidence(
                evidence,
                profile=profile,
                assessment=assessment if assessment_integrity_valid else None,
                assessed_at=now,
            )
        dossier = self._build_onboarding_readiness(
            profile=profile,
            assessment=assessment if assessment_integrity_valid else None,
            assessment_integrity_valid=assessment_integrity_valid,
            evidence=evidence if evidence_valid else None,
            evidence_reason=evidence_reason,
            assessed_at=now,
        )
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_SANDBOX_ONBOARDING_READ,
            result_code=f"itsm_sandbox_onboarding_{dossier.state.value}",
            scope_reference=profile.profile_id,
            idempotency_key=None,
        )
        return dossier

    async def close(self) -> None:
        await self._repository.close()

    async def _run_sandbox_diagnostic(
        self, *, profile: ItsmIntegrationProfile, challenge_digest: str
    ) -> ItsmSandboxDiagnostic:
        if not self._sandbox_prerequisites_satisfied(profile):
            return self._bounded_diagnostic(
                profile=profile,
                challenge_digest=challenge_digest,
                adapter_id="adapter.itsm.application",
                state=ItsmSandboxConformanceState.PROFILE_BLOCKED,
                reason="profile_blocked",
            )
        if self._sandbox_conformance_adapter is None:
            return self._bounded_diagnostic(
                profile=profile,
                challenge_digest=challenge_digest,
                adapter_id="adapter.itsm.unconfigured",
                state=ItsmSandboxConformanceState.UNAVAILABLE,
                reason="adapter_unavailable",
            )
        try:
            return await self._sandbox_conformance_adapter.assess(
                profile=profile,
                challenge_digest=challenge_digest,
                diagnostic_contract_version=ITSM_SANDBOX_DIAGNOSTIC_CONTRACT,
            )
        except Exception:
            return self._bounded_diagnostic(
                profile=profile,
                challenge_digest=challenge_digest,
                adapter_id="adapter.itsm.failure-contained",
                state=ItsmSandboxConformanceState.ROUND_TRIP_FAILED,
                reason="round_trip_failed",
            )

    @staticmethod
    def _bounded_diagnostic(
        *,
        profile: ItsmIntegrationProfile,
        challenge_digest: str,
        adapter_id: str,
        state: ItsmSandboxConformanceState,
        reason: str,
    ) -> ItsmSandboxDiagnostic:
        return ItsmSandboxDiagnostic(
            adapter_id=adapter_id,
            adapter_version="version.1",
            organization_id=profile.organization_id,
            environment_id=profile.environment_id,
            site_id=profile.site_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            challenge_digest=challenge_digest,
            state=state,
            reason_code=f"itsm.sandbox-conformance.{reason}",
        )

    @staticmethod
    def _sandbox_prerequisites_satisfied(profile: ItsmIntegrationProfile) -> bool:
        return all(
            check.state is ItsmCheckState.SATISFIED
            for check in profile.readiness.checks
            if check.check_id != "itsm.readiness.sandbox-validation"
        )

    @staticmethod
    def _validate_sandbox_diagnostic(
        diagnostic: ItsmSandboxDiagnostic,
        *,
        profile: ItsmIntegrationProfile,
        challenge_digest: str,
    ) -> None:
        if (
            diagnostic.organization_id != profile.organization_id
            or diagnostic.environment_id != profile.environment_id
            or diagnostic.site_id != profile.site_id
            or diagnostic.profile_id != profile.profile_id
            or diagnostic.profile_version != profile.version
            or diagnostic.challenge_digest != challenge_digest
        ):
            raise ItsmIntegrationError("itsm_sandbox_conformance_adapter_binding_invalid")

    @classmethod
    def _validate_sandbox_assessment(
        cls,
        assessment: ItsmSandboxConformanceAssessment,
        *,
        profile: ItsmIntegrationProfile,
    ) -> None:
        if (
            assessment.organization_id != profile.organization_id
            or assessment.environment_id != profile.environment_id
            or assessment.site_id != profile.site_id
            or assessment.profile_id != profile.profile_id
            or assessment.profile_version != profile.version
            or assessment.profile_digest != profile.canonical_digest
            or assessment.mapping_version != profile.mapping_version
            or cls._digest(cls._sandbox_assessment_payload(assessment))
            != assessment.canonical_digest
        ):
            raise ItsmIntegrationError("itsm_sandbox_conformance_integrity_failed")

    @classmethod
    def _sandbox_assessment_payload(
        cls, assessment: ItsmSandboxConformanceAssessment
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(assessment))
        for field in ("assessment_id", "idempotency_key", "canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _validate_onboarding_evidence(
        cls,
        evidence: ItsmSandboxOnboardingEvidence | None,
        *,
        profile: ItsmIntegrationProfile,
        assessment: ItsmSandboxConformanceAssessment | None,
        assessed_at: datetime,
    ) -> tuple[bool, str]:
        if evidence is None:
            return False, "itsm.sandbox-onboarding.evidence_missing"
        if cls._digest(cls._onboarding_evidence_payload(evidence)) != evidence.canonical_digest:
            return False, "itsm.sandbox-onboarding.evidence_integrity_failed"
        if (
            assessment is None
            or evidence.organization_id != profile.organization_id
            or evidence.environment_id != profile.environment_id
            or evidence.site_id != profile.site_id
            or evidence.profile_id != profile.profile_id
            or evidence.profile_version != profile.version
            or evidence.profile_digest != profile.canonical_digest
            or evidence.mapping_version != profile.mapping_version
            or evidence.adapter_id != assessment.adapter_id
            or evidence.adapter_version != assessment.adapter_version
        ):
            return False, "itsm.sandbox-onboarding.evidence_binding_invalid"
        if evidence.valid_until <= assessed_at:
            return False, "itsm.sandbox-onboarding.evidence_expired"
        return True, "itsm.sandbox-onboarding.satisfied"

    @classmethod
    def _onboarding_evidence_payload(
        cls, evidence: ItsmSandboxOnboardingEvidence
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(evidence))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _build_onboarding_readiness(
        cls,
        *,
        profile: ItsmIntegrationProfile,
        assessment: ItsmSandboxConformanceAssessment | None,
        assessment_integrity_valid: bool,
        evidence: ItsmSandboxOnboardingEvidence | None,
        evidence_reason: str,
        assessed_at: datetime,
    ) -> ItsmSandboxOnboardingReadiness:
        profile_current = profile.lifecycle is ItsmProfileLifecycle.ACTIVE
        if assessment is None:
            conformance_reason = (
                "itsm.sandbox-onboarding.conformance_integrity_failed"
                if not assessment_integrity_valid
                else "itsm.sandbox-onboarding.conformance_missing"
            )
            conformance_current = False
        elif assessment.state is not ItsmSandboxConformanceState.CONFORMANT:
            conformance_reason = "itsm.sandbox-onboarding.conformance_not_conformant"
            conformance_current = False
        elif assessment.valid_until <= assessed_at:
            conformance_reason = "itsm.sandbox-onboarding.conformance_expired"
            conformance_current = False
        else:
            conformance_reason = "itsm.sandbox-onboarding.satisfied"
            conformance_current = True

        def evidence_condition(value: bool, missing_reason: str) -> tuple[bool, str]:
            if evidence is None:
                return False, evidence_reason
            return (True, "itsm.sandbox-onboarding.satisfied") if value else (False, missing_reason)

        adapter_eligible = bool(
            evidence
            and assessment
            and evidence.adapter_sandbox_approved
            and evidence.production_eligible
            and assessment.adapter_production_eligible
        )
        conditions = (
            (
                "itsm.sandbox-onboarding.profile-current",
                profile_current,
                "itsm.sandbox-onboarding.profile_not_active",
            ),
            (
                "itsm.sandbox-onboarding.conformance-current",
                conformance_current,
                conformance_reason,
            ),
            (
                "itsm.sandbox-onboarding.adapter-registered",
                *evidence_condition(
                    bool(evidence and evidence.adapter_registered),
                    "itsm.sandbox-onboarding.adapter_not_registered",
                ),
            ),
            (
                "itsm.sandbox-onboarding.adapter-sandbox-approved",
                *evidence_condition(
                    adapter_eligible,
                    "itsm.sandbox-onboarding.adapter_not_onboarding_eligible",
                ),
            ),
            (
                "itsm.sandbox-onboarding.workload-identity",
                *evidence_condition(
                    bool(evidence and evidence.workload_identity_configured),
                    "itsm.sandbox-onboarding.workload_identity_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.credential-ownership",
                *evidence_condition(
                    bool(evidence and evidence.credential_reference_owned),
                    "itsm.sandbox-onboarding.credential_ownership_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.network-trust",
                *evidence_condition(
                    bool(evidence and evidence.network_trust_approved),
                    "itsm.sandbox-onboarding.network_trust_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.mapping-change-control",
                *evidence_condition(
                    bool(evidence and evidence.mapping_change_control_configured),
                    "itsm.sandbox-onboarding.mapping_change_control_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.rate-backpressure",
                *evidence_condition(
                    bool(evidence and evidence.rate_limit_and_backpressure_configured),
                    "itsm.sandbox-onboarding.rate_backpressure_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.audit-routing",
                *evidence_condition(
                    bool(evidence and evidence.audit_routing_configured),
                    "itsm.sandbox-onboarding.audit_routing_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.availability-recovery",
                *evidence_condition(
                    bool(evidence and evidence.availability_and_recovery_configured),
                    "itsm.sandbox-onboarding.availability_recovery_missing",
                ),
            ),
            (
                "itsm.sandbox-onboarding.owner-approvals",
                *evidence_condition(
                    bool(
                        evidence
                        and evidence.security_approval_reference
                        and evidence.deployment_approval_reference
                    ),
                    "itsm.sandbox-onboarding.owner_approvals_missing",
                ),
            ),
        )
        requirements = tuple(
            ItsmSandboxOnboardingRequirement(
                requirement_id=requirement_id,
                state=(
                    ItsmSandboxOnboardingRequirementState.SATISFIED
                    if satisfied
                    else ItsmSandboxOnboardingRequirementState.BLOCKED
                ),
                reason_code=reason,
            )
            for requirement_id, satisfied, reason in conditions
        )
        ready = all(
            item.state is ItsmSandboxOnboardingRequirementState.SATISFIED for item in requirements
        )
        payload: dict[str, object] = {
            "schema_version": "atlas.itsm-sandbox-onboarding-readiness.v1",
            "version": 1,
            "organization_id": profile.organization_id,
            "environment_id": profile.environment_id,
            "site_id": profile.site_id,
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "profile_digest": profile.canonical_digest,
            "mapping_version": profile.mapping_version,
            "conformance_assessment_id": assessment.assessment_id if assessment else None,
            "conformance_assessment_digest": assessment.canonical_digest if assessment else None,
            "adapter_id": assessment.adapter_id if assessment else None,
            "adapter_version": assessment.adapter_version if assessment else None,
            "policy_version": ITSM_SANDBOX_ONBOARDING_POLICY,
            "assessed_at": assessed_at,
            "evidence_observed_at": evidence.observed_at if evidence else None,
            "evidence_valid_until": evidence.valid_until if evidence else None,
            "state": ItsmSandboxOnboardingState.READY
            if ready
            else ItsmSandboxOnboardingState.BLOCKED,
            "requirements": requirements,
            "sandbox_onboarding_ready": ready,
            "production_ready": False,
            "dispatch_authorized": False,
            "external_record_mutation_authorized": False,
            "workflow_approved": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        return ItsmSandboxOnboardingReadiness(
            **cast(dict[str, Any], payload), canonical_digest=cls._digest(payload)
        )

    def _require_scope(self, actor: AuthenticatedSubject, record: ItsmIntegrationProfile) -> None:
        if (
            record.organization_id != actor.organization_id
            or record.environment_id != self._environment_id
            or record.site_id != self._site_id
        ):
            raise ItsmIntegrationError("itsm_integration_not_found")

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ItsmIntegrationError("itsm_integration_human_required")

    @classmethod
    def _validate_record(cls, record: ItsmIntegrationProfile) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ItsmIntegrationError("itsm_integration_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ItsmIntegrationProfile) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in (
            "canonical_digest",
            "create_request_fingerprint",
            "create_idempotency_key",
            "retirement_request_fingerprint",
            "retirement_idempotency_key",
            "reused",
        ):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value) and not isinstance(value, type):
            return cls._normalize(asdict(value))
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @classmethod
    def _digest(cls, payload: object) -> str:
        return sha256(
            json.dumps(
                cls._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @classmethod
    def _assess(
        cls,
        *,
        owner_id: str,
        endpoint_origin: str,
        trust_boundary_reference: str,
        secret_reference_id: str,
        field_mappings: tuple[ItsmFieldMapping, ...],
        sandbox_validation_reference: str | None,
        sandbox_validation_digest: str | None,
        audit_profile_id: str,
        assessed_at: datetime,
    ) -> ItsmReadinessAssessment:
        conditions = (
            ("itsm.readiness.ownership", bool(owner_id), "itsm.readiness.owner_missing"),
            (
                "itsm.readiness.network-trust",
                endpoint_origin.startswith("https://") and bool(trust_boundary_reference),
                "itsm.readiness.network_trust_missing",
            ),
            (
                "itsm.readiness.credential-reference",
                secret_reference_id.startswith("secret."),
                "itsm.readiness.credential_reference_missing",
            ),
            (
                "itsm.readiness.mapping",
                {item.source_field for item in field_mappings}
                >= {"work_notes", "u_atlas_report_reference", "u_atlas_review_state"},
                "itsm.readiness.mapping_incomplete",
            ),
            (
                "itsm.readiness.sandbox-validation",
                sandbox_validation_reference is not None and sandbox_validation_digest is not None,
                "itsm.readiness.sandbox_validation_missing",
            ),
            ("itsm.readiness.audit", bool(audit_profile_id), "itsm.readiness.audit_missing"),
        )
        checks = tuple(
            ItsmReadinessCheck(
                check_id=check_id,
                state=ItsmCheckState.SATISFIED if satisfied else ItsmCheckState.BLOCKED,
                reason_code="itsm.readiness.satisfied" if satisfied else reason,
            )
            for check_id, satisfied, reason in conditions
        )
        state = (
            ItsmReadinessState.READY_FOR_SANDBOX
            if all(item.state is ItsmCheckState.SATISFIED for item in checks)
            else ItsmReadinessState.BLOCKED
        )
        payload = {
            "state": state,
            "checks": checks,
            "assessed_at": assessed_at,
            "authority": False,
        }
        return ItsmReadinessAssessment(
            state=state,
            checks=checks,
            assessed_at=assessed_at,
            canonical_digest=cls._digest(payload),
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        *,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.itsm.integration-profile",
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
                resource_type="resource.itsm.integration",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
            )
        )
