from __future__ import annotations

import asyncio
import json
import tomllib
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.license_analysis_ports import (
    LicenseAcquisitionSource,
    LicenseArchiveSource,
    LicenseInventorySource,
    LicenseMalwareSource,
    LicensePolicySnapshotProvider,
    PackageLicenseAnalysisError,
    PackageLicenseAnalysisRepository,
)
from atlas.modules.connectors.application.malware_analysis import PackageMalwareAnalysisService
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.license_analysis import (
    ConnectorPackageLicenseAnalysis,
    LicenseCheck,
    LicenseCheckSeverity,
    LicenseCheckState,
    LicenseDisposition,
    LicenseFinding,
    LicenseLifecycle,
    LicenseOutcome,
    LicensePolicySnapshot,
    LicensePolicySnapshotSummary,
    LicenseSeverity,
    LicenseSubjectScope,
    LicenseSubjectSummary,
)
from atlas.modules.connectors.domain.malware_analysis import (
    ConnectorPackageMalwareAnalysis,
    MalwareOutcome,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    DependencyKind,
    InventoryOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

LICENSE_ANALYSIS_CREATE_PERMISSION = "connectors.package-license-analyses.create"
LICENSE_ANALYSIS_READ_PERMISSION = "connectors.package-license-analyses.read"
LICENSE_ANALYSIS_SCHEMA = "atlas.connector-package-license-analysis.v1"
LICENSE_ANALYSIS_PROFILE = "atlas.connector-license-policy.python312.v1"
LICENSE_ANALYZER = "atlas.connector-license-policy-analyzer.v1"
LICENSE_POLICY_SNAPSHOT_SCHEMA = "atlas.connector-license-policy-snapshot.v1"
PACKAGE_LICENSE_EXPRESSION = "LicenseRef-Atlas-Internal-Generated"
PYPROJECT_PATH = "pyproject.toml"

LICENSE_LIMITATIONS = (
    "This report compares exact package metadata and represented dependency subjects "
    "to one policy snapshot only.",
    "Raw legal terms, private license identifiers, license and notice bodies, paths, "
    "dependency identities, and policy bodies are not retained.",
    "A passed result is policy-bound, metadata-bound, and internal-distribution-bound "
    "and is not legal advice or a legal conclusion.",
    "Contract, runner, self-test, and lab validation remain incomplete.",
    "Exceptions, public redistribution, rejection, registration, approval, installation, "
    "enablement, runtime trust, execution, and deployment remain prohibited.",
)


def build_bootstrap_license_policy_snapshot(
    *, organization_id: str, environment_id: str, now: datetime
) -> LicensePolicySnapshot:
    issued_at = now.astimezone(UTC)
    snapshot = LicensePolicySnapshot(
        snapshot_id="license-policy-snapshot.bootstrap.v1",
        schema_version=LICENSE_POLICY_SNAPSHOT_SCHEMA,
        snapshot_version="snapshot.bootstrap.v1",
        organization_id=organization_id,
        environment_id=environment_id,
        analysis_profile=LICENSE_ANALYSIS_PROFILE,
        analyzer_version=LICENSE_ANALYZER,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(days=30),
        package_coverage_complete=False,
        source_coverage_complete=False,
        dependency_coverage_complete=False,
        obligation_coverage_complete=False,
        signing_key_id="signing-key.bootstrap.v1",
        signature_verified=True,
        records=(),
        canonical_digest="0" * 64,
    )
    return replace(
        snapshot,
        canonical_digest=PackageLicenseAnalysisService._digest(
            PackageLicenseAnalysisService._snapshot_payload(snapshot)
        ),
    )


class PackageLicenseAnalysisService:
    def __init__(
        self,
        *,
        repository: PackageLicenseAnalysisRepository,
        malware_source: LicenseMalwareSource,
        inventory_source: LicenseInventorySource,
        acquisition_source: LicenseAcquisitionSource,
        archive_source: LicenseArchiveSource,
        policy_provider: LicensePolicySnapshotProvider,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._malware_source = malware_source
        self._inventory_source = inventory_source
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._policy_provider = policy_provider
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_malware_analysis_id: str,
        source_malware_analysis_digest: str,
        package_digest: str,
        analysis_profile: str,
        acknowledged_policy_not_legal_advice: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageLicenseAnalysis:
        self._require_enterprise_human(actor)
        if not acknowledged_policy_not_legal_advice:
            raise PackageLicenseAnalysisError("package_license_acknowledgement_required")
        if analysis_profile != LICENSE_ANALYSIS_PROFILE:
            raise PackageLicenseAnalysisError("package_license_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageLicenseAnalysisError("package_license_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_malware_analysis_id": source_malware_analysis_id,
                "source_malware_analysis_digest": source_malware_analysis_digest,
                "package_digest": package_digest,
                "analysis_profile": analysis_profile,
                "acknowledged_policy_not_legal_advice": True,
                "analyzed_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            analyzed_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_analysis(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageLicenseAnalysisError("package_license_idempotency_conflict")

        source = await self._malware_source.get_by_id(analysis_id=source_malware_analysis_id)
        if source is None:
            raise PackageLicenseAnalysisError("package_license_source_not_found")
        self._require_scope(actor, source.organization_id, source.environment_id)
        self._require_separation(actor, source)
        self._verify_source(source)
        if (
            source.canonical_digest != source_malware_analysis_digest
            or source.package_digest != package_digest
        ):
            raise PackageLicenseAnalysisError("package_license_source_not_found")

        inventory = await self._inventory_source.get_by_id(inventory_id=source.source_inventory_id)
        if inventory is None:
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed")
        self._verify_inventory_binding(source, inventory)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=source.source_acquisition_id
        )
        if acquisition is None:
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed")
        self._verify_acquisition_binding(source, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=source.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            PackageStaticDependencyAnalysisService._verify_inventory_files(inventory, files)
            subjects = self._subjects(inventory, files)
        except PackageLicenseAnalysisError:
            raise
        except Exception as error:
            raise PackageLicenseAnalysisError("package_license_archive_integrity_failed") from error

        try:
            snapshot = await self._policy_provider.current(
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
            self._verify_snapshot(snapshot, source, self._clock())
        except PackageLicenseAnalysisError:
            raise
        except Exception as error:
            raise PackageLicenseAnalysisError("package_license_policy_untrusted") from error

        analyzed_at = self._clock()
        policy_summary, subject_summary, findings = self._analyze(
            source=source,
            subjects=subjects,
            snapshot=snapshot,
            analyzed_at=analyzed_at,
        )
        checks = self._checks(policy_summary, subject_summary)
        outcome = (
            LicenseOutcome.PASSED
            if all(item.state is LicenseCheckState.PASSED for item in checks)
            else LicenseOutcome.FAILED
        )
        finding_set_digest = self._digest(self._finding_payload(findings))
        analysis_digest = self._digest(
            {
                "analyzer_version": LICENSE_ANALYZER,
                "package_digest": source.package_digest,
                "dependency_set_digest": inventory.dependency_set_digest,
                "subject_set_digest": subject_summary.subject_set_digest,
                "policy_snapshot_digest": policy_summary.snapshot_digest,
                "finding_set_digest": finding_set_digest,
            }
        )
        payload = self._canonical_payload(
            source=source,
            inventory=inventory,
            actor_id=actor.subject_id,
            analysis_profile=analysis_profile,
            policy_snapshot=policy_summary,
            subject_summary=subject_summary,
            findings=findings,
            finding_set_digest=finding_set_digest,
            analysis_digest=analysis_digest,
            checks=checks,
            outcome=outcome,
        )
        canonical_digest = self._digest(payload)
        analysis = ConnectorPackageLicenseAnalysis(
            analysis_id=f"connector-license-analysis.{canonical_digest[:24]}",
            schema_version=LICENSE_ANALYSIS_SCHEMA,
            version=1,
            lifecycle=LicenseLifecycle.VALIDATING,
            outcome=outcome,
            source_malware_analysis_id=source.analysis_id,
            source_malware_analysis_digest=source.canonical_digest,
            source_vulnerability_analysis_id=source.source_vulnerability_analysis_id,
            source_vulnerability_analysis_digest=source.source_vulnerability_analysis_digest,
            source_static_dependency_analysis_id=source.source_static_dependency_analysis_id,
            source_static_dependency_analysis_digest=source.source_static_dependency_analysis_digest,
            source_authority_behavior_validation_id=source.source_authority_behavior_validation_id,
            source_schema_semantics_validation_id=source.source_schema_semantics_validation_id,
            source_content_policy_scan_id=source.source_content_policy_scan_id,
            source_inventory_id=source.source_inventory_id,
            source_validation_id=source.source_validation_id,
            source_acquisition_id=source.source_acquisition_id,
            source_handoff_id=source.source_handoff_id,
            source_project_id=source.source_project_id,
            source_acquired_by=source.source_acquired_by,
            source_manifest_validated_by=source.source_manifest_validated_by,
            source_inventoried_by=source.source_inventoried_by,
            source_content_scanned_by=source.source_content_scanned_by,
            source_schema_validated_by=source.source_schema_validated_by,
            source_authority_validated_by=source.source_authority_validated_by,
            source_static_analyzed_by=source.source_static_analyzed_by,
            source_vulnerability_analyzed_by=source.source_vulnerability_analyzed_by,
            source_malware_analyzed_by=source.analyzed_by,
            source_custodied_by=source.source_custodied_by,
            source_domain_reviewed_by=source.source_domain_reviewed_by,
            source_security_reviewed_by=source.source_security_reviewed_by,
            source_lab_operated_by=source.source_lab_operated_by,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            analyzed_by=actor.subject_id,
            analysis_profile=analysis_profile,
            analyzer_version=LICENSE_ANALYZER,
            package_digest=source.package_digest,
            package_size_bytes=source.package_size_bytes,
            inventory_digest=source.inventory_digest,
            dependency_set_digest=inventory.dependency_set_digest,
            policy_snapshot=policy_summary,
            subject_summary=subject_summary,
            findings=findings,
            finding_set_digest=finding_set_digest,
            analysis_digest=analysis_digest,
            checks=checks,
            limitations=LICENSE_LIMITATIONS,
            promotion_blocked=outcome is LicenseOutcome.FAILED,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            analyzed_at=analyzed_at,
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_source_analysis(
                source_malware_analysis_id=source.analysis_id
            )
            if existing is not None:
                self._verify_analysis(existing)
                if (
                    existing.analyzed_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageLicenseAnalysisError("package_license_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=LICENSE_ANALYSIS_CREATE_PERMISSION,
                result_code=f"connector_license_analysis_{outcome.value}",
                analysis=analysis,
            )
            if not await self._repository.add(analysis):
                raced = await self._repository.get_by_create_key(
                    analyzed_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageLicenseAnalysisError("package_license_conflict")
                self._verify_analysis(raced)
                return replace(raced, reused=True)
        return analysis

    async def get(
        self, *, actor: AuthenticatedSubject, analysis_id: str, correlation_id: str
    ) -> ConnectorPackageLicenseAnalysis:
        self._require_enterprise_human(actor)
        analysis = await self._repository.get_by_id(analysis_id=analysis_id)
        if analysis is None:
            raise PackageLicenseAnalysisError("package_license_not_found")
        self._require_scope(actor, analysis.organization_id, analysis.environment_id)
        if actor.subject_id in self._source_actor_ids(analysis):
            raise PackageLicenseAnalysisError("package_license_not_found")
        self._verify_analysis(analysis)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=LICENSE_ANALYSIS_READ_PERMISSION,
            result_code="connector_license_analysis_read",
            analysis=analysis,
        )
        return analysis

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageLicenseAnalysisRepository:
        return self._repository

    @classmethod
    def _subjects(
        cls,
        inventory: ConnectorPackageSupplyChainInventory,
        files: dict[str, bytes],
    ) -> tuple[tuple[LicenseSubjectScope, str], ...]:
        raw = files.get(PYPROJECT_PATH)
        if raw is None or len(raw) > 65_536:
            raise PackageLicenseAnalysisError("package_license_metadata_invalid")
        try:
            document = tomllib.loads(raw.decode("utf-8"))
        except (UnicodeError, tomllib.TOMLDecodeError) as error:
            raise PackageLicenseAnalysisError("package_license_metadata_invalid") from error
        metadata = document.get("project") if isinstance(document, dict) else None
        tool = document.get("tool") if isinstance(document, dict) else None
        atlas = tool.get("atlas") if isinstance(tool, dict) else None
        licensing = atlas.get("licensing") if isinstance(atlas, dict) else None
        if not isinstance(metadata, dict) or not isinstance(licensing, dict):
            raise PackageLicenseAnalysisError("package_license_metadata_invalid")
        package_license = metadata.get("license")
        source_license = licensing.get("source-license-id")
        redistribution = licensing.get("source-redistribution-allowed")
        distribution_mode = licensing.get("distribution-mode")
        if (
            package_license != PACKAGE_LICENSE_EXPRESSION
            or not isinstance(source_license, str)
            or not source_license.strip()
            or len(source_license) > 200
            or not isinstance(redistribution, bool)
            or distribution_mode != "internal"
        ):
            raise PackageLicenseAnalysisError("package_license_metadata_invalid")
        subjects: list[tuple[LicenseSubjectScope, str]] = [
            (
                LicenseSubjectScope.PACKAGE,
                cls.subject_fingerprint(LicenseSubjectScope.PACKAGE, PACKAGE_LICENSE_EXPRESSION),
            ),
            (
                LicenseSubjectScope.SOURCE,
                cls.subject_fingerprint(
                    LicenseSubjectScope.SOURCE,
                    json.dumps(
                        {
                            "license_id": source_license,
                            "redistribution_allowed": redistribution,
                            "distribution_mode": distribution_mode,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ),
                ),
            ),
        ]
        for dependency in inventory.dependencies:
            scope = (
                LicenseSubjectScope.RUNTIME
                if dependency.kind is DependencyKind.RUNTIME
                else LicenseSubjectScope.BUILD
            )
            subjects.append(
                (
                    scope,
                    cls.subject_fingerprint(
                        scope,
                        f"{dependency.name.casefold()}:{dependency.version_constraint}",
                    ),
                )
            )
        return tuple(sorted(subjects, key=lambda item: (item[0], item[1])))

    @classmethod
    def subject_fingerprint(cls, scope: LicenseSubjectScope, identity: str) -> str:
        return cls._digest({"scope": scope.value, "identity": identity})

    @classmethod
    def _analyze(
        cls,
        *,
        source: ConnectorPackageMalwareAnalysis,
        subjects: tuple[tuple[LicenseSubjectScope, str], ...],
        snapshot: LicensePolicySnapshot,
        analyzed_at: datetime,
    ) -> tuple[LicensePolicySnapshotSummary, LicenseSubjectSummary, tuple[LicenseFinding, ...]]:
        fresh = snapshot.issued_at <= analyzed_at < snapshot.expires_at
        coverage_complete = all(
            (
                snapshot.package_coverage_complete,
                snapshot.source_coverage_complete,
                snapshot.dependency_coverage_complete,
                snapshot.obligation_coverage_complete,
            )
        )
        findings: list[LicenseFinding] = []
        if not fresh:
            findings.append(cls._dataset_finding(source, snapshot, "ATLAS-LICENSE-POLICY-EXPIRED"))
        if not coverage_complete:
            findings.append(
                cls._dataset_finding(source, snapshot, "ATLAS-LICENSE-POLICY-INCOMPLETE")
            )
        active = {
            (record.subject_scope, record.subject_fingerprint): record
            for record in snapshot.records
            if record.active
        }
        permitted = review = prohibited = unknown = obligations = unsatisfied = 0
        for scope, fingerprint in subjects:
            record = active.get((scope, fingerprint))
            if record is None:
                unknown += 1
                findings.append(
                    LicenseFinding(
                        rule_id="ATLAS-LICENSE-UNKNOWN",
                        category="policy-coverage",
                        severity=LicenseSeverity.CRITICAL,
                        subject_scope=scope,
                        subject_fingerprint=fingerprint,
                        disposition=LicenseDisposition.REVIEW_REQUIRED,
                        obligations=(),
                        summary="A represented license subject has no admitted policy decision.",
                        remediation=(
                            "Admit an independently reviewed policy record before retrying."
                        ),
                    )
                )
                continue
            obligations += len(record.obligations)
            unsupported = tuple(item for item in record.obligations if item != "internal-use-only")
            unsatisfied += len(unsupported)
            if record.disposition is LicenseDisposition.PERMITTED and not unsupported:
                permitted += 1
                continue
            if record.disposition is LicenseDisposition.PROHIBITED:
                prohibited += 1
                severity = LicenseSeverity.CRITICAL
            else:
                review += 1
                severity = LicenseSeverity.HIGH
            findings.append(
                LicenseFinding(
                    rule_id=record.rule_id,
                    category=record.category,
                    severity=severity,
                    subject_scope=scope,
                    subject_fingerprint=fingerprint,
                    disposition=record.disposition,
                    obligations=record.obligations,
                    summary=(
                        "The represented subject is prohibited by the admitted policy."
                        if record.disposition is LicenseDisposition.PROHIBITED
                        else "The represented subject requires an independent policy decision."
                    ),
                    remediation=(
                        "Resolve the policy disposition and obligations in a new package lineage."
                    ),
                )
            )
        summary = LicenseSubjectSummary(
            package_subject_count=sum(
                scope is LicenseSubjectScope.PACKAGE for scope, _ in subjects
            ),
            source_subject_count=sum(scope is LicenseSubjectScope.SOURCE for scope, _ in subjects),
            runtime_dependency_count=sum(
                scope is LicenseSubjectScope.RUNTIME for scope, _ in subjects
            ),
            transitive_dependency_count=sum(
                scope is LicenseSubjectScope.TRANSITIVE for scope, _ in subjects
            ),
            build_dependency_count=sum(scope is LicenseSubjectScope.BUILD for scope, _ in subjects),
            scanned_subject_count=len(subjects),
            permitted_count=permitted,
            review_required_count=review,
            prohibited_count=prohibited,
            unknown_count=unknown,
            obligation_count=obligations,
            unsatisfied_obligation_count=unsatisfied,
            subject_set_digest=cls._digest([(scope.value, fp) for scope, fp in subjects]),
        )
        snapshot_summary = LicensePolicySnapshotSummary(
            snapshot_id=snapshot.snapshot_id,
            snapshot_version=snapshot.snapshot_version,
            snapshot_digest=snapshot.canonical_digest,
            signing_key_id=snapshot.signing_key_id,
            issued_at=snapshot.issued_at,
            expires_at=snapshot.expires_at,
            analysis_profile=snapshot.analysis_profile,
            analyzer_version=snapshot.analyzer_version,
            record_count=len(snapshot.records),
            package_coverage_complete=snapshot.package_coverage_complete,
            source_coverage_complete=snapshot.source_coverage_complete,
            dependency_coverage_complete=snapshot.dependency_coverage_complete,
            obligation_coverage_complete=snapshot.obligation_coverage_complete,
            fresh=fresh,
        )
        return (
            snapshot_summary,
            summary,
            tuple(
                sorted(
                    findings,
                    key=lambda item: (item.subject_scope, item.subject_fingerprint, item.rule_id),
                )
            ),
        )

    @classmethod
    def _verify_snapshot(
        cls,
        snapshot: LicensePolicySnapshot,
        source: ConnectorPackageMalwareAnalysis,
        now: datetime,
    ) -> None:
        try:
            snapshot.__post_init__()
        except ValueError as error:
            raise PackageLicenseAnalysisError("package_license_policy_untrusted") from error
        if (
            snapshot.schema_version != LICENSE_POLICY_SNAPSHOT_SCHEMA
            or snapshot.organization_id != source.organization_id
            or snapshot.environment_id != source.environment_id
            or snapshot.analysis_profile != LICENSE_ANALYSIS_PROFILE
            or snapshot.analyzer_version != LICENSE_ANALYZER
            or not snapshot.signature_verified
            or snapshot.issued_at > now
            or cls._digest(cls._snapshot_payload(snapshot)) != snapshot.canonical_digest
        ):
            raise PackageLicenseAnalysisError("package_license_policy_untrusted")
        active_keys = [
            (item.subject_scope, item.subject_fingerprint)
            for item in snapshot.records
            if item.active
        ]
        if len(active_keys) != len(set(active_keys)):
            raise PackageLicenseAnalysisError("package_license_policy_untrusted")

    @staticmethod
    def _snapshot_payload(snapshot: LicensePolicySnapshot) -> dict[str, object]:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "schema_version": snapshot.schema_version,
            "snapshot_version": snapshot.snapshot_version,
            "organization_id": snapshot.organization_id,
            "environment_id": snapshot.environment_id,
            "analysis_profile": snapshot.analysis_profile,
            "analyzer_version": snapshot.analyzer_version,
            "issued_at": snapshot.issued_at.isoformat(),
            "expires_at": snapshot.expires_at.isoformat(),
            "package_coverage_complete": snapshot.package_coverage_complete,
            "source_coverage_complete": snapshot.source_coverage_complete,
            "dependency_coverage_complete": snapshot.dependency_coverage_complete,
            "obligation_coverage_complete": snapshot.obligation_coverage_complete,
            "signing_key_id": snapshot.signing_key_id,
            "records": [
                {
                    "rule_id": item.rule_id,
                    "category": item.category,
                    "subject_scope": item.subject_scope.value,
                    "subject_fingerprint": item.subject_fingerprint,
                    "disposition": item.disposition.value,
                    "obligations": item.obligations,
                    "active": item.active,
                }
                for item in snapshot.records
            ],
        }

    @classmethod
    def _dataset_finding(
        cls,
        source: ConnectorPackageMalwareAnalysis,
        snapshot: LicensePolicySnapshot,
        rule_id: str,
    ) -> LicenseFinding:
        return LicenseFinding(
            rule_id=rule_id,
            category="dataset-trust",
            severity=LicenseSeverity.CRITICAL,
            subject_scope=LicenseSubjectScope.DATASET,
            subject_fingerprint=cls._digest(
                {
                    "package_digest": source.package_digest,
                    "snapshot_digest": snapshot.canonical_digest,
                    "rule_id": rule_id,
                }
            ),
            disposition=LicenseDisposition.REVIEW_REQUIRED,
            obligations=(),
            summary="The admitted license policy evidence is not current and complete.",
            remediation="Admit a fresh coverage-complete signed policy snapshot before retrying.",
        )

    @classmethod
    def _checks(
        cls,
        snapshot: LicensePolicySnapshotSummary,
        summary: LicenseSubjectSummary,
    ) -> tuple[LicenseCheck, ...]:
        coverage = snapshot.fresh and all(
            (
                snapshot.package_coverage_complete,
                snapshot.source_coverage_complete,
                snapshot.dependency_coverage_complete,
                snapshot.obligation_coverage_complete,
            )
        )
        permitted = (
            summary.permitted_count == summary.scanned_subject_count
            and summary.review_required_count == 0
            and summary.prohibited_count == 0
            and summary.unknown_count == 0
            and summary.unsatisfied_obligation_count == 0
        )
        return (
            cls._check("license.source.accepted", True, "Provide a passed malware report."),
            cls._check("license.archive.contract", True, "Restore immutable package bytes."),
            cls._check(
                "license.metadata.contract", True, "Restore exact generated license metadata."
            ),
            cls._check(
                "license.policy.trusted", True, "Admit a signed digest-valid policy snapshot."
            ),
            cls._check(
                "license.policy.coverage", coverage, "Refresh complete license policy coverage."
            ),
            cls._check(
                "license.subjects.permitted",
                permitted,
                "Resolve blocking dispositions and obligations.",
            ),
        )

    @staticmethod
    def _check(code: str, passed: bool, remediation: str) -> LicenseCheck:
        return LicenseCheck(
            code=code,
            state=LicenseCheckState.PASSED if passed else LicenseCheckState.FAILED,
            severity=(LicenseCheckSeverity.INFORMATIONAL if passed else LicenseCheckSeverity.ERROR),
            summary="Bounded check passed."
            if passed
            else "Bounded check produced blocking evidence.",
            remediation=remediation,
        )

    @classmethod
    def _canonical_payload(
        cls,
        *,
        source: ConnectorPackageMalwareAnalysis,
        inventory: ConnectorPackageSupplyChainInventory,
        actor_id: str,
        analysis_profile: str,
        policy_snapshot: LicensePolicySnapshotSummary,
        subject_summary: LicenseSubjectSummary,
        findings: tuple[LicenseFinding, ...],
        finding_set_digest: str,
        analysis_digest: str,
        checks: tuple[LicenseCheck, ...],
        outcome: LicenseOutcome,
    ) -> dict[str, object]:
        return {
            "schema_version": LICENSE_ANALYSIS_SCHEMA,
            "version": 1,
            "lifecycle": LicenseLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            **cls._source_fields(source),
            "organization_id": source.organization_id,
            "environment_id": source.environment_id,
            "analyzed_by": actor_id,
            "analysis_profile": analysis_profile,
            "analyzer_version": LICENSE_ANALYZER,
            "package_digest": source.package_digest,
            "package_size_bytes": source.package_size_bytes,
            "inventory_digest": source.inventory_digest,
            "dependency_set_digest": inventory.dependency_set_digest,
            "policy_snapshot": cls._snapshot_summary_payload(policy_snapshot),
            "subject_summary": cls._subject_summary_payload(subject_summary),
            "findings": cls._finding_payload(findings),
            "finding_set_digest": finding_set_digest,
            "analysis_digest": analysis_digest,
            "checks": cls._check_payload(checks),
            "limitations": LICENSE_LIMITATIONS,
            "promotion_blocked": outcome is LicenseOutcome.FAILED,
        }

    @staticmethod
    def _source_fields(source: ConnectorPackageMalwareAnalysis) -> dict[str, str]:
        return {
            "source_malware_analysis_id": source.analysis_id,
            "source_malware_analysis_digest": source.canonical_digest,
            "source_vulnerability_analysis_id": source.source_vulnerability_analysis_id,
            "source_vulnerability_analysis_digest": source.source_vulnerability_analysis_digest,
            "source_static_dependency_analysis_id": source.source_static_dependency_analysis_id,
            "source_static_dependency_analysis_digest": (
                source.source_static_dependency_analysis_digest
            ),
            "source_authority_behavior_validation_id": (
                source.source_authority_behavior_validation_id
            ),
            "source_schema_semantics_validation_id": source.source_schema_semantics_validation_id,
            "source_content_policy_scan_id": source.source_content_policy_scan_id,
            "source_inventory_id": source.source_inventory_id,
            "source_validation_id": source.source_validation_id,
            "source_acquisition_id": source.source_acquisition_id,
            "source_handoff_id": source.source_handoff_id,
            "source_project_id": source.source_project_id,
            "source_acquired_by": source.source_acquired_by,
            "source_manifest_validated_by": source.source_manifest_validated_by,
            "source_inventoried_by": source.source_inventoried_by,
            "source_content_scanned_by": source.source_content_scanned_by,
            "source_schema_validated_by": source.source_schema_validated_by,
            "source_authority_validated_by": source.source_authority_validated_by,
            "source_static_analyzed_by": source.source_static_analyzed_by,
            "source_vulnerability_analyzed_by": source.source_vulnerability_analyzed_by,
            "source_malware_analyzed_by": source.analyzed_by,
            "source_custodied_by": source.source_custodied_by,
            "source_domain_reviewed_by": source.source_domain_reviewed_by,
            "source_security_reviewed_by": source.source_security_reviewed_by,
            "source_lab_operated_by": source.source_lab_operated_by,
        }

    @classmethod
    def _canonical_payload_from_analysis(
        cls, analysis: ConnectorPackageLicenseAnalysis
    ) -> dict[str, object]:
        source_fields = {
            field: getattr(analysis, field)
            for field in (
                "source_malware_analysis_id",
                "source_malware_analysis_digest",
                "source_vulnerability_analysis_id",
                "source_vulnerability_analysis_digest",
                "source_static_dependency_analysis_id",
                "source_static_dependency_analysis_digest",
                "source_authority_behavior_validation_id",
                "source_schema_semantics_validation_id",
                "source_content_policy_scan_id",
                "source_inventory_id",
                "source_validation_id",
                "source_acquisition_id",
                "source_handoff_id",
                "source_project_id",
                "source_acquired_by",
                "source_manifest_validated_by",
                "source_inventoried_by",
                "source_content_scanned_by",
                "source_schema_validated_by",
                "source_authority_validated_by",
                "source_static_analyzed_by",
                "source_vulnerability_analyzed_by",
                "source_malware_analyzed_by",
                "source_custodied_by",
                "source_domain_reviewed_by",
                "source_security_reviewed_by",
                "source_lab_operated_by",
            )
        }
        return {
            "schema_version": analysis.schema_version,
            "version": analysis.version,
            "lifecycle": analysis.lifecycle.value,
            "outcome": analysis.outcome.value,
            **source_fields,
            "organization_id": analysis.organization_id,
            "environment_id": analysis.environment_id,
            "analyzed_by": analysis.analyzed_by,
            "analysis_profile": analysis.analysis_profile,
            "analyzer_version": analysis.analyzer_version,
            "package_digest": analysis.package_digest,
            "package_size_bytes": analysis.package_size_bytes,
            "inventory_digest": analysis.inventory_digest,
            "dependency_set_digest": analysis.dependency_set_digest,
            "policy_snapshot": cls._snapshot_summary_payload(analysis.policy_snapshot),
            "subject_summary": cls._subject_summary_payload(analysis.subject_summary),
            "findings": cls._finding_payload(analysis.findings),
            "finding_set_digest": analysis.finding_set_digest,
            "analysis_digest": analysis.analysis_digest,
            "checks": cls._check_payload(analysis.checks),
            "limitations": analysis.limitations,
            "promotion_blocked": analysis.promotion_blocked,
        }

    @classmethod
    def _verify_analysis(cls, analysis: ConnectorPackageLicenseAnalysis) -> None:
        try:
            analysis.__post_init__()
        except ValueError as error:
            raise PackageLicenseAnalysisError("package_license_integrity_failed") from error
        if cls._digest(cls._canonical_payload_from_analysis(analysis)) != analysis.canonical_digest:
            raise PackageLicenseAnalysisError("package_license_integrity_failed")

    @staticmethod
    def _snapshot_summary_payload(item: LicensePolicySnapshotSummary) -> dict[str, object]:
        return {
            "snapshot_id": item.snapshot_id,
            "snapshot_version": item.snapshot_version,
            "snapshot_digest": item.snapshot_digest,
            "signing_key_id": item.signing_key_id,
            "issued_at": item.issued_at.isoformat(),
            "expires_at": item.expires_at.isoformat(),
            "analysis_profile": item.analysis_profile,
            "analyzer_version": item.analyzer_version,
            "record_count": item.record_count,
            "package_coverage_complete": item.package_coverage_complete,
            "source_coverage_complete": item.source_coverage_complete,
            "dependency_coverage_complete": item.dependency_coverage_complete,
            "obligation_coverage_complete": item.obligation_coverage_complete,
            "fresh": item.fresh,
        }

    @staticmethod
    def _subject_summary_payload(item: LicenseSubjectSummary) -> dict[str, object]:
        return {
            field: getattr(item, field)
            for field in (
                "package_subject_count",
                "source_subject_count",
                "runtime_dependency_count",
                "transitive_dependency_count",
                "build_dependency_count",
                "scanned_subject_count",
                "permitted_count",
                "review_required_count",
                "prohibited_count",
                "unknown_count",
                "obligation_count",
                "unsatisfied_obligation_count",
                "subject_set_digest",
            )
        }

    @staticmethod
    def _finding_payload(items: tuple[LicenseFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_id": item.rule_id,
                "category": item.category,
                "severity": item.severity.value,
                "subject_scope": item.subject_scope.value,
                "subject_fingerprint": item.subject_fingerprint,
                "disposition": item.disposition.value,
                "obligations": item.obligations,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def _check_payload(items: tuple[LicenseCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def _verify_source(source: ConnectorPackageMalwareAnalysis) -> None:
        try:
            PackageMalwareAnalysisService._verify_analysis(source)
        except Exception as error:
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed") from error
        if (
            source.outcome is not MalwareOutcome.PASSED
            or source.promotion_blocked
            or not source.vulnerability_scan_completed
            or not source.malware_scan_completed
            or source.license_scan_completed
            or source.connector_rejected
            or source.connector_registered
            or source.runtime_trust_granted
            or source.execution_authorized
            or source.infrastructure_mutation_performed
        ):
            raise PackageLicenseAnalysisError("package_license_source_unsupported")

    @staticmethod
    def _verify_inventory_binding(
        source: ConnectorPackageMalwareAnalysis,
        inventory: ConnectorPackageSupplyChainInventory,
    ) -> None:
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
        except Exception as error:
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed") from error
        if (
            inventory.outcome is not InventoryOutcome.PASSED
            or inventory.inventory_id != source.source_inventory_id
            or inventory.package_digest != source.package_digest
            or inventory.package_size_bytes != source.package_size_bytes
            or inventory.inventory_digest != source.inventory_digest
            or inventory.organization_id != source.organization_id
            or inventory.environment_id != source.environment_id
        ):
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed")

    @staticmethod
    def _verify_acquisition_binding(
        source: ConnectorPackageMalwareAnalysis,
        acquisition: ConnectorPackageAcquisition,
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed") from error
        if (
            acquisition.acquisition_id != source.source_acquisition_id
            or acquisition.package_digest != source.package_digest
            or acquisition.package_size_bytes != source.package_size_bytes
            or acquisition.organization_id != source.organization_id
            or acquisition.environment_id != source.environment_id
        ):
            raise PackageLicenseAnalysisError("package_license_source_integrity_failed")

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
            raise PackageLicenseAnalysisError("package_license_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageLicenseAnalysisError("package_license_not_found")

    @staticmethod
    def _require_separation(
        actor: AuthenticatedSubject, source: ConnectorPackageMalwareAnalysis
    ) -> None:
        source_actors = {
            source.source_acquired_by,
            source.source_manifest_validated_by,
            source.source_inventoried_by,
            source.source_content_scanned_by,
            source.source_schema_validated_by,
            source.source_authority_validated_by,
            source.source_static_analyzed_by,
            source.source_vulnerability_analyzed_by,
            source.analyzed_by,
            source.source_custodied_by,
            source.source_domain_reviewed_by,
            source.source_security_reviewed_by,
            source.source_lab_operated_by,
        }
        if actor.subject_id in source_actors:
            raise PackageLicenseAnalysisError("package_license_separation_required")

    @staticmethod
    def _source_actor_ids(analysis: ConnectorPackageLicenseAnalysis) -> set[str]:
        return {
            analysis.source_acquired_by,
            analysis.source_manifest_validated_by,
            analysis.source_inventoried_by,
            analysis.source_content_scanned_by,
            analysis.source_schema_validated_by,
            analysis.source_authority_validated_by,
            analysis.source_static_analyzed_by,
            analysis.source_vulnerability_analyzed_by,
            analysis.source_malware_analyzed_by,
            analysis.source_custodied_by,
            analysis.source_domain_reviewed_by,
            analysis.source_security_reviewed_by,
            analysis.source_lab_operated_by,
        }

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        analysis: ConnectorPackageLicenseAnalysis,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-license-analysis",
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
                resource_type="resource.connector.package-license-analysis",
                scope_reference=analysis.analysis_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=analysis.idempotency_key,
                target_metadata=(
                    ("analysis_id", analysis.analysis_id),
                    ("source_malware_analysis_id", analysis.source_malware_analysis_id),
                    ("package_digest", analysis.package_digest),
                    ("policy_snapshot_id", analysis.policy_snapshot.snapshot_id),
                    ("policy_snapshot_digest", analysis.policy_snapshot.snapshot_digest),
                    ("analysis_outcome", analysis.outcome.value),
                    (
                        "scanned_subject_count",
                        str(analysis.subject_summary.scanned_subject_count),
                    ),
                    (
                        "blocking_subject_count",
                        str(
                            analysis.subject_summary.review_required_count
                            + analysis.subject_summary.prohibited_count
                            + analysis.subject_summary.unknown_count
                        ),
                    ),
                    (
                        "unsatisfied_obligation_count",
                        str(analysis.subject_summary.unsatisfied_obligation_count),
                    ),
                ),
            )
        )
