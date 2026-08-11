from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Protocol, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.instance_creation import (
    INSTANCE_READ_PERMISSION,
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_installation_ports import PackageInstallationError
from atlas.modules.connectors.application.target_configuration_ports import (
    ConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.domain.instance_creation import RETIRED, ConnectorInstanceRecord
from atlas.modules.connectors.domain.package_installation import ConnectorPackageInstallationReceipt
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord
from atlas.modules.connectors.domain.upgrade_readiness import (
    ConnectorCapabilityChange,
    ConnectorUpgradeCandidate,
    ConnectorUpgradePlan,
    ConnectorUpgradePlanStep,
    ConnectorUpgradeReadiness,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

UPGRADE_READINESS_SCHEMA = "atlas.connector-upgrade-readiness.v1"
UPGRADE_PLAN_SCHEMA = "atlas.connector-upgrade-plan.v1"
_SEMVER = re.compile(
    r"^version\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class ConnectorUpgradePackageSource(Protocol):
    async def get(
        self, *, receipt_id: str
    ) -> tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord]: ...

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[
        tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord], ...
    ]: ...


class PackageInstallationUpgradeSource:
    def __init__(self, service: PackageInstallationService) -> None:
        self._service = service

    async def get(
        self, *, receipt_id: str
    ) -> tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord]:
        try:
            (
                receipt,
                _policy,
                registration,
                _actors,
            ) = await self._service.connector_instance_creation_source(receipt_id=receipt_id)
        except PackageInstallationError as error:
            raise ConnectorInstanceCreationError("connector_upgrade_source_not_found") from error
        return receipt, registration

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord], ...]:
        receipts = await self._service.repository.list_scope(
            organization_id=organization_id,
            environment_id=environment_id,
        )
        resolved = []
        for receipt in receipts:
            resolved.append(await self.get(receipt_id=receipt.receipt_id))
        return tuple(resolved)


class ConnectorUpgradeReadinessService:
    def __init__(
        self,
        *,
        instance_repository: ConnectorInstanceRepository,
        target_repository: ConnectorTargetConfigurationRepository,
        package_source: ConnectorUpgradePackageSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._instance_repository = instance_repository
        self._target_repository = target_repository
        self._package_source = package_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def evaluate(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradeReadiness:
        self._require_enterprise_human(actor)
        record = await self._instance_repository.get(record_id=record_id)
        if record is None:
            raise ConnectorInstanceCreationError("connector_instance_record_not_found")
        ConnectorInstanceCreationService._verify_record(record)
        if (
            record.organization_id != actor.organization_id
            or record.environment_id != self._environment_id
        ):
            raise ConnectorInstanceCreationError("connector_instance_record_not_found")
        if record.instance_state == RETIRED:
            raise ConnectorInstanceCreationError("connector_upgrade_source_retired")

        current_receipt, current_registration = await self._package_source.get(
            receipt_id=record.source_installation_receipt_id
        )
        self._verify_current_binding(record, current_receipt, current_registration)
        target = await self._target_repository.get_by_instance(
            source_instance_record_id=record.record_id
        )
        packages = await self._package_source.list_scope(
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        candidates = tuple(
            sorted(
                (
                    self._candidate(
                        current_receipt=current_receipt,
                        current_registration=current_registration,
                        candidate_receipt=receipt,
                        candidate_registration=registration,
                        target_configured=target is not None,
                    )
                    for receipt, registration in packages
                    if receipt.connector_id == record.connector_id
                    and receipt.package_digest != record.package_digest
                    and self._is_newer(receipt.release_version, record.release_version)
                ),
                key=lambda item: self._version_key(item.release_version),
                reverse=True,
            )
        )
        generated_at = self._clock()
        readiness = ConnectorUpgradeReadiness(
            schema_version=UPGRADE_READINESS_SCHEMA,
            source_record_id=record.record_id,
            source_record_version=record.version,
            instance_id=record.instance_id,
            instance_key=record.instance_key,
            connector_id=record.connector_id,
            current_release_version=record.release_version,
            current_package_digest=record.package_digest,
            current_manifest_digest=record.manifest_digest,
            current_receipt_id=current_receipt.receipt_id,
            current_receipt_digest=current_receipt.canonical_digest,
            target_configured=target is not None,
            candidates=candidates,
            generated_at=generated_at,
            canonical_digest="0" * 64,
        )
        readiness = replace(
            readiness,
            canonical_digest=self._digest(self._payload(readiness)),
        )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.upgrade-readiness",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=generated_at,
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=INSTANCE_READ_PERMISSION,
                resource_type="resource.connector.instance",
                scope_reference=record.instance_id,
                decision_id=None,
                outcome="succeeded",
                result_code="connector_upgrade_readiness_evaluated",
                idempotency_key=None,
                target_metadata=(("candidate_count", str(len(candidates))),),
            )
        )
        return readiness

    async def plan(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        candidate_receipt_id: str,
        correlation_id: str,
    ) -> ConnectorUpgradePlan:
        readiness = await self.evaluate(
            actor=actor,
            record_id=record_id,
            correlation_id=correlation_id,
        )
        candidate = next(
            (item for item in readiness.candidates if item.receipt_id == candidate_receipt_id),
            None,
        )
        if candidate is None:
            raise ConnectorInstanceCreationError("connector_upgrade_candidate_not_found")
        target = await self._target_repository.get_by_instance(source_instance_record_id=record_id)
        if (target is not None) != readiness.target_configured:
            raise ConnectorInstanceCreationError("connector_upgrade_plan_source_drift")
        target_configured = target is not None
        blockers = tuple(
            dict.fromkeys(
                (
                    *candidate.blockers,
                    *(("connector.upgrade.impact-evidence-required",) if target_configured else ()),
                )
            )
        )
        prerequisites = [
            "connector.upgrade.prerequisite.exact-lineage",
            "connector.upgrade.prerequisite.package-installed",
            "connector.upgrade.prerequisite.rollback-anchor",
            "connector.upgrade.prerequisite.human-approval",
        ]
        if candidate.policy_review_required:
            prerequisites.append("connector.upgrade.prerequisite.policy-review")
        if candidate.configuration_migration_required:
            prerequisites.append("connector.upgrade.prerequisite.configuration-runbook")
        if target_configured:
            prerequisites.append("connector.upgrade.prerequisite.impact-assessment")
        now = self._clock()
        steps = self._plan_steps(target_configured=target_configured)
        plan_seed = {
            "schema_version": UPGRADE_PLAN_SCHEMA,
            "source_record_id": readiness.source_record_id,
            "source_record_version": readiness.source_record_version,
            "readiness_digest": readiness.canonical_digest,
            "candidate_receipt_id": candidate.receipt_id,
            "candidate_digest": candidate.canonical_digest,
            "target_binding_digest": target.canonical_digest if target else None,
            "prerequisites": tuple(prerequisites),
            "steps": tuple(asdict(item) for item in steps),
            "blockers": blockers,
        }
        plan_digest = self._digest(plan_seed)
        plan = ConnectorUpgradePlan(
            plan_id=f"connector-upgrade-plan.{plan_digest[:24]}",
            schema_version=UPGRADE_PLAN_SCHEMA,
            source_record_id=readiness.source_record_id,
            source_record_version=readiness.source_record_version,
            instance_id=readiness.instance_id,
            connector_id=readiness.connector_id,
            current_release_version=readiness.current_release_version,
            current_receipt_id=readiness.current_receipt_id,
            current_receipt_digest=readiness.current_receipt_digest,
            candidate_release_version=candidate.release_version,
            candidate_receipt_id=candidate.receipt_id,
            candidate_receipt_digest=candidate.receipt_digest,
            readiness_digest=readiness.canonical_digest,
            candidate_digest=candidate.canonical_digest,
            risk_level=candidate.risk_level,
            target_configured=target_configured,
            target_id=target.target_id if target else None,
            site_id=target.site_id if target else None,
            target_product=target.target_product if target else None,
            plan_state="blocked" if blockers or target_configured else "ready_for_human_review",
            plan_eligible=not blockers and not target_configured,
            prerequisite_ids=tuple(prerequisites),
            steps=steps,
            validation_check_ids=(
                "connector.upgrade.verify.package-lineage",
                "connector.upgrade.verify.configuration-schema",
                "connector.upgrade.verify.capability-policy",
                "connector.upgrade.verify.target-connectivity",
                "connector.upgrade.verify.runtime-health",
                "connector.upgrade.verify.audit-completeness",
            ),
            stop_condition_ids=(
                "connector.upgrade.stop.source-drift",
                "connector.upgrade.stop.policy-rejected",
                "connector.upgrade.stop.impact-unknown",
                "connector.upgrade.stop.validation-failed",
                "connector.upgrade.stop.rollback-anchor-invalid",
            ),
            rollback_step_ids=(
                "connector.upgrade.rollback.quiesce-candidate",
                "connector.upgrade.rollback.restore-package-binding",
                "connector.upgrade.rollback.restore-configuration",
                "connector.upgrade.rollback.verify-source-release",
            ),
            blockers=blockers,
            unknowns=(
                (
                    "Current business-service impact, active sessions and approved maintenance "
                    "window are not established."
                ),
            )
            if target_configured
            else (),
            estimated_interruption_min_minutes=None if target_configured else 0,
            estimated_interruption_max_minutes=None if target_configured else 0,
            rollback_window_minutes=60,
            generated_at=now,
            expires_at=now + timedelta(hours=1),
            canonical_digest=plan_digest,
        )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.upgrade-plan",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=now,
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=INSTANCE_READ_PERMISSION,
                resource_type="resource.connector.instance",
                scope_reference=readiness.instance_id,
                decision_id=None,
                outcome="succeeded",
                result_code="connector_upgrade_plan_generated",
                idempotency_key=None,
                target_metadata=(
                    ("candidate_receipt_id", candidate.receipt_id),
                    ("plan_state", plan.plan_state),
                ),
            )
        )
        return plan

    @staticmethod
    def _plan_steps(*, target_configured: bool) -> tuple[ConnectorUpgradePlanStep, ...]:
        return (
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.obtain-approval", 1, "approval", 0, False, False
            ),
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.capture-baseline", 2, "precheck", 2, False, False
            ),
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.quiesce-sessions",
                3,
                "quiescence",
                2,
                target_configured,
                True,
            ),
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.bind-candidate-package",
                4,
                "package_binding",
                3,
                target_configured,
                True,
            ),
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.migrate-configuration",
                5,
                "configuration",
                4,
                target_configured,
                True,
            ),
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.verify-candidate", 6, "verification", 5, False, True
            ),
            ConnectorUpgradePlanStep(
                "connector.upgrade.step.confirm-rollback-gate",
                7,
                "rollback_gate",
                2,
                False,
                True,
            ),
        )

    def _candidate(
        self,
        *,
        current_receipt: ConnectorPackageInstallationReceipt,
        current_registration: ConnectorPackageRegistrationRecord,
        candidate_receipt: ConnectorPackageInstallationReceipt,
        candidate_registration: ConnectorPackageRegistrationRecord,
        target_configured: bool,
    ) -> ConnectorUpgradeCandidate:
        if (
            candidate_receipt.receipt_id == current_receipt.receipt_id
            or candidate_receipt.connector_id != current_receipt.connector_id
            or candidate_registration.record_id != candidate_receipt.source_registration_record_id
            or candidate_registration.canonical_digest
            != candidate_receipt.source_registration_record_digest
            or candidate_registration.manifest.manifest_digest != candidate_receipt.manifest_digest
            or candidate_registration.organization_id != candidate_receipt.organization_id
            or candidate_registration.environment_id != candidate_receipt.environment_id
            or candidate_registration.package_digest != candidate_receipt.package_digest
            or candidate_registration.connector_id != candidate_receipt.connector_id
            or candidate_registration.release_version != candidate_receipt.release_version
            or candidate_registration.publisher_id != candidate_receipt.publisher_id
            or candidate_registration.manifest.connector_id != candidate_receipt.connector_id
            or candidate_registration.manifest.release_version != candidate_receipt.release_version
            or candidate_registration.manifest.sdk_profile != candidate_receipt.sdk_profile
        ):
            raise ConnectorInstanceCreationError("connector_upgrade_candidate_binding_invalid")
        current_manifest = current_registration.manifest
        candidate_manifest = candidate_registration.manifest
        current_capabilities = {item.capability_id: item for item in current_manifest.capabilities}
        candidate_capabilities = {
            item.capability_id: item for item in candidate_manifest.capabilities
        }
        changes = []
        for capability_id in sorted(current_capabilities.keys() | candidate_capabilities.keys()):
            current = current_capabilities.get(capability_id)
            proposed = candidate_capabilities.get(capability_id)
            if current == proposed:
                continue
            changes.append(
                ConnectorCapabilityChange(
                    capability_id=capability_id,
                    change_type=(
                        "added" if current is None else "removed" if proposed is None else "changed"
                    ),
                    current_class=current.capability_class if current else None,
                    candidate_class=proposed.capability_class if proposed else None,
                    current_permission=current.required_permission if current else None,
                    candidate_permission=proposed.required_permission if proposed else None,
                )
            )
        target_added = tuple(
            sorted(set(candidate_manifest.target_products) - set(current_manifest.target_products))
        )
        target_removed = tuple(
            sorted(set(current_manifest.target_products) - set(candidate_manifest.target_products))
        )
        network_added = tuple(
            sorted(
                set(candidate_manifest.network_destinations)
                - set(current_manifest.network_destinations)
            )
        )
        network_removed = tuple(
            sorted(
                set(current_manifest.network_destinations)
                - set(candidate_manifest.network_destinations)
            )
        )
        configuration_delta = (
            candidate_manifest.configuration_key_count - current_manifest.configuration_key_count
        )
        secret_delta = (
            candidate_manifest.secret_reference_count - current_manifest.secret_reference_count
        )
        upgrade_class = self._upgrade_class(
            current_receipt.release_version, candidate_receipt.release_version
        )
        blockers = (
            ("connector.upgrade.publisher-changed",)
            if candidate_receipt.publisher_id != current_receipt.publisher_id
            else ()
        )
        sdk_changed = candidate_manifest.sdk_profile != current_manifest.sdk_profile
        if sdk_changed:
            blockers = (*blockers, "connector.upgrade.sdk-profile-changed")
        authority_changed = bool(
            changes or target_added or target_removed or network_added or network_removed
        )
        if blockers:
            risk_level = "critical"
        elif (
            upgrade_class == "major"
            or sdk_changed
            or network_added
            or secret_delta > 0
            or any(
                item.change_type == "added"
                or item.current_class != item.candidate_class
                or item.current_permission != item.candidate_permission
                for item in changes
            )
        ):
            risk_level = "high"
        elif (
            upgrade_class == "minor"
            or changes
            or target_added
            or target_removed
            or configuration_delta
            or secret_delta
        ):
            risk_level = "medium"
        else:
            risk_level = "low"
        candidate_record = ConnectorUpgradeCandidate(
            receipt_id=candidate_receipt.receipt_id,
            receipt_digest=candidate_receipt.canonical_digest,
            package_digest=candidate_receipt.package_digest,
            manifest_digest=candidate_receipt.manifest_digest,
            release_version=candidate_receipt.release_version,
            publisher_id=candidate_receipt.publisher_id,
            sdk_profile=candidate_receipt.sdk_profile,
            installed_at=candidate_receipt.installed_at,
            upgrade_class=upgrade_class,
            risk_level=risk_level,
            capability_changes=tuple(changes),
            target_products_added=target_added,
            target_products_removed=target_removed,
            network_destinations_added=network_added,
            network_destinations_removed=network_removed,
            configuration_key_delta=configuration_delta,
            secret_reference_delta=secret_delta,
            policy_review_required=(
                authority_changed or sdk_changed or configuration_delta != 0 or secret_delta != 0
            ),
            configuration_migration_required=target_configured or configuration_delta != 0,
            rollback_receipt_id=current_receipt.receipt_id,
            rollback_receipt_digest=current_receipt.canonical_digest,
            review_eligible=not blockers,
            blockers=blockers,
            canonical_digest="0" * 64,
        )
        return replace(
            candidate_record,
            canonical_digest=self._digest(self._payload(candidate_record)),
        )

    @staticmethod
    def _verify_current_binding(
        record: ConnectorInstanceRecord,
        receipt: ConnectorPackageInstallationReceipt,
        registration: ConnectorPackageRegistrationRecord,
    ) -> None:
        if (
            receipt.receipt_id != record.source_installation_receipt_id
            or receipt.canonical_digest != record.source_installation_receipt_digest
            or receipt.organization_id != record.organization_id
            or receipt.environment_id != record.environment_id
            or receipt.package_digest != record.package_digest
            or receipt.connector_id != record.connector_id
            or receipt.release_version != record.release_version
            or receipt.manifest_digest != record.manifest_digest
            or receipt.sdk_profile != record.sdk_profile
            or registration.record_id != receipt.source_registration_record_id
            or registration.canonical_digest != receipt.source_registration_record_digest
            or registration.organization_id != receipt.organization_id
            or registration.environment_id != receipt.environment_id
            or registration.package_digest != receipt.package_digest
            or registration.connector_id != receipt.connector_id
            or registration.release_version != receipt.release_version
            or registration.publisher_id != receipt.publisher_id
            or registration.manifest.connector_id != receipt.connector_id
            or registration.manifest.release_version != receipt.release_version
            or registration.manifest.manifest_digest != receipt.manifest_digest
            or registration.manifest.sdk_profile != receipt.sdk_profile
        ):
            raise ConnectorInstanceCreationError("connector_upgrade_source_binding_invalid")

    @classmethod
    def _upgrade_class(cls, current: str, candidate: str) -> str:
        current_key = cls._version_key(current)
        candidate_key = cls._version_key(candidate)
        if candidate_key[0] != current_key[0]:
            return "major"
        if candidate_key[1] != current_key[1]:
            return "minor"
        return "patch"

    @classmethod
    def _is_newer(cls, candidate: str, current: str) -> bool:
        return cls._version_key(candidate) > cls._version_key(current)

    @staticmethod
    def _version_key(value: str) -> tuple[int, int, int, int, tuple[tuple[int, object], ...]]:
        match = _SEMVER.fullmatch(value)
        if match is None:
            raise ConnectorInstanceCreationError("connector_upgrade_release_version_invalid")
        prerelease = match.group(4)
        identifiers: tuple[tuple[int, object], ...] = ()
        stable = 1
        if prerelease is not None:
            stable = 0
            identifiers = tuple(
                (0, int(item)) if item.isdigit() else (1, item) for item in prerelease.split(".")
            )
        return (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            stable,
            identifiers,
        )

    @classmethod
    def _payload(
        cls, value: ConnectorUpgradeCandidate | ConnectorUpgradeReadiness
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(value))
        payload.pop("canonical_digest")
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
            raise ConnectorInstanceCreationError(
                "connector_upgrade_readiness_enterprise_human_mfa_required"
            )
