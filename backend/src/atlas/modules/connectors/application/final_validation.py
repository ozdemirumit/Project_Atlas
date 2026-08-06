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
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.authority_behavior_validation import (
    PackageAuthorityBehaviorValidationService,
)
from atlas.modules.connectors.application.content_policy_scan import PackageContentPolicyScanService
from atlas.modules.connectors.application.contract_validation import (
    PackageContractValidationService,
)
from atlas.modules.connectors.application.final_validation_ports import (
    FinalAcquisitionSource,
    FinalArchiveSource,
    FinalAuthorityBehaviorSource,
    FinalContentPolicySource,
    FinalContractSource,
    FinalHandoffSource,
    FinalInventorySource,
    FinalLabSource,
    FinalLicenseSource,
    FinalMalwareSource,
    FinalPackageValidationSource,
    FinalRunnerSource,
    FinalSchemaSemanticsSource,
    FinalStaticDependencySource,
    FinalValidationPolicySource,
    FinalVulnerabilitySource,
    PackageFinalValidationError,
    PackageFinalValidationRepository,
)
from atlas.modules.connectors.application.lab_self_test import PackageLabSelfTestService
from atlas.modules.connectors.application.license_analysis import PackageLicenseAnalysisService
from atlas.modules.connectors.application.malware_analysis import PackageMalwareAnalysisService
from atlas.modules.connectors.application.runner_validation import PackageRunnerValidationService
from atlas.modules.connectors.application.schema_semantics_validation import (
    PackageSchemaSemanticsValidationService,
)
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.application.vulnerability_analysis import (
    PackageVulnerabilityAnalysisService,
)
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)
from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan
from atlas.modules.connectors.domain.contract_validation import ConnectorPackageContractValidation
from atlas.modules.connectors.domain.final_validation import (
    FINAL_VALIDATION_STAGE_CODES,
    ConnectorPackageFinalValidation,
    FinalRiskClassification,
    FinalRiskSummary,
    FinalStageEvidence,
    FinalValidationCheck,
    FinalValidationCheckState,
    FinalValidationOutcome,
    FinalValidationPolicySnapshot,
    FinalValidationSeverity,
)
from atlas.modules.connectors.domain.lab_self_test import ConnectorPackageLabSelfTest
from atlas.modules.connectors.domain.license_analysis import ConnectorPackageLicenseAnalysis
from atlas.modules.connectors.domain.malware_analysis import ConnectorPackageMalwareAnalysis
from atlas.modules.connectors.domain.runner_validation import ConnectorPackageRunnerValidation
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
)
from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)
from atlas.modules.connectors.domain.validation_intake import ConnectorPackageValidation
from atlas.modules.connectors.domain.vulnerability_analysis import (
    ConnectorPackageVulnerabilityAnalysis,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff

FINAL_VALIDATION_CREATE_PERMISSION = "connectors.package-final-validations.create"
FINAL_VALIDATION_READ_PERMISSION = "connectors.package-final-validations.read"
FINAL_VALIDATION_SCHEMA = "atlas.connector-package-final-validation.v1"
FINAL_VALIDATION_LIMITATIONS = (
    "Eligibility means only that the exact evidence may enter independent human approval.",
    "Final validation does not accept risk, attest a publisher, sign, register, install, or "
    "enable.",
    "No production target, secret, model, package execution, or infrastructure operation occurs.",
)


@dataclass(frozen=True, slots=True)
class _FinalSources:
    handoff: McpBuilderCandidateHandoff
    acquisition: ConnectorPackageAcquisition
    validation: ConnectorPackageValidation
    inventory: ConnectorPackageSupplyChainInventory
    content_policy: ConnectorPackageContentPolicyScan
    schema_semantics: ConnectorPackageSchemaSemanticsValidation
    authority_behavior: ConnectorPackageAuthorityBehaviorValidation
    static_dependency: ConnectorPackageStaticDependencyAnalysis
    vulnerability: ConnectorPackageVulnerabilityAnalysis
    malware: ConnectorPackageMalwareAnalysis
    license: ConnectorPackageLicenseAnalysis
    contract: ConnectorPackageContractValidation
    runner: ConnectorPackageRunnerValidation
    lab: ConnectorPackageLabSelfTest


class PackageFinalValidationService:
    def __init__(
        self,
        *,
        repository: PackageFinalValidationRepository,
        handoff_source: FinalHandoffSource,
        acquisition_source: FinalAcquisitionSource,
        archive_source: FinalArchiveSource,
        validation_source: FinalPackageValidationSource,
        inventory_source: FinalInventorySource,
        content_policy_source: FinalContentPolicySource,
        schema_semantics_source: FinalSchemaSemanticsSource,
        authority_behavior_source: FinalAuthorityBehaviorSource,
        static_dependency_source: FinalStaticDependencySource,
        vulnerability_source: FinalVulnerabilitySource,
        malware_source: FinalMalwareSource,
        license_source: FinalLicenseSource,
        contract_source: FinalContractSource,
        runner_source: FinalRunnerSource,
        lab_source: FinalLabSource,
        policy_source: FinalValidationPolicySource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._handoff_source = handoff_source
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._validation_source = validation_source
        self._inventory_source = inventory_source
        self._content_policy_source = content_policy_source
        self._schema_semantics_source = schema_semantics_source
        self._authority_behavior_source = authority_behavior_source
        self._static_dependency_source = static_dependency_source
        self._vulnerability_source = vulnerability_source
        self._malware_source = malware_source
        self._license_source = license_source
        self._contract_source = contract_source
        self._runner_source = runner_source
        self._lab_source = lab_source
        self._policy_source = policy_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_lab_self_test_id: str,
        source_lab_self_test_digest: str,
        package_digest: str,
        policy_id: str,
        policy_digest: str,
        acknowledged_evidence_only_no_approval: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageFinalValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_evidence_only_no_approval:
            raise PackageFinalValidationError("package_final_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageFinalValidationError("package_final_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_lab_self_test_id": source_lab_self_test_id,
                "source_lab_self_test_digest": source_lab_self_test_digest,
                "package_digest": package_digest,
                "policy_id": policy_id,
                "policy_digest": policy_digest,
                "acknowledged_evidence_only_no_approval": True,
            }
        )
        existing = await self._repository.get_by_create_key(
            validated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._reuse(existing, actor, fingerprint)

        lab = await self._lab_source.get_by_id(self_test_id=source_lab_self_test_id)
        if lab is None:
            raise PackageFinalValidationError("package_final_source_not_found")
        self._require_scope(actor, lab.organization_id, lab.environment_id)
        try:
            PackageLabSelfTestService._verify_self_test(lab)
        except Exception as error:
            raise PackageFinalValidationError("package_final_source_integrity_failed") from error
        if (
            lab.canonical_digest != source_lab_self_test_digest
            or lab.package_digest != package_digest
            or lab.outcome.value != "passed"
            or lab.promotion_blocked
            or not lab.lab_validation_completed
        ):
            raise PackageFinalValidationError("package_final_source_not_eligible")

        sources = await self._load_sources(lab)
        policy = await self._policy_source.get_by_id(policy_id=policy_id)
        if policy is None:
            raise PackageFinalValidationError("package_final_policy_not_found")
        self._verify_sources(sources)
        self._verify_policy(policy)
        self._verify_bindings(sources)
        if (
            policy.canonical_digest != policy_digest
            or policy.organization_id != lab.organization_id
            or policy.environment_id != lab.environment_id
        ):
            raise PackageFinalValidationError("package_final_policy_mismatch")

        source_actors = self._source_actors(sources)
        if actor.subject_id in source_actors:
            raise PackageFinalValidationError("package_final_separation_required")
        now = self._clock()
        policy_ok = policy.issued_at <= now < policy.expires_at
        stage_evidence = self._stage_evidence(sources)
        stage_passes = tuple(
            item.outcome in {"passed", "quarantined"} and not item.promotion_blocked
            for item in stage_evidence
        )
        freshness_ok = all(
            item.observed_at <= now
            and now - item.observed_at <= timedelta(days=policy.maximum_evidence_age_days)
            for item in stage_evidence
        )
        coverage_ok = (
            sources.lab.capability_count
            == sources.lab.tested_capability_count
            == sources.contract.coverage.capability_count
            == sources.contract.coverage.covered_capability_count
        )
        finding_count = sum(item.finding_count for item in stage_evidence)
        limitation_count = sum(item.limitation_count for item in stage_evidence)
        risks = self._risks(stage_evidence, policy, now)
        risks_ok = not any(item.blocking for item in risks)
        no_authority_ok = self._no_authority(sources.lab)
        checks = (
            self._check("final.policy.accepted", policy_ok),
            self._check("final.lineage.complete", True),
            *(
                self._check(f"final.stage.{item.stage_code}", passed)
                for item, passed in zip(stage_evidence, stage_passes, strict=True)
            ),
            self._check("final.coverage.complete", coverage_ok),
            self._check("final.risks.classified", risks_ok and freshness_ok),
            self._check("final.no-authority", no_authority_ok),
        )
        eligible = all(item.state is FinalValidationCheckState.PASSED for item in checks)
        outcome = FinalValidationOutcome.ELIGIBLE if eligible else FinalValidationOutcome.BLOCKED
        actor_set_digest = self._digest(sorted(source_actors))
        evidence_digest = self._digest(
            {
                "stage_evidence": self._normalize([asdict(item) for item in stage_evidence]),
                "policy_digest": policy.canonical_digest,
                "source_actor_set_digest": actor_set_digest,
                "checks": self._normalize([asdict(item) for item in checks]),
                "risks": self._normalize([asdict(item) for item in risks]),
                "outcome": outcome.value,
            }
        )
        validation = ConnectorPackageFinalValidation(
            validation_id=f"connector-package-final-validation.{evidence_digest[:24]}",
            schema_version=FINAL_VALIDATION_SCHEMA,
            version=1,
            outcome=outcome,
            source_lab_self_test_id=lab.self_test_id,
            source_lab_self_test_digest=lab.canonical_digest,
            source_handoff_id=sources.handoff.handoff_id,
            source_handoff_digest=sources.handoff.canonical_digest,
            source_project_id=sources.handoff.project_id,
            source_actor_set_digest=actor_set_digest,
            organization_id=lab.organization_id,
            environment_id=lab.environment_id,
            validated_by=actor.subject_id,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            policy_version=policy.policy_version,
            package_digest=lab.package_digest,
            inventory_digest=lab.inventory_digest,
            product_family=lab.product_family,
            observed_product_version=lab.observed_product_version,
            capability_count=lab.capability_count,
            tested_capability_count=lab.tested_capability_count,
            stage_evidence=stage_evidence,
            stage_count=len(stage_evidence),
            passed_stage_count=sum(stage_passes),
            finding_count=finding_count,
            limitation_count=limitation_count,
            blocking_risk_count=sum(item.blocking for item in risks),
            risks=risks,
            checks=checks,
            limitations=FINAL_VALIDATION_LIMITATIONS,
            eligible_for_human_approval=eligible,
            promotion_blocked=not eligible,
            evidence_digest=evidence_digest,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            validated_at=now,
        )
        validation = replace(
            validation,
            canonical_digest=self._digest(self._canonical_payload(validation)),
        )
        async with self._mutation_lock:
            source_existing = await self._repository.get_by_source_self_test(
                source_lab_self_test_id=lab.self_test_id
            )
            if source_existing is not None:
                if (
                    source_existing.validated_by == actor.subject_id
                    and source_existing.idempotency_key == idempotency_key
                    and source_existing.request_fingerprint == fingerprint
                ):
                    return replace(source_existing, reused=True)
                raise PackageFinalValidationError("package_final_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=FINAL_VALIDATION_CREATE_PERMISSION,
                result_code=f"connector_final_validation_{outcome.value}",
                validation=validation,
            )
            if not await self._repository.add(validation):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageFinalValidationError("package_final_conflict")
                self._verify_validation(raced)
                return replace(raced, reused=True)
        return validation

    async def get(
        self, *, actor: AuthenticatedSubject, validation_id: str, correlation_id: str
    ) -> ConnectorPackageFinalValidation:
        self._require_enterprise_human(actor)
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageFinalValidationError("package_final_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        lab = await self._lab_source.get_by_id(self_test_id=validation.source_lab_self_test_id)
        if lab is None:
            raise PackageFinalValidationError("package_final_not_found")
        sources = await self._load_sources(lab)
        if actor.subject_id in self._source_actors(sources):
            raise PackageFinalValidationError("package_final_not_found")
        self._verify_validation(validation)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=FINAL_VALIDATION_READ_PERMISSION,
            result_code="connector_final_validation_read",
            validation=validation,
        )
        return validation

    async def approval_source(
        self, *, validation_id: str
    ) -> tuple[ConnectorPackageFinalValidation, frozenset[str]]:
        """Resolve and re-verify approval lineage without exposing actor identities via HTTP."""
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageFinalValidationError("package_final_not_found")
        self._verify_validation(validation)
        lab = await self._lab_source.get_by_id(self_test_id=validation.source_lab_self_test_id)
        if lab is None:
            raise PackageFinalValidationError("package_final_lineage_incomplete")
        sources = await self._load_sources(lab)
        self._verify_sources(sources)
        self._verify_bindings(sources)
        policy = await self._policy_source.get_by_id(policy_id=validation.policy_id)
        if policy is None:
            raise PackageFinalValidationError("package_final_policy_not_found")
        self._verify_policy(policy)
        if (
            validation.source_lab_self_test_digest != lab.canonical_digest
            or validation.package_digest != lab.package_digest
            or validation.policy_digest != policy.canonical_digest
            or validation.source_actor_set_digest
            != self._digest(sorted(self._source_actors(sources)))
        ):
            raise PackageFinalValidationError("package_final_source_integrity_failed")
        forbidden = self._source_actors(sources) | {validation.validated_by, policy.signed_by}
        return validation, frozenset(forbidden)

    async def registry_publication_source(
        self, *, validation_id: str
    ) -> tuple[
        ConnectorPackageFinalValidation,
        ConnectorPackageAcquisition,
        bytes,
        frozenset[str],
    ]:
        """Resolve the exact acquisition custody behind a still-valid final validation."""
        validation, forbidden = await self.approval_source(validation_id=validation_id)
        lab = await self._lab_source.get_by_id(self_test_id=validation.source_lab_self_test_id)
        if lab is None:
            raise PackageFinalValidationError("package_final_lineage_incomplete")
        sources = await self._load_sources(lab)
        self._verify_sources(sources)
        self._verify_bindings(sources)
        if (
            sources.acquisition.package_digest != validation.package_digest
            or sources.acquisition.organization_id != validation.organization_id
            or sources.acquisition.environment_id != validation.environment_id
        ):
            raise PackageFinalValidationError("package_final_source_integrity_failed")
        try:
            content = await self._archive_source.read(
                package_digest=sources.acquisition.package_digest,
                size_bytes=sources.acquisition.package_size_bytes,
            )
        except Exception as error:
            raise PackageFinalValidationError("package_final_archive_unavailable") from error
        if (
            len(content) != sources.acquisition.package_size_bytes
            or sha256(content).hexdigest() != sources.acquisition.package_digest
        ):
            raise PackageFinalValidationError("package_final_archive_integrity_failed")
        return validation, sources.acquisition, content, forbidden

    async def package_registration_source(
        self, *, validation_id: str
    ) -> tuple[
        ConnectorPackageFinalValidation,
        McpBuilderCandidateHandoff,
        ConnectorPackageAcquisition,
        frozenset[str],
    ]:
        """Resolve exact candidate declarations behind current final-validation evidence."""
        validation, forbidden = await self.approval_source(validation_id=validation_id)
        lab = await self._lab_source.get_by_id(self_test_id=validation.source_lab_self_test_id)
        if lab is None:
            raise PackageFinalValidationError("package_final_lineage_incomplete")
        sources = await self._load_sources(lab)
        self._verify_sources(sources)
        self._verify_bindings(sources)
        if (
            sources.handoff.handoff_id != validation.source_handoff_id
            or sources.handoff.canonical_digest != validation.source_handoff_digest
            or sources.handoff.organization_id != validation.organization_id
            or sources.handoff.environment_id != validation.environment_id
            or len(sources.handoff.capabilities) != validation.capability_count
        ):
            raise PackageFinalValidationError("package_final_source_integrity_failed")
        return validation, sources.handoff, sources.acquisition, forbidden

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageFinalValidationRepository:
        return self._repository

    async def _load_sources(self, lab: ConnectorPackageLabSelfTest) -> _FinalSources:
        runner = await self._runner_source.get_by_id(validation_id=lab.source_runner_validation_id)
        contract = await self._contract_source.get_by_id(
            validation_id=lab.source_contract_validation_id
        )
        if runner is None or contract is None:
            raise PackageFinalValidationError("package_final_lineage_incomplete")
        results = await asyncio.gather(
            self._handoff_source.get_by_id(handoff_id=contract.source_handoff_id),
            self._acquisition_source.get_by_id(acquisition_id=contract.source_acquisition_id),
            self._validation_source.get_by_id(validation_id=contract.source_validation_id),
            self._inventory_source.get_by_id(inventory_id=contract.source_inventory_id),
            self._content_policy_source.get_by_id(scan_id=contract.source_content_policy_scan_id),
            self._schema_semantics_source.get_by_id(
                validation_id=contract.source_schema_semantics_validation_id
            ),
            self._authority_behavior_source.get_by_id(
                validation_id=contract.source_authority_behavior_validation_id
            ),
            self._static_dependency_source.get_by_id(
                analysis_id=contract.source_static_dependency_analysis_id
            ),
            self._vulnerability_source.get_by_id(
                analysis_id=contract.source_vulnerability_analysis_id
            ),
            self._malware_source.get_by_id(analysis_id=contract.source_malware_analysis_id),
            self._license_source.get_by_id(analysis_id=contract.source_license_analysis_id),
        )
        if any(item is None for item in results):
            raise PackageFinalValidationError("package_final_lineage_incomplete")
        return _FinalSources(
            handoff=cast(McpBuilderCandidateHandoff, results[0]),
            acquisition=cast(ConnectorPackageAcquisition, results[1]),
            validation=cast(ConnectorPackageValidation, results[2]),
            inventory=cast(ConnectorPackageSupplyChainInventory, results[3]),
            content_policy=cast(ConnectorPackageContentPolicyScan, results[4]),
            schema_semantics=cast(ConnectorPackageSchemaSemanticsValidation, results[5]),
            authority_behavior=cast(ConnectorPackageAuthorityBehaviorValidation, results[6]),
            static_dependency=cast(ConnectorPackageStaticDependencyAnalysis, results[7]),
            vulnerability=cast(ConnectorPackageVulnerabilityAnalysis, results[8]),
            malware=cast(ConnectorPackageMalwareAnalysis, results[9]),
            license=cast(ConnectorPackageLicenseAnalysis, results[10]),
            contract=contract,
            runner=runner,
            lab=lab,
        )

    @staticmethod
    def _verify_sources(sources: _FinalSources) -> None:
        try:
            PackageAcquisitionService._verify_handoff(sources.handoff)
            PackageAcquisitionService._verify_acquisition(sources.acquisition)
            PackageValidationService._verify_validation(sources.validation)
            PackageSupplyChainInventoryService._verify_inventory(sources.inventory)
            PackageContentPolicyScanService._verify_scan(sources.content_policy)
            PackageSchemaSemanticsValidationService._verify_validation(sources.schema_semantics)
            PackageAuthorityBehaviorValidationService._verify_validation(sources.authority_behavior)
            PackageStaticDependencyAnalysisService._verify_analysis(sources.static_dependency)
            PackageVulnerabilityAnalysisService._verify_analysis(sources.vulnerability)
            PackageMalwareAnalysisService._verify_analysis(sources.malware)
            PackageLicenseAnalysisService._verify_analysis(sources.license)
            PackageContractValidationService._verify_validation(sources.contract)
            PackageRunnerValidationService._verify_validation(sources.runner)
            PackageLabSelfTestService._verify_self_test(sources.lab)
        except Exception as error:
            raise PackageFinalValidationError("package_final_source_integrity_failed") from error

    @classmethod
    def _verify_bindings(cls, s: _FinalSources) -> None:
        common = (
            s.acquisition.package_digest
            == s.validation.package_digest
            == s.inventory.package_digest
            == s.content_policy.package_digest
            == s.schema_semantics.package_digest
            == s.authority_behavior.package_digest
            == s.static_dependency.package_digest
            == s.vulnerability.package_digest
            == s.malware.package_digest
            == s.license.package_digest
            == s.contract.package_digest
            == s.runner.package_digest
            == s.lab.package_digest
            and s.handoff.organization_id == s.lab.organization_id == s.contract.organization_id
            and s.handoff.environment_id == s.lab.environment_id == s.contract.environment_id
            and s.acquisition.source_handoff_id == s.handoff.handoff_id
            and s.acquisition.source_handoff_digest == s.handoff.canonical_digest
            and s.validation.source_acquisition_id == s.acquisition.acquisition_id
            and s.validation.source_acquisition_digest == s.acquisition.canonical_digest
            and s.inventory.source_validation_id == s.validation.validation_id
            and s.inventory.source_validation_digest == s.validation.canonical_digest
            and s.content_policy.source_inventory_id == s.inventory.inventory_id
            and s.content_policy.source_inventory_digest == s.inventory.canonical_digest
            and s.schema_semantics.source_content_policy_scan_id == s.content_policy.scan_id
            and s.schema_semantics.source_content_policy_scan_digest
            == s.content_policy.canonical_digest
            and s.authority_behavior.source_schema_semantics_validation_id
            == s.schema_semantics.validation_id
            and s.authority_behavior.source_schema_semantics_validation_digest
            == s.schema_semantics.canonical_digest
            and s.static_dependency.source_authority_behavior_validation_id
            == s.authority_behavior.validation_id
            and s.static_dependency.source_authority_behavior_validation_digest
            == s.authority_behavior.canonical_digest
            and s.vulnerability.source_static_dependency_analysis_id
            == s.static_dependency.analysis_id
            and s.vulnerability.source_static_dependency_analysis_digest
            == s.static_dependency.canonical_digest
            and s.malware.source_vulnerability_analysis_id == s.vulnerability.analysis_id
            and s.malware.source_vulnerability_analysis_digest == s.vulnerability.canonical_digest
            and s.license.source_malware_analysis_id == s.malware.analysis_id
            and s.license.source_malware_analysis_digest == s.malware.canonical_digest
            and s.contract.source_license_analysis_id == s.license.analysis_id
            and s.contract.source_license_analysis_digest == s.license.canonical_digest
            and s.runner.source_contract_validation_id == s.contract.validation_id
            and s.runner.source_contract_validation_digest == s.contract.canonical_digest
            and s.lab.source_runner_validation_id == s.runner.validation_id
            and s.lab.source_runner_validation_digest == s.runner.canonical_digest
            and s.lab.source_contract_validation_id == s.contract.validation_id
            and s.lab.source_contract_validation_digest == s.contract.canonical_digest
            and s.lab.inventory_digest == s.inventory.inventory_digest
            and s.runner.source_actor_set_digest
            == cls._digest(sorted(s.contract.source_actor_ids | {s.contract.validated_by}))
            == s.lab.source_actor_set_digest
        )
        if not common:
            raise PackageFinalValidationError("package_final_lineage_mismatch")

    @classmethod
    def _stage_evidence(cls, s: _FinalSources) -> tuple[FinalStageEvidence, ...]:
        rows = (
            (
                "acquisition",
                s.acquisition.acquisition_id,
                s.acquisition.canonical_digest,
                s.acquisition.acquired_at,
                s.acquisition.state.value,
                False,
                0,
                len(s.handoff.limitations) + len(s.acquisition.limitations),
            ),
            cls._row("validation-intake", s.validation, "validation_id", "validated_at"),
            cls._row("supply-chain-inventory", s.inventory, "inventory_id", "inventoried_at"),
            cls._row("content-policy", s.content_policy, "scan_id", "scanned_at"),
            cls._row("schema-semantics", s.schema_semantics, "validation_id", "validated_at"),
            cls._row("authority-behavior", s.authority_behavior, "validation_id", "validated_at"),
            cls._row("static-dependency", s.static_dependency, "analysis_id", "analyzed_at"),
            cls._row("vulnerability", s.vulnerability, "analysis_id", "analyzed_at"),
            cls._row("malware", s.malware, "analysis_id", "analyzed_at"),
            cls._row("license", s.license, "analysis_id", "analyzed_at"),
            cls._row("contract", s.contract, "validation_id", "validated_at"),
            cls._row("runner", s.runner, "validation_id", "validated_at"),
            cls._row("lab", s.lab, "self_test_id", "validated_at"),
        )
        return tuple(FinalStageEvidence(*row) for row in rows)

    @staticmethod
    def _row(
        stage: str, source: object, id_field: str, time_field: str
    ) -> tuple[str, str, str, datetime, str, bool, int, int]:
        outcome = cast(Enum, getattr(source, "outcome"))  # noqa: B009
        return (
            stage,
            cast(str, getattr(source, id_field)),
            cast(str, getattr(source, "canonical_digest")),  # noqa: B009
            cast(datetime, getattr(source, time_field)),
            cast(str, outcome.value),
            cast(bool, getattr(source, "promotion_blocked", False)),
            len(cast(tuple[object, ...], getattr(source, "findings", ()))),
            len(cast(tuple[str, ...], getattr(source, "limitations", ()))),
        )

    @staticmethod
    def _risks(
        stages: tuple[FinalStageEvidence, ...],
        policy: FinalValidationPolicySnapshot,
        now: datetime,
    ) -> tuple[FinalRiskSummary, ...]:
        risks = [
            FinalRiskSummary(
                code=f"final.risk.{item.stage_code}.limitations",
                source_stage=item.stage_code,
                source_evidence_id=item.evidence_id,
                source_evidence_digest=item.evidence_digest,
                classification=FinalRiskClassification.DISCLOSED_LIMITATION,
                severity=FinalValidationSeverity.INFORMATIONAL,
                blocking=False,
                occurrence_count=item.limitation_count,
                next_step="Review the source-stage limitations during independent human approval.",
            )
            for item in stages
            if item.limitation_count
        ]
        total = sum(item.limitation_count for item in stages)
        if total > policy.maximum_disclosed_limitations:
            source = stages[-1]
            risks.append(
                FinalRiskSummary(
                    code="final.risk.policy.limitations-exceeded",
                    source_stage=source.stage_code,
                    source_evidence_id=source.evidence_id,
                    source_evidence_digest=source.evidence_digest,
                    classification=FinalRiskClassification.BLOCKING_POLICY,
                    severity=FinalValidationSeverity.ERROR,
                    blocking=True,
                    occurrence_count=total,
                    next_step=(
                        "Resolve or reclassify limitations through an independent policy process."
                    ),
                )
            )
        for item in stages:
            if item.promotion_blocked or item.outcome not in {"passed", "quarantined"}:
                risks.append(
                    FinalRiskSummary(
                        code=f"final.risk.{item.stage_code}.stage-blocked",
                        source_stage=item.stage_code,
                        source_evidence_id=item.evidence_id,
                        source_evidence_digest=item.evidence_digest,
                        classification=FinalRiskClassification.BLOCKING_POLICY,
                        severity=FinalValidationSeverity.ERROR,
                        blocking=True,
                        occurrence_count=1,
                        next_step=(
                            "Resolve the failed source stage and repeat independent validation."
                        ),
                    )
                )
            if item.observed_at > now or now - item.observed_at > timedelta(
                days=policy.maximum_evidence_age_days
            ):
                risks.append(
                    FinalRiskSummary(
                        code=f"final.risk.{item.stage_code}.evidence-stale",
                        source_stage=item.stage_code,
                        source_evidence_id=item.evidence_id,
                        source_evidence_digest=item.evidence_digest,
                        classification=FinalRiskClassification.BLOCKING_POLICY,
                        severity=FinalValidationSeverity.ERROR,
                        blocking=True,
                        occurrence_count=1,
                        next_step="Refresh the source-stage evidence under the active policy.",
                    )
                )
        return tuple(sorted(risks, key=lambda item: item.code))

    @staticmethod
    def _no_authority(lab: ConnectorPackageLabSelfTest) -> bool:
        return not any(
            (
                lab.package_signed,
                lab.publisher_attested,
                lab.connector_rejected,
                lab.connector_registered,
                lab.connector_approved,
                lab.connector_installed,
                lab.connector_enabled,
                lab.target_configured,
                lab.credentials_resolved,
                lab.runtime_trust_granted,
                lab.execution_authorized,
                lab.deployment_approved,
                lab.infrastructure_mutation_performed,
            )
        )

    @staticmethod
    def _source_actors(s: _FinalSources) -> set[str]:
        return s.contract.source_actor_ids | {
            s.contract.validated_by,
            s.runner.validated_by,
            s.lab.validated_by,
            s.lab.lab_plan_approved_by,
            s.lab.credential_custodied_by,
        }

    @staticmethod
    def _check(code: str, passed: bool) -> FinalValidationCheck:
        return FinalValidationCheck(
            code=code,
            state=(
                FinalValidationCheckState.PASSED if passed else FinalValidationCheckState.FAILED
            ),
            severity=(
                FinalValidationSeverity.INFORMATIONAL if passed else FinalValidationSeverity.ERROR
            ),
            summary=(
                "The required final-validation control passed."
                if passed
                else "The required final-validation control failed."
            ),
            remediation=(
                "No remediation is required."
                if passed
                else "Repeat or correct the governed source stage before human approval."
            ),
        )

    @classmethod
    def _verify_policy(cls, policy: FinalValidationPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        if cls._digest(cls._normalize(payload)) != policy.canonical_digest:
            raise PackageFinalValidationError("package_final_policy_integrity_failed")

    @classmethod
    def _verify_validation(cls, validation: ConnectorPackageFinalValidation) -> None:
        if cls._digest(cls._canonical_payload(validation)) != validation.canonical_digest:
            raise PackageFinalValidationError("package_final_integrity_failed")

    @classmethod
    def _canonical_payload(cls, validation: ConnectorPackageFinalValidation) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(validation))
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _reuse(
        cls,
        existing: ConnectorPackageFinalValidation,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorPackageFinalValidation:
        if existing.validated_by != actor.subject_id or existing.request_fingerprint != fingerprint:
            raise PackageFinalValidationError("package_final_idempotency_conflict")
        cls._verify_validation(existing)
        return replace(existing, reused=True)

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
            raise PackageFinalValidationError("package_final_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageFinalValidationError("package_final_not_found")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: ConnectorPackageFinalValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-final-validation",
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
                resource_type="resource.connector.package-final-validation",
                scope_reference=validation.validation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    ("source_lab_self_test_id", validation.source_lab_self_test_id),
                    ("policy_id", validation.policy_id),
                    ("validation_outcome", validation.outcome.value),
                    ("stage_count", str(validation.stage_count)),
                    ("blocking_risk_count", str(validation.blocking_risk_count)),
                ),
            )
        )


def build_development_final_validation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> FinalValidationPolicySnapshot:
    policy = FinalValidationPolicySnapshot(
        policy_id="connector-final-policy.development",
        schema_version="atlas.connector-final-validation-policy.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="version.1.0",
        required_stage_codes=FINAL_VALIDATION_STAGE_CODES,
        maximum_evidence_age_days=3650,
        maximum_disclosed_limitations=100,
        require_complete_capability_coverage=True,
        signed_by="subject.final-policy-authority",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy,
        canonical_digest=PackageFinalValidationService._digest(
            PackageFinalValidationService._normalize(payload)
        ),
    )
