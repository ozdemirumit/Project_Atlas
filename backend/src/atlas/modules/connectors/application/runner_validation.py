from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.adapters.runner_subprocess import (
    RUNNER_ADAPTER_CONTRACT,
    RUNNER_HARNESS_VERSION,
    RUNNER_VALIDATION_PROFILE,
)
from atlas.modules.connectors.application.acquisition import PackageAcquisitionService
from atlas.modules.connectors.application.contract_validation import (
    PackageContractValidationService,
)
from atlas.modules.connectors.application.contract_validation_ports import (
    ContractAcquisitionSource,
    ContractArchiveSource,
    ContractInventorySource,
)
from atlas.modules.connectors.application.runner_validation_ports import (
    PackageRunner,
    PackageRunnerValidationError,
    PackageRunnerValidationRepository,
    RunnerContractSource,
)
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.runner_validation import (
    ConnectorPackageRunnerValidation,
    RunnerCheck,
    RunnerCheckSeverity,
    RunnerCheckState,
    RunnerExecutionResult,
    RunnerValidationOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

RUNNER_VALIDATION_CREATE_PERMISSION = "connectors.package-runner-validations.create"
RUNNER_VALIDATION_READ_PERMISSION = "connectors.package-runner-validations.read"
RUNNER_VALIDATION_SCHEMA = "atlas.connector-package-runner-validation.v1"
RUNNER_LIMITATIONS = (
    "This report proves bounded disconnected synthetic behavior for one exact package only.",
    "The local subprocess adapter is evidence infrastructure, not a production-grade sandbox.",
    "Package tests, source, fixtures, expected values, capability identities, paths, environment, "
    "stdout, stderr, exception text, and harness diagnostics are not retained.",
    "No dependency was resolved or installed and no credential, model, network, or target was "
    "used.",
    "Lab, vendor compatibility, signing, approval, registration, installation, enablement, runtime "
    "trust, execution, and deployment remain prohibited.",
)


class PackageRunnerValidationService:
    def __init__(
        self,
        *,
        repository: PackageRunnerValidationRepository,
        contract_source: RunnerContractSource,
        inventory_source: ContractInventorySource,
        acquisition_source: ContractAcquisitionSource,
        archive_source: ContractArchiveSource,
        runner: PackageRunner,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._contract_source = contract_source
        self._inventory_source = inventory_source
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._runner = runner
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_contract_validation_id: str,
        source_contract_validation_digest: str,
        package_digest: str,
        validation_profile: str,
        acknowledged_disconnected_synthetic_execution: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageRunnerValidation:
        self._require_enterprise_human(actor)
        if not acknowledged_disconnected_synthetic_execution:
            raise PackageRunnerValidationError("package_runner_acknowledgement_required")
        if validation_profile != RUNNER_VALIDATION_PROFILE:
            raise PackageRunnerValidationError("package_runner_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageRunnerValidationError("package_runner_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_contract_validation_id": source_contract_validation_id,
                "source_contract_validation_digest": source_contract_validation_digest,
                "package_digest": package_digest,
                "validation_profile": validation_profile,
                "acknowledged_disconnected_synthetic_execution": True,
                "validated_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            validated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_validation(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageRunnerValidationError("package_runner_idempotency_conflict")

        source = await self._contract_source.get_by_id(validation_id=source_contract_validation_id)
        if source is None:
            raise PackageRunnerValidationError("package_runner_source_not_found")
        self._require_scope(actor, source.organization_id, source.environment_id)
        if actor.subject_id in source.source_actor_ids | {source.validated_by}:
            raise PackageRunnerValidationError("package_runner_separation_required")
        try:
            PackageContractValidationService._verify_validation(source)
        except Exception as error:
            raise PackageRunnerValidationError("package_runner_source_integrity_failed") from error
        if (
            source.outcome.value != "passed"
            or source.promotion_blocked
            or not source.contract_validation_completed
            or source.runner_validation_completed
            or source.runtime_trust_granted
            or source.execution_authorized
            or source.infrastructure_mutation_performed
            or source.canonical_digest != source_contract_validation_digest
            or source.package_digest != package_digest
        ):
            raise PackageRunnerValidationError("package_runner_source_unsupported")

        inventory = await self._inventory_source.get_by_id(inventory_id=source.source_inventory_id)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=source.source_acquisition_id
        )
        if inventory is None or acquisition is None:
            raise PackageRunnerValidationError("package_runner_source_integrity_failed")
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
            PackageAcquisitionService._verify_acquisition(acquisition)
        except Exception as error:
            raise PackageRunnerValidationError("package_runner_source_integrity_failed") from error
        if (
            inventory.inventory_id != source.source_inventory_id
            or inventory.package_digest != source.package_digest
            or inventory.package_size_bytes != source.package_size_bytes
            or inventory.inventory_digest != source.inventory_digest
            or inventory.organization_id != source.organization_id
            or inventory.environment_id != source.environment_id
            or acquisition.acquisition_id != source.source_acquisition_id
            or acquisition.package_digest != source.package_digest
            or acquisition.package_size_bytes != source.package_size_bytes
            or acquisition.organization_id != source.organization_id
            or acquisition.environment_id != source.environment_id
        ):
            raise PackageRunnerValidationError("package_runner_source_integrity_failed")
        try:
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=source.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            PackageStaticDependencyAnalysisService._verify_inventory_files(inventory, files)
        except Exception as error:
            raise PackageRunnerValidationError("package_runner_archive_integrity_failed") from error

        execution = await self._runner.run(files=files, validation_profile=validation_profile)
        if not execution.workspace_removed:
            raise PackageRunnerValidationError("package_runner_cleanup_failed")
        execution = self._enforce_runner_identity(execution)
        execution = self._enforce_coverage(execution, source.coverage.capability_count)
        checks = (
            self._check("runner.source.accepted", True),
            self._check("runner.archive.integrity", True),
            *execution.checks,
        )
        outcome = (
            RunnerValidationOutcome.PASSED
            if all(item.state is RunnerCheckState.PASSED for item in checks)
            else RunnerValidationOutcome.FAILED
        )
        actor_set_digest = self._digest(sorted(source.source_actor_ids | {source.validated_by}))
        evidence_digest = self._digest(
            {
                "source_contract_validation_digest": source.canonical_digest,
                "package_digest": source.package_digest,
                "inventory_digest": source.inventory_digest,
                "profile": validation_profile,
                "adapter_contract": execution.adapter_contract,
                "harness_version": execution.harness_version,
                "runtime_version": execution.runtime_version,
                "checks": self._normalize([asdict(item) for item in checks]),
                "capability_count": execution.capability_count,
                "invoked_capability_count": execution.invoked_capability_count,
                "fail_closed_count": execution.fail_closed_count,
                "bounded_literal_count": execution.bounded_literal_count,
                "output_digest": execution.output_digest,
                "outcome": outcome.value,
            }
        )
        validation = ConnectorPackageRunnerValidation(
            validation_id=f"connector-runner-validation.{evidence_digest[:24]}",
            schema_version=RUNNER_VALIDATION_SCHEMA,
            version=1,
            outcome=outcome,
            source_contract_validation_id=source.validation_id,
            source_contract_validation_digest=source.canonical_digest,
            source_license_analysis_id=source.source_license_analysis_id,
            source_license_analysis_digest=source.source_license_analysis_digest,
            source_inventory_id=source.source_inventory_id,
            source_acquisition_id=source.source_acquisition_id,
            source_project_id=source.source_project_id,
            source_contract_validated_by=source.validated_by,
            source_actor_set_digest=actor_set_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            validated_by=actor.subject_id,
            validation_profile=validation_profile,
            adapter_contract=execution.adapter_contract,
            harness_version=execution.harness_version,
            runtime_version=execution.runtime_version,
            package_digest=source.package_digest,
            package_size_bytes=source.package_size_bytes,
            inventory_digest=source.inventory_digest,
            capability_count=execution.capability_count,
            invoked_capability_count=execution.invoked_capability_count,
            fail_closed_count=execution.fail_closed_count,
            bounded_literal_count=execution.bounded_literal_count,
            checks=checks,
            child_started=execution.child_started,
            child_exit_code=execution.child_exit_code,
            duration_ms=execution.duration_ms,
            output_digest=execution.output_digest,
            output_size_bytes=execution.output_size_bytes,
            workspace_removed=execution.workspace_removed,
            limitations=RUNNER_LIMITATIONS,
            promotion_blocked=outcome is RunnerValidationOutcome.FAILED,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            validated_at=self._clock(),
        )
        validation = replace(
            validation,
            canonical_digest=self._digest(self._canonical_payload(validation)),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_source_validation(
                source_contract_validation_id=source.validation_id
            )
            if existing is not None:
                self._verify_validation(existing)
                if (
                    existing.validated_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageRunnerValidationError("package_runner_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=RUNNER_VALIDATION_CREATE_PERMISSION,
                result_code=f"connector_runner_validation_{outcome.value}",
                validation=validation,
            )
            if not await self._repository.add(validation):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageRunnerValidationError("package_runner_conflict")
                self._verify_validation(raced)
                return replace(raced, reused=True)
        return validation

    async def get(
        self, *, actor: AuthenticatedSubject, validation_id: str, correlation_id: str
    ) -> ConnectorPackageRunnerValidation:
        self._require_enterprise_human(actor)
        validation = await self._repository.get_by_id(validation_id=validation_id)
        if validation is None:
            raise PackageRunnerValidationError("package_runner_not_found")
        self._require_scope(actor, validation.organization_id, validation.environment_id)
        if actor.subject_id == validation.source_contract_validated_by:
            raise PackageRunnerValidationError("package_runner_not_found")
        self._verify_validation(validation)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=RUNNER_VALIDATION_READ_PERMISSION,
            result_code="connector_runner_validation_read",
            validation=validation,
        )
        return validation

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageRunnerValidationRepository:
        return self._repository

    @classmethod
    def _enforce_runner_identity(cls, result: RunnerExecutionResult) -> RunnerExecutionResult:
        valid = bool(
            result.adapter_contract == RUNNER_ADAPTER_CONTRACT
            and result.harness_version == RUNNER_HARNESS_VERSION
            and result.runtime_version.startswith("python.3.12.")
            and result.child_started
            and result.child_exit_code == 0
        )
        if valid:
            return result
        checks = tuple(
            replace(
                item,
                state=RunnerCheckState.FAILED,
                severity=RunnerCheckSeverity.ERROR,
                summary="The isolated runner identity or process result was invalid.",
                remediation="Use the fixed platform runner and repeat validation.",
            )
            if item.code == "runner.process.isolation"
            else item
            for item in result.checks
        )
        return replace(result, checks=checks)

    @classmethod
    def _enforce_coverage(
        cls, result: RunnerExecutionResult, expected_count: int
    ) -> RunnerExecutionResult:
        if result.capability_count == result.invoked_capability_count == expected_count:
            return result
        checks = tuple(
            replace(
                item,
                state=RunnerCheckState.FAILED,
                severity=RunnerCheckSeverity.ERROR,
                summary="The isolated runner capability coverage was incomplete.",
                remediation="Regenerate the exact package and repeat every prior gate.",
            )
            if item.code == "runner.capabilities.synthetic"
            else item
            for item in result.checks
        )
        return replace(result, checks=checks)

    @staticmethod
    def _check(code: str, passed: bool) -> RunnerCheck:
        return RunnerCheck(
            code=code,
            state=RunnerCheckState.PASSED if passed else RunnerCheckState.FAILED,
            severity=(RunnerCheckSeverity.INFORMATIONAL if passed else RunnerCheckSeverity.ERROR),
            summary=(
                "The required runner admission control passed."
                if passed
                else "The required runner admission control failed."
            ),
            remediation=(
                "No remediation is required."
                if passed
                else "Repeat every prior promotion gate for the exact package."
            ),
        )

    @classmethod
    def _canonical_payload(cls, validation: ConnectorPackageRunnerValidation) -> dict[str, object]:
        payload = cls._payload(validation)
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @staticmethod
    def _payload(validation: ConnectorPackageRunnerValidation) -> dict[str, object]:
        return cast(dict[str, object], asdict(validation))

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

    @classmethod
    def _verify_validation(cls, validation: ConnectorPackageRunnerValidation) -> None:
        if cls._digest(cls._canonical_payload(validation)) != validation.canonical_digest:
            raise PackageRunnerValidationError("package_runner_integrity_failed")

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
            raise PackageRunnerValidationError("package_runner_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageRunnerValidationError("package_runner_not_found")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        validation: ConnectorPackageRunnerValidation,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-runner-validation",
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
                resource_type="resource.connector.package-runner-validation",
                scope_reference=validation.validation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=validation.idempotency_key,
                target_metadata=(
                    ("validation_id", validation.validation_id),
                    ("source_contract_validation_id", validation.source_contract_validation_id),
                    ("package_digest", validation.package_digest),
                    ("validation_profile", validation.validation_profile),
                    ("validation_outcome", validation.outcome.value),
                    ("capability_count", str(validation.capability_count)),
                    ("invoked_capability_count", str(validation.invoked_capability_count)),
                ),
            )
        )
