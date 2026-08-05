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
from atlas.modules.connectors.adapters.lab_mock_target import (
    LAB_ADAPTER_CONTRACT,
    LAB_RUNNER_RUNTIME,
    LAB_SELF_TEST_PROFILE,
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
from atlas.modules.connectors.application.lab_self_test_ports import (
    ConnectorLabPlanSource,
    ConnectorLabRunner,
    LabAccessBroker,
    LabRunnerValidationSource,
    PackageLabSelfTestError,
    PackageLabSelfTestRepository,
)
from atlas.modules.connectors.application.runner_validation import PackageRunnerValidationService
from atlas.modules.connectors.application.runner_validation_ports import RunnerContractSource
from atlas.modules.connectors.application.static_dependency_analysis import (
    PackageStaticDependencyAnalysisService,
)
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.validation_intake import PackageValidationService
from atlas.modules.connectors.domain.lab_self_test import (
    ConnectorLabPlan,
    ConnectorPackageLabSelfTest,
    LabCheck,
    LabCheckSeverity,
    LabCheckState,
    LabExecutionResult,
    LabSelfTestOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

LAB_SELF_TEST_CREATE_PERMISSION = "connectors.package-lab-self-tests.create"
LAB_SELF_TEST_READ_PERMISSION = "connectors.package-lab-self-tests.read"
LAB_SELF_TEST_SCHEMA = "atlas.connector-package-lab-self-test.v1"
LAB_LIMITATIONS = (
    "This report proves bounded read-only behavior for one exact package and approved lab plan.",
    "The foundation mock-target adapter proves orchestration controls, not vendor compatibility.",
    "Target coordinates, trust material, secret references and values, raw traffic, package "
    "internals, "
    "paths, stdout, stderr, and exception details are not retained.",
    "The temporary lab lease and credential handle are released before evidence is persisted.",
    "Signing, approval, registration, installation, enablement, production trust, execution, and "
    "deployment remain prohibited.",
)


class PackageLabSelfTestService:
    def __init__(
        self,
        *,
        repository: PackageLabSelfTestRepository,
        runner_source: LabRunnerValidationSource,
        contract_source: RunnerContractSource,
        inventory_source: ContractInventorySource,
        acquisition_source: ContractAcquisitionSource,
        archive_source: ContractArchiveSource,
        plan_source: ConnectorLabPlanSource,
        access_broker: LabAccessBroker,
        runner: ConnectorLabRunner,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._runner_source = runner_source
        self._contract_source = contract_source
        self._inventory_source = inventory_source
        self._acquisition_source = acquisition_source
        self._archive_source = archive_source
        self._plan_source = plan_source
        self._access_broker = access_broker
        self._runner = runner
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_runner_validation_id: str,
        source_runner_validation_digest: str,
        package_digest: str,
        lab_plan_id: str,
        lab_plan_digest: str,
        validation_profile: str,
        acknowledged_non_production_read_only_lab_access: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorPackageLabSelfTest:
        self._require_enterprise_human(actor)
        if not acknowledged_non_production_read_only_lab_access:
            raise PackageLabSelfTestError("package_lab_acknowledgement_required")
        if validation_profile != LAB_SELF_TEST_PROFILE:
            raise PackageLabSelfTestError("package_lab_profile_unsupported")
        if not 8 <= len(idempotency_key) <= 128:
            raise PackageLabSelfTestError("package_lab_idempotency_key_invalid")
        fingerprint = self._digest(
            {
                "source_runner_validation_id": source_runner_validation_id,
                "source_runner_validation_digest": source_runner_validation_digest,
                "package_digest": package_digest,
                "lab_plan_id": lab_plan_id,
                "lab_plan_digest": lab_plan_digest,
                "validation_profile": validation_profile,
                "acknowledged_non_production_read_only_lab_access": True,
                "validated_by": actor.subject_id,
            }
        )
        replay = await self._repository.get_by_create_key(
            validated_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            self._verify_self_test(replay)
            if replay.request_fingerprint == fingerprint:
                return replace(replay, reused=True)
            raise PackageLabSelfTestError("package_lab_idempotency_conflict")

        source = await self._runner_source.get_by_id(validation_id=source_runner_validation_id)
        plan = await self._plan_source.get_by_id(plan_id=lab_plan_id)
        if source is None or plan is None:
            raise PackageLabSelfTestError("package_lab_source_not_found")
        self._require_scope(actor, source.organization_id, source.environment_id)
        try:
            PackageRunnerValidationService._verify_validation(source)
            self._verify_plan(plan)
        except Exception as error:
            raise PackageLabSelfTestError("package_lab_source_integrity_failed") from error
        if (
            source.outcome.value != "passed"
            or source.promotion_blocked
            or not source.runner_validation_completed
            or source.lab_validation_completed
            or source.runtime_trust_granted
            or source.execution_authorized
            or source.infrastructure_mutation_performed
            or source.canonical_digest != source_runner_validation_digest
            or source.package_digest != package_digest
            or plan.canonical_digest != lab_plan_digest
            or plan.validation_profile != validation_profile
            or plan.adapter_contract != LAB_ADAPTER_CONTRACT
            or plan.organization_id != source.organization_id
            or plan.environment_id != source.environment_id
            or plan.capability_count != source.capability_count
            or plan.approved_at > self._clock()
            or plan.expires_at <= self._clock()
        ):
            raise PackageLabSelfTestError("package_lab_source_unsupported")

        contract = await self._contract_source.get_by_id(
            validation_id=source.source_contract_validation_id
        )
        if contract is None:
            raise PackageLabSelfTestError("package_lab_source_integrity_failed")
        try:
            PackageContractValidationService._verify_validation(contract)
        except Exception as error:
            raise PackageLabSelfTestError("package_lab_source_integrity_failed") from error
        source_actors = contract.source_actor_ids | {contract.validated_by, source.validated_by}
        if actor.subject_id in source_actors | {plan.approved_by, plan.credential_custodied_by}:
            raise PackageLabSelfTestError("package_lab_separation_required")
        if (
            plan.approved_by in source_actors
            or plan.credential_custodied_by in source_actors
            or contract.validation_id != source.source_contract_validation_id
            or contract.canonical_digest != source.source_contract_validation_digest
            or contract.package_digest != source.package_digest
            or contract.inventory_digest != source.inventory_digest
            or self._digest(sorted(contract.source_actor_ids | {contract.validated_by}))
            != source.source_actor_set_digest
        ):
            raise PackageLabSelfTestError("package_lab_source_integrity_failed")

        inventory = await self._inventory_source.get_by_id(inventory_id=source.source_inventory_id)
        acquisition = await self._acquisition_source.get_by_id(
            acquisition_id=source.source_acquisition_id
        )
        if inventory is None or acquisition is None:
            raise PackageLabSelfTestError("package_lab_source_integrity_failed")
        try:
            PackageSupplyChainInventoryService._verify_inventory(inventory)
            PackageAcquisitionService._verify_acquisition(acquisition)
            content = await self._archive_source.read(
                package_digest=package_digest, size_bytes=source.package_size_bytes
            )
            files, _ = PackageValidationService._verify_archive(acquisition, content)
            PackageStaticDependencyAnalysisService._verify_inventory_files(inventory, files)
        except Exception as error:
            raise PackageLabSelfTestError("package_lab_archive_integrity_failed") from error

        try:
            lease = await self._access_broker.issue(plan=plan)
        except Exception as error:
            raise PackageLabSelfTestError("package_lab_lease_unavailable") from error
        execution: LabExecutionResult | None = None
        runner_error: Exception | None = None
        released = False
        try:
            if (
                lease.plan_id != plan.plan_id
                or lease.issued_at > self._clock()
                or lease.expires_at <= self._clock()
            ):
                raise PackageLabSelfTestError("package_lab_lease_invalid")
            execution = await self._runner.run(files=files, plan=plan, lease=lease)
        except PackageLabSelfTestError:
            raise
        except Exception as error:
            runner_error = error
        finally:
            released = await self._access_broker.release(lease=lease)
        if runner_error is not None or execution is None:
            raise PackageLabSelfTestError("package_lab_runner_unavailable")
        execution = self._enforce_execution(execution, plan)
        checks = (
            self._check("lab.source.accepted", True),
            self._check("lab.plan.approved", True),
            self._check("lab.package.integrity", True),
            *execution.checks[:-1],
            self._check("lab.access.revoked", released),
            execution.checks[-1],
        )
        outcome = (
            LabSelfTestOutcome.PASSED
            if all(item.state is LabCheckState.PASSED for item in checks)
            else LabSelfTestOutcome.FAILED
        )
        evidence_digest = self._digest(
            {
                "source_runner_validation_digest": source.canonical_digest,
                "source_contract_validation_digest": contract.canonical_digest,
                "lab_plan_digest": plan.canonical_digest,
                "package_digest": source.package_digest,
                "inventory_digest": source.inventory_digest,
                "profile": validation_profile,
                "adapter_contract": execution.adapter_contract,
                "runner_runtime": execution.runner_runtime,
                "observed_product_version": execution.observed_product_version,
                "checks": self._normalize([asdict(item) for item in checks]),
                "capability_count": execution.capability_count,
                "tested_capability_count": execution.tested_capability_count,
                "request_count": execution.request_count,
                "request_bytes": execution.request_bytes,
                "response_bytes": execution.response_bytes,
                "runner_evidence_digest": execution.evidence_digest,
                "outcome": outcome.value,
            }
        )
        self_test = ConnectorPackageLabSelfTest(
            self_test_id=f"connector-lab-self-test.{evidence_digest[:24]}",
            schema_version=LAB_SELF_TEST_SCHEMA,
            version=1,
            outcome=outcome,
            source_runner_validation_id=source.validation_id,
            source_runner_validation_digest=source.canonical_digest,
            source_contract_validation_id=source.source_contract_validation_id,
            source_contract_validation_digest=source.source_contract_validation_digest,
            source_inventory_id=source.source_inventory_id,
            source_acquisition_id=source.source_acquisition_id,
            source_project_id=source.source_project_id,
            source_runner_validated_by=source.validated_by,
            source_actor_set_digest=source.source_actor_set_digest,
            lab_plan_id=plan.plan_id,
            lab_plan_digest=plan.canonical_digest,
            lab_plan_approved_by=plan.approved_by,
            credential_custodied_by=plan.credential_custodied_by,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            validated_by=actor.subject_id,
            target_alias=plan.target_alias,
            product_family=plan.product_family,
            observed_product_version=execution.observed_product_version,
            validation_profile=validation_profile,
            adapter_contract=execution.adapter_contract,
            runner_runtime=execution.runner_runtime,
            package_digest=source.package_digest,
            package_size_bytes=source.package_size_bytes,
            inventory_digest=source.inventory_digest,
            capability_count=execution.capability_count,
            tested_capability_count=execution.tested_capability_count,
            request_count=execution.request_count,
            request_bytes=execution.request_bytes,
            response_bytes=execution.response_bytes,
            checks=checks,
            duration_ms=execution.duration_ms,
            evidence_digest=evidence_digest,
            lease_issued=execution.lease_issued,
            lease_released=released,
            credentials_revoked=released,
            session_closed=execution.session_closed,
            workspace_removed=execution.workspace_removed,
            limitations=LAB_LIMITATIONS,
            promotion_blocked=outcome is LabSelfTestOutcome.FAILED,
            canonical_digest="0" * 64,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            validated_at=self._clock(),
        )
        self_test = replace(
            self_test,
            canonical_digest=self._digest(self._canonical_payload(self_test)),
        )
        async with self._mutation_lock:
            existing = await self._repository.get_by_source_validation(
                source_runner_validation_id=source.validation_id
            )
            if existing is not None:
                self._verify_self_test(existing)
                if (
                    existing.validated_by == actor.subject_id
                    and existing.idempotency_key == idempotency_key
                    and existing.request_fingerprint == fingerprint
                ):
                    return replace(existing, reused=True)
                raise PackageLabSelfTestError("package_lab_exists")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=LAB_SELF_TEST_CREATE_PERMISSION,
                result_code=f"connector_lab_self_test_{outcome.value}",
                self_test=self_test,
            )
            if not await self._repository.add(self_test):
                raced = await self._repository.get_by_create_key(
                    validated_by=actor.subject_id, idempotency_key=idempotency_key
                )
                if raced is None or raced.request_fingerprint != fingerprint:
                    raise PackageLabSelfTestError("package_lab_conflict")
                self._verify_self_test(raced)
                return replace(raced, reused=True)
        return self_test

    async def get(
        self, *, actor: AuthenticatedSubject, self_test_id: str, correlation_id: str
    ) -> ConnectorPackageLabSelfTest:
        self._require_enterprise_human(actor)
        self_test = await self._repository.get_by_id(self_test_id=self_test_id)
        if self_test is None:
            raise PackageLabSelfTestError("package_lab_not_found")
        self._require_scope(actor, self_test.organization_id, self_test.environment_id)
        contract = await self._contract_source.get_by_id(
            validation_id=self_test.source_contract_validation_id
        )
        if contract is None or actor.subject_id in contract.source_actor_ids | {
            contract.validated_by,
            self_test.source_runner_validated_by,
            self_test.lab_plan_approved_by,
            self_test.credential_custodied_by,
        }:
            raise PackageLabSelfTestError("package_lab_not_found")
        self._verify_self_test(self_test)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=LAB_SELF_TEST_READ_PERMISSION,
            result_code="connector_lab_self_test_read",
            self_test=self_test,
        )
        return self_test

    async def close(self) -> None:
        await self._repository.close()

    @property
    def repository(self) -> PackageLabSelfTestRepository:
        return self._repository

    @classmethod
    def _enforce_execution(
        cls, result: LabExecutionResult, plan: ConnectorLabPlan
    ) -> LabExecutionResult:
        checks = result.checks
        identity_valid = (
            result.adapter_contract == plan.adapter_contract == LAB_ADAPTER_CONTRACT
            and result.runner_runtime == LAB_RUNNER_RUNTIME
            and result.observed_product_version == plan.product_version
            and result.lease_issued
        )
        if not identity_valid:
            checks = cls._fail_check(
                checks, "lab.tls.identity", "Lab identity evidence mismatched."
            )
        coverage_valid = (
            result.capability_count == result.tested_capability_count == plan.capability_count
        )
        if not coverage_valid:
            checks = cls._fail_check(
                checks, "lab.capabilities.readonly", "Lab capability coverage was incomplete."
            )
        budget_valid = (
            result.request_count <= plan.max_requests
            and result.request_bytes <= plan.max_request_bytes
            and result.response_bytes <= plan.max_response_bytes
            and result.duration_ms <= plan.timeout_seconds * 1_000
        )
        if not budget_valid:
            checks = cls._fail_check(
                checks, "lab.response.bounded", "Lab request or response budget was exceeded."
            )
        if not result.session_closed:
            checks = cls._fail_check(checks, "lab.session.closed", "Lab session remained open.")
        if not result.workspace_removed:
            checks = cls._fail_check(
                checks, "lab.workspace.cleaned", "Lab workspace cleanup was incomplete."
            )
        return replace(result, checks=checks)

    @staticmethod
    def _fail_check(checks: tuple[LabCheck, ...], code: str, summary: str) -> tuple[LabCheck, ...]:
        return tuple(
            replace(
                item,
                state=LabCheckState.FAILED,
                severity=LabCheckSeverity.ERROR,
                summary=summary,
                remediation=(
                    "Correct the approved lab boundary and repeat with a new governed package."
                ),
            )
            if item.code == code
            else item
            for item in checks
        )

    @staticmethod
    def _check(code: str, passed: bool) -> LabCheck:
        return LabCheck(
            code=code,
            state=LabCheckState.PASSED if passed else LabCheckState.FAILED,
            severity=(LabCheckSeverity.INFORMATIONAL if passed else LabCheckSeverity.ERROR),
            summary=(
                "The required lab admission control passed."
                if passed
                else "The required lab admission control failed."
            ),
            remediation=(
                "No remediation is required."
                if passed
                else "Repeat every prior promotion gate and obtain a new approved lab plan."
            ),
        )

    @classmethod
    def _plan_payload(cls, plan: ConnectorLabPlan) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(plan))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _verify_plan(cls, plan: ConnectorLabPlan) -> None:
        if cls._digest(cls._plan_payload(plan)) != plan.canonical_digest:
            raise PackageLabSelfTestError("package_lab_plan_integrity_failed")

    @classmethod
    def _canonical_payload(cls, self_test: ConnectorPackageLabSelfTest) -> dict[str, object]:
        payload = cls._payload(self_test)
        for field in ("canonical_digest", "request_fingerprint", "idempotency_key", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @staticmethod
    def _payload(self_test: ConnectorPackageLabSelfTest) -> dict[str, object]:
        return cast(dict[str, object], asdict(self_test))

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
    def _verify_self_test(cls, self_test: ConnectorPackageLabSelfTest) -> None:
        if cls._digest(cls._canonical_payload(self_test)) != self_test.canonical_digest:
            raise PackageLabSelfTestError("package_lab_integrity_failed")

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
            raise PackageLabSelfTestError("package_lab_enterprise_human_mfa_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise PackageLabSelfTestError("package_lab_not_found")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        self_test: ConnectorPackageLabSelfTest,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.package-lab-self-test",
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
                resource_type="resource.connector.package-lab-self-test",
                scope_reference=self_test.self_test_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=self_test.idempotency_key,
                target_metadata=(
                    ("self_test_id", self_test.self_test_id),
                    ("source_runner_validation_id", self_test.source_runner_validation_id),
                    ("lab_plan_id", self_test.lab_plan_id),
                    ("target_alias", self_test.target_alias),
                    ("product_family", self_test.product_family),
                    ("validation_outcome", self_test.outcome.value),
                    ("capability_count", str(self_test.capability_count)),
                    ("tested_capability_count", str(self_test.tested_capability_count)),
                ),
            )
        )


def build_development_lab_plan(
    *, organization_id: str, environment_id: str, approved_at: datetime, expires_at: datetime
) -> ConnectorLabPlan:
    plan = ConnectorLabPlan(
        plan_id="connector-lab-plan.development-readonly",
        schema_version="atlas.connector-lab-plan.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        target_alias="target.lab.synthetic-storage",
        product_family="product.synthetic-storage",
        product_version="1.0",
        validation_profile=LAB_SELF_TEST_PROFILE,
        adapter_contract=LAB_ADAPTER_CONTRACT,
        allowed_capability_classes=("C0", "C1"),
        capability_count=1,
        destination_references=("destination.lab.synthetic-storage",),
        tls_trust_reference="trust.lab.synthetic-storage",
        secret_reference_ids=("secret.lab.synthetic-storage.readonly",),
        max_requests=16,
        max_request_bytes=65_536,
        max_response_bytes=262_144,
        timeout_seconds=30,
        approved_by="subject.lab.plan-approver",
        credential_custodied_by="subject.lab.credential-custodian",
        approved_at=approved_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        plan,
        canonical_digest=PackageLabSelfTestService._digest(
            PackageLabSelfTestService._plan_payload(plan)
        ),
    )
