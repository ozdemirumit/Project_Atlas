from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.content_policy_scan_ports import (
    ContentPolicyAcquisitionSource,
    ContentPolicyArchiveSource,
    ContentPolicyInventorySource,
    PackageContentPolicyScanError,
    PackageContentPolicyScanRepository,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    INSPECTOR_VERSION,
    INVENTORY_PROFILE,
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.content_policy_scan import (
    ConnectorPackageContentPolicyScan,
    ContentPolicyCheck,
    ContentPolicyCheckState,
    ContentPolicyFinding,
    ContentPolicyFindingKind,
    ContentPolicyLifecycle,
    ContentPolicyOutcome,
    ContentPolicySeverity,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    InventoryOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

CONTENT_POLICY_CREATE_PERMISSION = "connectors.package-content-policy-scans.create"
CONTENT_POLICY_READ_PERMISSION = "connectors.package-content-policy-scans.read"
CONTENT_POLICY_SCHEMA = "atlas.connector-package-content-policy-scan.v1"
CONTENT_POLICY_PROFILE = "atlas.connector-content-policy-scan.python312.v1"
CONTENT_POLICY_SCANNER = "atlas.connector-secret-prohibited-content-scanner.v1"

CONTENT_POLICY_LIMITATIONS = (
    "This report proves only the bounded embedded-secret and prohibited-content scan.",
    "No matched value, source snippet, decoded body, secret length, or reversible digest is "
    "retained.",
    "Vulnerability, malware, license, schema-semantic, static-code, permission-behavior, contract, "
    "runner, self-test, and lab validation remain incomplete.",
    "Signing, attestation, rejection, registration, approval, installation, enablement, runtime "
    "trust, execution, and deployment remain prohibited.",
)

_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
_KNOWN_TOKEN = re.compile(r"(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|sk-[A-Za-z0-9]{20,})")
_AUTHORIZATION = re.compile(
    r"(?i)\bauthorization\s*[:=]\s*['\"]?(?:bearer|basic)\s+[A-Za-z0-9+/_.=-]{12,}"
)
_CREDENTIAL_URL = re.compile(r"(?i)https?://[^\s/:@]{1,100}:[^\s/@]{1,200}@")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)\b"
    r"\s*[:=]\s*['\"]?([^'\"\s,;}{]{4,300})"
)
_PLACEHOLDERS = frozenset(
    {
        "changeme",
        "dummy",
        "example",
        "placeholder",
        "redacted",
        "sample",
        "synthetic",
        "test",
        "unset",
    }
)
_PROHIBITED_SUFFIXES = frozenset(
    {
        ".7z",
        ".class",
        ".dll",
        ".dylib",
        ".exe",
        ".gz",
        ".jar",
        ".msi",
        ".pyd",
        ".pyc",
        ".pyo",
        ".rar",
        ".so",
        ".tar",
        ".whl",
        ".zip",
    }
)
_PROHIBITED_PARTS = frozenset({".git", ".hg", ".svn", "__pycache__", "node_modules"})
_BINARY_MAGIC = (
    (b"MZ", "content.prohibited.executable-magic"),
    (b"\x7fELF", "content.prohibited.executable-magic"),
    (b"PK\x03\x04", "content.prohibited.nested-archive"),
    (b"\x1f\x8b", "content.prohibited.nested-archive"),
)


class PackageContentPolicyScanService:
    def __init__(
        self,
        *,
        repository: PackageContentPolicyScanRepository,
        inventory_source: ContentPolicyInventorySource,
        acquisition_source: ContentPolicyAcquisitionSource,
        archive_source: ContentPolicyArchiveSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._inventory_source = inventory_source
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_inventory_id: str,
        source_inventory_digest: str,
        package_digest: str,
        scan_profile: str,
        acknowledged_untrusted_package_content: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageContentPolicyScan:
        self._require_enterprise_human(actor)
        if not acknowledged_untrusted_package_content:
            raise PackageContentPolicyScanError("package_content_policy_acknowledgement_required")
        if scan_profile != CONTENT_POLICY_PROFILE:
            raise PackageContentPolicyScanError("package_content_policy_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageContentPolicyScanError("package_content_policy_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_inventory_id": source_inventory_id,
                "source_inventory_digest": source_inventory_digest,
                "package_digest": package_digest,
                "scan_profile": scan_profile,
                "acknowledged_untrusted_package_content": True,
                "scanned_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            scanned_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_scan(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageContentPolicyScanError("package_content_policy_idempotency_conflict")

        inventory = await self._inventory_source.get_by_id(inventory_id=source_inventory_id)
        if inventory is None:
            raise PackageContentPolicyScanError("package_content_policy_source_not_found")
        self._require_scope(actor, inventory.organization_id, inventory.environment_id)
        self._require_separation(actor, inventory)
        self._verify_source_inventory(inventory)
        if (
            inventory.canonical_digest != source_inventory_digest
            or inventory.package_digest != package_digest
        ):
            raise PackageContentPolicyScanError("package_content_policy_source_not_found")
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=inventory.source_acquisition_id
        )
        if acquisition is None:
            raise PackageContentPolicyScanError("package_content_policy_source_integrity_failed")
        self._verify_acquisition_binding(inventory, acquisition)
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=inventory.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            self._verify_inventory_files(inventory, files)
        except PackageContentPolicyScanError:
            raise
        except Exception as error:
            raise PackageContentPolicyScanError(
                "package_content_policy_archive_integrity_failed"
            ) from error

        findings = self._scan_files(package_digest, files)
        secret_findings = tuple(
            item for item in findings if item.kind is ContentPolicyFindingKind.EMBEDDED_SECRET
        )
        prohibited_findings = tuple(
            item for item in findings if item.kind is ContentPolicyFindingKind.PROHIBITED_CONTENT
        )
        checks = self._checks(
            secret_findings=secret_findings,
            prohibited_findings=prohibited_findings,
        )
        outcome = (
            ContentPolicyOutcome.PASSED
            if all(item.state is ContentPolicyCheckState.PASSED for item in checks)
            else ContentPolicyOutcome.FAILED
        )
        finding_set_digest = self._digest(self._finding_payload(findings))
        content_scan_digest = self._digest(
            {
                "scanner_version": CONTENT_POLICY_SCANNER,
                "package_digest": inventory.package_digest,
                "inventory_digest": inventory.inventory_digest,
                "files": [
                    {
                        "relative_path": item.relative_path,
                        "digest": item.digest,
                        "size_bytes": item.size_bytes,
                        "content_class": item.content_class.value,
                    }
                    for item in inventory.files
                ],
            }
        )
        payload = self._canonical_payload(
            inventory=inventory,
            actor_id=actor.subject_id,
            scan_profile=scan_profile,
            findings=findings,
            finding_set_digest=finding_set_digest,
            content_scan_digest=content_scan_digest,
            checks=checks,
            outcome=outcome,
        )
        canonical_digest = self._digest(payload)
        scan = ConnectorPackageContentPolicyScan(
            scan_id=f"connector-content-policy-scan.{canonical_digest[:24]}",
            schema_version=CONTENT_POLICY_SCHEMA,
            version=1,
            lifecycle=ContentPolicyLifecycle.VALIDATING,
            outcome=outcome,
            source_inventory_id=inventory.inventory_id,
            source_inventory_digest=inventory.canonical_digest,
            source_validation_id=inventory.source_validation_id,
            source_validation_digest=inventory.source_validation_digest,
            source_acquisition_id=inventory.source_acquisition_id,
            source_acquisition_digest=inventory.source_acquisition_digest,
            source_handoff_id=inventory.source_handoff_id,
            source_project_id=inventory.source_project_id,
            source_acquired_by=inventory.source_acquired_by,
            source_validated_by=inventory.source_validated_by,
            source_inventoried_by=inventory.inventoried_by,
            source_custodied_by=inventory.source_custodied_by,
            source_domain_reviewed_by=inventory.source_domain_reviewed_by,
            source_security_reviewed_by=inventory.source_security_reviewed_by,
            source_lab_operated_by=inventory.source_lab_operated_by,
            organization_id=inventory.organization_id,
            environment_id=inventory.environment_id,
            scanned_by=actor.subject_id,
            scan_profile=scan_profile,
            scanner_version=CONTENT_POLICY_SCANNER,
            package_digest=inventory.package_digest,
            package_size_bytes=inventory.package_size_bytes,
            inventory_digest=inventory.inventory_digest,
            dependency_set_digest=inventory.dependency_set_digest,
            scanned_file_count=len(inventory.files),
            findings=findings,
            finding_set_digest=finding_set_digest,
            content_scan_digest=content_scan_digest,
            checks=checks,
            limitations=CONTENT_POLICY_LIMITATIONS,
            promotion_blocked=outcome is ContentPolicyOutcome.FAILED,
            canonical_digest=canonical_digest,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            scanned_at=self._clock(),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_inventory(
                source_inventory_id=source_inventory_id
            )
            if existing is not None:
                self._verify_scan(existing)
                if (
                    existing.scanned_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageContentPolicyScanError("package_content_policy_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=CONTENT_POLICY_CREATE_PERMISSION,
                result_code=f"connector_content_policy_scan_{outcome.value}",
                scan=scan,
            )
            if not await self._repository.add(scan):
                raced = await self._repository.get_by_create_key(
                    scanned_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageContentPolicyScanError("package_content_policy_conflict")
                self._verify_scan(raced)
                return replace(raced, reused=True)
        return scan

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        scan_id: str,
        correlation_id: str,
    ) -> ConnectorPackageContentPolicyScan:
        self._require_enterprise_human(actor)
        scan = await self._repository.get_by_id(scan_id=scan_id)
        if scan is None:
            raise PackageContentPolicyScanError("package_content_policy_not_found")
        self._require_scope(actor, scan.organization_id, scan.environment_id)
        if actor.subject_id in self._source_actors(scan):
            raise PackageContentPolicyScanError("package_content_policy_not_found")
        self._verify_scan(scan)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=CONTENT_POLICY_READ_PERMISSION,
            result_code="connector_content_policy_scan_read",
            scan=scan,
        )
        return scan

    async def close(self) -> None:
        await self._repository.close()

    @staticmethod
    def _verify_source_inventory(inventory: ConnectorPackageSupplyChainInventory) -> None:
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
        except Exception as error:
            raise PackageContentPolicyScanError(
                "package_content_policy_source_integrity_failed"
            ) from error
        if (
            inventory.outcome is not InventoryOutcome.PASSED
            or inventory.inventory_profile != INVENTORY_PROFILE
            or inventory.inspector_version != INSPECTOR_VERSION
            or not inventory.content_inventory_completed
            or not inventory.dependency_inventory_completed
            or inventory.secret_content_scan_completed
            or inventory.prohibited_content_scan_completed
            or inventory.connector_rejected
            or inventory.connector_registered
            or inventory.runtime_trust_granted
            or inventory.execution_authorized
            or inventory.infrastructure_mutation_performed
        ):
            raise PackageContentPolicyScanError("package_content_policy_source_unsupported")

    @staticmethod
    def _verify_acquisition_binding(
        inventory: ConnectorPackageSupplyChainInventory,
        acquisition: ConnectorPackageAcquisition,
    ) -> None:
        try:
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageContentPolicyScanError(
                "package_content_policy_source_integrity_failed"
            ) from error
        if (
            acquisition.acquisition_id != inventory.source_acquisition_id
            or acquisition.canonical_digest != inventory.source_acquisition_digest
            or acquisition.package_digest != inventory.package_digest
            or acquisition.package_size_bytes != inventory.package_size_bytes
            or acquisition.organization_id != inventory.organization_id
            or acquisition.environment_id != inventory.environment_id
        ):
            raise PackageContentPolicyScanError("package_content_policy_source_integrity_failed")

    @staticmethod
    def _verify_inventory_files(
        inventory: ConnectorPackageSupplyChainInventory, files: dict[str, bytes]
    ) -> None:
        actual = tuple(
            (
                path,
                sha256(raw).hexdigest(),
                len(raw),
                PackageSupplyChainInventoryService._classify(path),
            )
            for path, raw in sorted(files.items())
        )
        expected = tuple(
            (item.relative_path, item.digest, item.size_bytes, item.content_class)
            for item in inventory.files
        )
        if actual != expected:
            raise PackageContentPolicyScanError("package_content_policy_inventory_mismatch")

    @classmethod
    def _scan_files(
        cls, package_digest: str, files: dict[str, bytes]
    ) -> tuple[ContentPolicyFinding, ...]:
        findings: list[ContentPolicyFinding] = []
        for path, raw in sorted(files.items()):
            findings.extend(cls._scan_prohibited(package_digest, path, raw))
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                findings.append(
                    cls._finding(
                        package_digest,
                        path,
                        None,
                        "content.prohibited.non-utf8",
                        ContentPolicyFindingKind.PROHIBITED_CONTENT,
                        raw[:32],
                        "Package text is not strict UTF-8.",
                        "Replace the file with bounded UTF-8 text for this package profile.",
                    )
                )
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                findings.extend(cls._scan_line(package_digest, path, line_number, line))
        return tuple(
            sorted(
                findings,
                key=lambda item: (item.relative_path, item.line_number or 0, item.rule_code),
            )
        )

    @classmethod
    def _scan_prohibited(
        cls, package_digest: str, path: str, raw: bytes
    ) -> list[ContentPolicyFinding]:
        findings: list[ContentPolicyFinding] = []
        pure = PurePosixPath(path)
        if pure.suffix.casefold() in _PROHIBITED_SUFFIXES or any(
            part.casefold() in _PROHIBITED_PARTS for part in pure.parts
        ):
            findings.append(
                cls._finding(
                    package_digest,
                    path,
                    None,
                    "content.prohibited.path",
                    ContentPolicyFindingKind.PROHIBITED_CONTENT,
                    path.encode("utf-8"),
                    "Package contains a prohibited path or file type.",
                    "Remove executable, generated, nested-package, or repository metadata files.",
                )
            )
        for magic, rule in _BINARY_MAGIC:
            if raw.startswith(magic):
                findings.append(
                    cls._finding(
                        package_digest,
                        path,
                        None,
                        rule,
                        ContentPolicyFindingKind.PROHIBITED_CONTENT,
                        magic,
                        "Package content has a prohibited binary or nested-archive signature.",
                        "Remove binary and nested archive content from the source package.",
                    )
                )
        controls = bytes(item for item in raw if item < 32 and item not in {9, 10, 13})
        if controls:
            findings.append(
                cls._finding(
                    package_digest,
                    path,
                    None,
                    "content.prohibited.control-byte",
                    ContentPolicyFindingKind.PROHIBITED_CONTENT,
                    controls[:32],
                    "Package text contains prohibited control bytes.",
                    "Replace control bytes with bounded printable UTF-8 text.",
                )
            )
        return findings

    @classmethod
    def _scan_line(
        cls, package_digest: str, path: str, line_number: int, line: str
    ) -> list[ContentPolicyFinding]:
        rules: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
            (
                "secret.embedded.private-key",
                _PRIVATE_KEY,
                "Package contains private-key material.",
                "Remove the private key and use an approved opaque secret reference.",
            ),
            (
                "secret.embedded.known-token",
                _KNOWN_TOKEN,
                "Package contains a recognized credential token form.",
                "Revoke the credential, remove it, and use an approved opaque secret reference.",
            ),
            (
                "secret.embedded.authorization",
                _AUTHORIZATION,
                "Package contains a literal authorization credential.",
                "Remove the authorization value and inject credentials only in the governed "
                "runner.",
            ),
            (
                "secret.embedded.credential-url",
                _CREDENTIAL_URL,
                "Package contains a credential-bearing URL.",
                "Remove URL user information and use separate endpoint and secret references.",
            ),
        )
        findings: list[ContentPolicyFinding] = []
        for rule, pattern, summary, remediation in rules:
            for match in pattern.finditer(line):
                findings.append(
                    cls._finding(
                        package_digest,
                        path,
                        line_number,
                        rule,
                        ContentPolicyFindingKind.EMBEDDED_SECRET,
                        match.group(0).encode("utf-8"),
                        summary,
                        remediation,
                    )
                )
        for match in _SENSITIVE_ASSIGNMENT.finditer(line):
            value = match.group(2)
            normalized = value.casefold().strip()
            if (
                normalized in _PLACEHOLDERS
                or normalized.startswith(("secret.", "${", "{{"))
                or normalized.endswith(("_ref", "-ref"))
            ):
                continue
            findings.append(
                cls._finding(
                    package_digest,
                    path,
                    line_number,
                    "secret.embedded.sensitive-assignment",
                    ContentPolicyFindingKind.EMBEDDED_SECRET,
                    match.group(0).encode("utf-8"),
                    "Package contains a literal value in a sensitive assignment.",
                    "Replace the literal with an approved opaque secret reference.",
                )
            )
        return findings

    @staticmethod
    def _finding(
        package_digest: str,
        path: str,
        line_number: int | None,
        rule_code: str,
        kind: ContentPolicyFindingKind,
        matched: bytes,
        summary: str,
        remediation: str,
    ) -> ContentPolicyFinding:
        fingerprint = sha256(
            b"atlas-content-policy-v1\0"
            + package_digest.encode("ascii")
            + b"\0"
            + path.encode("utf-8")
            + b"\0"
            + rule_code.encode("ascii")
            + b"\0"
            + matched
        ).hexdigest()
        return ContentPolicyFinding(
            rule_code=rule_code,
            kind=kind,
            severity=ContentPolicySeverity.ERROR,
            relative_path=path,
            line_number=line_number,
            evidence_fingerprint=fingerprint,
            summary=summary,
            remediation=remediation,
        )

    @classmethod
    def _checks(
        cls,
        *,
        secret_findings: tuple[ContentPolicyFinding, ...],
        prohibited_findings: tuple[ContentPolicyFinding, ...],
    ) -> tuple[ContentPolicyCheck, ...]:
        return (
            cls._check(
                "content-policy.source.accepted",
                True,
                "Exact passed inventory evidence accepted.",
                (),
                "Restore exact passed inventory evidence.",
            ),
            cls._check(
                "content-policy.archive.contract",
                True,
                "Exact acquired archive contract accepted.",
                (),
                "Restore exact acquired archive bytes.",
            ),
            cls._check(
                "content-policy.inventory.contract",
                True,
                "Every archive file matches the exact passed inventory.",
                (),
                "Restore exact path, digest, size, and class inventory bindings.",
            ),
            cls._check(
                "content-policy.secret-content",
                not secret_findings,
                "No bounded embedded-secret detector produced a finding.",
                tuple(sorted({item.relative_path for item in secret_findings})),
                "Remove embedded credentials and use approved opaque secret references.",
            ),
            cls._check(
                "content-policy.prohibited-content",
                not prohibited_findings,
                "No prohibited path, binary signature, encoding, or control-byte finding exists.",
                tuple(sorted({item.relative_path for item in prohibited_findings})),
                "Remove prohibited content and restore bounded UTF-8 profile files.",
            ),
        )

    @staticmethod
    def _check(
        code: str,
        passed: bool,
        summary: str,
        evidence_paths: tuple[str, ...],
        remediation: str,
    ) -> ContentPolicyCheck:
        return ContentPolicyCheck(
            code=code,
            state=ContentPolicyCheckState.PASSED if passed else ContentPolicyCheckState.FAILED,
            severity=(
                ContentPolicySeverity.INFORMATIONAL if passed else ContentPolicySeverity.ERROR
            ),
            summary=summary,
            evidence_paths=evidence_paths,
            remediation=remediation,
        )

    @classmethod
    def _canonical_payload(
        cls,
        *,
        inventory: ConnectorPackageSupplyChainInventory,
        actor_id: str,
        scan_profile: str,
        findings: tuple[ContentPolicyFinding, ...],
        finding_set_digest: str,
        content_scan_digest: str,
        checks: tuple[ContentPolicyCheck, ...],
        outcome: ContentPolicyOutcome,
    ) -> dict[str, object]:
        return {
            "lifecycle": ContentPolicyLifecycle.VALIDATING.value,
            "outcome": outcome.value,
            "source_inventory_id": inventory.inventory_id,
            "source_inventory_digest": inventory.canonical_digest,
            "source_validation_id": inventory.source_validation_id,
            "source_validation_digest": inventory.source_validation_digest,
            "source_acquisition_id": inventory.source_acquisition_id,
            "source_acquisition_digest": inventory.source_acquisition_digest,
            "source_handoff_id": inventory.source_handoff_id,
            "source_project_id": inventory.source_project_id,
            "source_acquired_by": inventory.source_acquired_by,
            "source_validated_by": inventory.source_validated_by,
            "source_inventoried_by": inventory.inventoried_by,
            "source_custodied_by": inventory.source_custodied_by,
            "source_domain_reviewed_by": inventory.source_domain_reviewed_by,
            "source_security_reviewed_by": inventory.source_security_reviewed_by,
            "source_lab_operated_by": inventory.source_lab_operated_by,
            "organization_id": inventory.organization_id,
            "environment_id": inventory.environment_id,
            "scanned_by": actor_id,
            "scan_profile": scan_profile,
            "scanner_version": CONTENT_POLICY_SCANNER,
            "package_digest": inventory.package_digest,
            "package_size_bytes": inventory.package_size_bytes,
            "inventory_digest": inventory.inventory_digest,
            "dependency_set_digest": inventory.dependency_set_digest,
            "scanned_file_count": len(inventory.files),
            "findings": cls._finding_payload(findings),
            "finding_set_digest": finding_set_digest,
            "content_scan_digest": content_scan_digest,
            "checks": cls._check_payload(checks),
            "limitations": CONTENT_POLICY_LIMITATIONS,
            "promotion_blocked": outcome is ContentPolicyOutcome.FAILED,
        }

    @classmethod
    def _verify_scan(cls, scan: ConnectorPackageContentPolicyScan) -> None:
        payload = {
            "lifecycle": scan.lifecycle.value,
            "outcome": scan.outcome.value,
            "source_inventory_id": scan.source_inventory_id,
            "source_inventory_digest": scan.source_inventory_digest,
            "source_validation_id": scan.source_validation_id,
            "source_validation_digest": scan.source_validation_digest,
            "source_acquisition_id": scan.source_acquisition_id,
            "source_acquisition_digest": scan.source_acquisition_digest,
            "source_handoff_id": scan.source_handoff_id,
            "source_project_id": scan.source_project_id,
            "source_acquired_by": scan.source_acquired_by,
            "source_validated_by": scan.source_validated_by,
            "source_inventoried_by": scan.source_inventoried_by,
            "source_custodied_by": scan.source_custodied_by,
            "source_domain_reviewed_by": scan.source_domain_reviewed_by,
            "source_security_reviewed_by": scan.source_security_reviewed_by,
            "source_lab_operated_by": scan.source_lab_operated_by,
            "organization_id": scan.organization_id,
            "environment_id": scan.environment_id,
            "scanned_by": scan.scanned_by,
            "scan_profile": scan.scan_profile,
            "scanner_version": scan.scanner_version,
            "package_digest": scan.package_digest,
            "package_size_bytes": scan.package_size_bytes,
            "inventory_digest": scan.inventory_digest,
            "dependency_set_digest": scan.dependency_set_digest,
            "scanned_file_count": scan.scanned_file_count,
            "findings": cls._finding_payload(scan.findings),
            "finding_set_digest": scan.finding_set_digest,
            "content_scan_digest": scan.content_scan_digest,
            "checks": cls._check_payload(scan.checks),
            "limitations": scan.limitations,
            "promotion_blocked": scan.promotion_blocked,
        }
        if cls._digest(payload) != scan.canonical_digest:
            raise PackageContentPolicyScanError("package_content_policy_integrity_failed")

    @staticmethod
    def _finding_payload(findings: tuple[ContentPolicyFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_code": item.rule_code,
                "kind": item.kind.value,
                "severity": item.severity.value,
                "relative_path": item.relative_path,
                "line_number": item.line_number,
                "evidence_fingerprint": item.evidence_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in findings
        ]

    @staticmethod
    def _check_payload(checks: tuple[ContentPolicyCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "evidence_paths": item.evidence_paths,
                "remediation": item.remediation,
            }
            for item in checks
        ]

    @staticmethod
    def _digest(payload: object) -> str:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise PackageContentPolicyScanError(
                "package_content_policy_enterprise_human_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageContentPolicyScanError("package_content_policy_not_found")

    @classmethod
    def _require_separation(
        cls, actor: AuthenticatedSubject, inventory: ConnectorPackageSupplyChainInventory
    ) -> None:
        if actor.subject_id in cls._inventory_source_actors(inventory):
            raise PackageContentPolicyScanError("package_content_policy_not_found")

    @staticmethod
    def _inventory_source_actors(inventory: ConnectorPackageSupplyChainInventory) -> set[str]:
        return {
            inventory.source_acquired_by,
            inventory.source_validated_by,
            inventory.inventoried_by,
            inventory.source_custodied_by,
            inventory.source_domain_reviewed_by,
            inventory.source_security_reviewed_by,
            inventory.source_lab_operated_by,
        }

    @staticmethod
    def _source_actors(scan: ConnectorPackageContentPolicyScan) -> set[str]:
        return {
            scan.source_acquired_by,
            scan.source_validated_by,
            scan.source_inventoried_by,
            scan.source_custodied_by,
            scan.source_domain_reviewed_by,
            scan.source_security_reviewed_by,
            scan.source_lab_operated_by,
        }

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scan: ConnectorPackageContentPolicyScan,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-content-policy-scan",
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
                resource_type="resource.connector.package-content-policy-scan",
                scope_reference=scan.scan_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=scan.idempotency_key,
                target_metadata=(
                    ("scan_id", scan.scan_id),
                    ("source_inventory_id", scan.source_inventory_id),
                    ("package_digest", scan.package_digest),
                    ("scan_outcome", scan.outcome.value),
                    ("finding_count", str(len(scan.findings))),
                ),
            )
        )
