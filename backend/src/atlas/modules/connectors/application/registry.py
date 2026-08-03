from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.capabilities import FOUNDATION_CAPABILITY_CLASSES, CapabilityClass
from atlas.modules.connectors.application.ports import (
    ConnectorRegistryRepository,
    ConnectorSelfTester,
)
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorHealth,
    ConnectorInstance,
    ConnectorPackageManifest,
    ConnectorValidationReport,
    InstanceLifecycle,
    PackageLifecycle,
    RegisteredPackage,
    SideEffect,
    ValidationFinding,
)

PACKAGE_REGISTER = "connectors.packages.register"
PACKAGE_READ = "connectors.packages.read"
INSTANCE_MANAGE = "connectors.instances.manage"
INSTANCE_READ = "connectors.instances.read"
CAPABILITY_DISCOVER = "connectors.capabilities.discover"


@dataclass(frozen=True, slots=True)
class ConnectorAccessContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    correlation_id: str
    permissions: frozenset[str]


class ConnectorRegistryError(Exception):
    def __init__(
        self,
        code: str,
        detail: str,
        *,
        validation_report: ConnectorValidationReport | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.validation_report = validation_report


class FoundationConnectorValidator:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def validate(self, manifest: ConnectorPackageManifest) -> ConnectorValidationReport:
        findings: list[ValidationFinding] = []
        for index, capability in enumerate(manifest.capabilities):
            path = f"/capabilities/{index}"
            if capability.capability_class not in FOUNDATION_CAPABILITY_CLASSES:
                findings.append(
                    ValidationFinding(
                        code="unsupported_capability_class",
                        path=f"{path}/capability_class",
                        message="The foundation registry accepts only C0 and C1 capabilities.",
                    )
                )
            findings.extend(self._validate_side_effects(capability, path))

        if manifest.runtime == "simulator" and manifest.network_destinations:
            findings.append(
                ValidationFinding(
                    code="simulator_network_access_forbidden",
                    path="/network_destinations",
                    message="Simulator packages cannot declare network destinations.",
                )
            )

        return ConnectorValidationReport(
            report_id=f"report.{uuid4().hex}",
            package_reference=manifest.version_reference,
            validated_at=self._clock(),
            findings=tuple(findings),
        )

    @staticmethod
    def _validate_side_effects(
        capability: CapabilityManifest, path: str
    ) -> tuple[ValidationFinding, ...]:
        if capability.capability_class is CapabilityClass.C0_INFORMATIONAL:
            allowed = frozenset({SideEffect.NONE})
        elif capability.capability_class is CapabilityClass.C1_READ_ONLY:
            allowed = frozenset({SideEffect.READ})
        else:
            return ()
        if capability.side_effects <= allowed:
            return ()
        return (
            ValidationFinding(
                code="capability_side_effect_mismatch",
                path=f"{path}/side_effects",
                message=(
                    f"{capability.capability_class.value} capability side effects exceed the "
                    "foundation safety boundary."
                ),
            ),
        )


class ConnectorRegistryService:
    def __init__(
        self,
        *,
        repository: ConnectorRegistryRepository,
        audit_sink: AuditSink,
        validator: FoundationConnectorValidator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        self._validator = validator or FoundationConnectorValidator(self._clock)
        self._mutation_lock = asyncio.Lock()

    async def register_package(
        self, manifest: ConnectorPackageManifest, context: ConnectorAccessContext
    ) -> RegisteredPackage:
        self._require_permission(context, PACKAGE_REGISTER)
        report = self._validator.validate(manifest)
        if not report.passed:
            await self._audit(
                context=context,
                event_type="atlas.connector.package.validation_failed",
                permission_id=PACKAGE_REGISTER,
                resource_type="resource.connector.package",
                scope_reference=manifest.version_reference,
                outcome="failed",
                result_code="connector_validation_failed",
            )
            raise ConnectorRegistryError(
                "connector_validation_failed",
                "Connector package validation failed; inspect the validation report.",
                validation_report=report,
            )

        async with self._mutation_lock:
            existing = await self._repository.get_package(
                manifest.package_id, manifest.package_version
            )
            if existing is not None:
                if existing.manifest.digest_sha256 == manifest.digest_sha256:
                    return existing
                raise ConnectorRegistryError(
                    "package_version_conflict",
                    "The package version is already registered with a different digest.",
                )

            lifecycle = (
                PackageLifecycle.QUARANTINED if manifest.generated else PackageLifecycle.REGISTERED
            )
            package = RegisteredPackage(
                manifest=manifest,
                lifecycle=lifecycle,
                registered_at=self._clock(),
                registered_by=context.subject_id,
                validation_report=report,
            )
            await self._audit(
                context=context,
                event_type=(
                    "atlas.connector.package.quarantined"
                    if lifecycle is PackageLifecycle.QUARANTINED
                    else "atlas.connector.package.registered"
                ),
                permission_id=PACKAGE_REGISTER,
                resource_type="resource.connector.package",
                scope_reference=manifest.version_reference,
                outcome="succeeded",
                result_code=(
                    "generated_package_quarantined"
                    if lifecycle is PackageLifecycle.QUARANTINED
                    else "package_registered"
                ),
            )
            await self._repository.add_package(package)
            return package

    async def list_packages(self, context: ConnectorAccessContext) -> tuple[RegisteredPackage, ...]:
        self._require_permission(context, PACKAGE_READ)
        return await self._repository.list_packages()

    async def create_instance(
        self,
        *,
        instance_id: str,
        package_id: str,
        package_version: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        target_id: str,
        enabled_capability_ids: frozenset[str],
        secret_reference_ids: tuple[str, ...],
        context: ConnectorAccessContext,
    ) -> ConnectorInstance:
        self._require_permission(context, INSTANCE_MANAGE)
        self._require_organization(context, organization_id)
        self._require_instance_scope(
            context,
            environment_id=environment_id,
            site_id=site_id,
            target_id=target_id,
        )

        async with self._mutation_lock:
            if await self._repository.get_instance(instance_id) is not None:
                raise ConnectorRegistryError(
                    "instance_conflict", "The connector instance identifier already exists."
                )
            package = await self._required_package(package_id, package_version)
            if package.lifecycle is not PackageLifecycle.REGISTERED:
                raise ConnectorRegistryError(
                    "package_not_approved",
                    "Connector instances can be created only from approved registered packages.",
                )
            declared = {item.capability_id for item in package.manifest.capabilities}
            if not enabled_capability_ids or not enabled_capability_ids <= declared:
                raise ConnectorRegistryError(
                    "invalid_capability_selection",
                    "Enabled capabilities must be a non-empty subset of the package manifest.",
                )
            if package.manifest.runtime == "simulator" and secret_reference_ids:
                raise ConnectorRegistryError(
                    "simulator_secret_reference_forbidden",
                    "Simulator instances cannot receive secret references.",
                )

            instance = ConnectorInstance(
                instance_id=instance_id,
                package_id=package_id,
                package_version=package_version,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                target_id=target_id,
                enabled_capability_ids=enabled_capability_ids,
                secret_reference_ids=secret_reference_ids,
                lifecycle=InstanceLifecycle.DISABLED,
                health=ConnectorHealth.UNKNOWN,
                configuration_revision=1,
                created_at=self._clock(),
                created_by=context.subject_id,
            )
            await self._audit(
                context=context,
                event_type="atlas.connector.instance.created",
                permission_id=INSTANCE_MANAGE,
                resource_type="resource.connector.instance",
                scope_reference=instance.instance_id,
                outcome="succeeded",
                result_code="instance_created_disabled",
            )
            await self._repository.add_instance(instance)
            return instance

    async def list_instances(
        self, context: ConnectorAccessContext
    ) -> tuple[ConnectorInstance, ...]:
        self._require_permission(context, INSTANCE_READ)
        instances = await self._repository.list_instances()
        visible = tuple(
            instance
            for instance in instances
            if (
                instance.organization_id,
                instance.environment_id,
                instance.site_id,
                instance.target_id,
            )
            == (
                context.organization_id,
                context.environment_id,
                context.site_id,
                context.target_id,
            )
        )
        await self._audit(
            context=context,
            event_type="atlas.connector.instances.listed",
            permission_id=INSTANCE_READ,
            resource_type="resource.connector.instance",
            scope_reference="/".join(
                (
                    context.organization_id,
                    context.environment_id,
                    context.site_id,
                    context.target_id,
                )
            ),
            outcome="succeeded",
            result_code="instances_listed",
        )
        return visible

    async def enable_instance(
        self,
        instance_id: str,
        self_tester: ConnectorSelfTester,
        context: ConnectorAccessContext,
    ) -> ConnectorInstance:
        self._require_permission(context, INSTANCE_MANAGE)
        instance = await self._required_instance(instance_id)
        self._require_organization(context, instance.organization_id)
        self._require_instance_scope(
            context,
            environment_id=instance.environment_id,
            site_id=instance.site_id,
            target_id=instance.target_id,
        )
        self_test = await self_tester.self_test(instance)
        if not self_test.passed:
            await self._audit(
                context=context,
                event_type="atlas.connector.instance.enablement_failed",
                permission_id=INSTANCE_MANAGE,
                resource_type="resource.connector.instance",
                scope_reference=instance.instance_id,
                outcome="failed",
                result_code=self_test.code,
            )
            raise ConnectorRegistryError(
                "self_test_failed",
                "A healthy connector self-test is required before enablement.",
            )

        async with self._mutation_lock:
            current = await self._required_instance(instance_id)
            if current.configuration_revision != instance.configuration_revision:
                await self._audit(
                    context=context,
                    event_type="atlas.connector.instance.enablement_failed",
                    permission_id=INSTANCE_MANAGE,
                    resource_type="resource.connector.instance",
                    scope_reference=current.instance_id,
                    outcome="failed",
                    result_code="instance_changed_during_self_test",
                )
                raise ConnectorRegistryError(
                    "instance_changed_during_self_test",
                    "The connector instance changed while its self-test was running.",
                )
            enabled = replace(
                current,
                lifecycle=InstanceLifecycle.ENABLED,
                health=self_test.health,
                configuration_revision=current.configuration_revision + 1,
            )
            await self._audit(
                context=context,
                event_type="atlas.connector.instance.enabled",
                permission_id=INSTANCE_MANAGE,
                resource_type="resource.connector.instance",
                scope_reference=current.instance_id,
                outcome="succeeded",
                result_code=self_test.code,
            )
            await self._repository.replace_instance(enabled)
            return enabled

    async def discover_capabilities(
        self, instance_id: str, context: ConnectorAccessContext
    ) -> tuple[CapabilityManifest, ...]:
        self._require_permission(context, CAPABILITY_DISCOVER)
        instance = await self._required_instance(instance_id)
        self._require_organization(context, instance.organization_id)
        self._require_instance_scope(
            context,
            environment_id=instance.environment_id,
            site_id=instance.site_id,
            target_id=instance.target_id,
        )
        if instance.lifecycle is not InstanceLifecycle.ENABLED:
            raise ConnectorRegistryError(
                "instance_not_enabled", "Capabilities are hidden until the instance is enabled."
            )
        package = await self._required_package(instance.package_id, instance.package_version)
        if package.lifecycle is not PackageLifecycle.REGISTERED:
            raise ConnectorRegistryError(
                "package_not_available", "The connector package is not available for discovery."
            )
        capabilities = tuple(
            item
            for item in package.manifest.capabilities
            if item.capability_id in instance.enabled_capability_ids
            and item.capability_class in FOUNDATION_CAPABILITY_CLASSES
        )
        await self._audit(
            context=context,
            event_type="atlas.connector.capabilities.discovered",
            permission_id=CAPABILITY_DISCOVER,
            resource_type="resource.connector.instance",
            scope_reference=instance.instance_id,
            outcome="succeeded",
            result_code="capabilities_discovered",
        )
        return capabilities

    async def _required_package(self, package_id: str, package_version: str) -> RegisteredPackage:
        package = await self._repository.get_package(package_id, package_version)
        if package is None:
            raise ConnectorRegistryError("package_not_found", "Connector package was not found.")
        return package

    async def _required_instance(self, instance_id: str) -> ConnectorInstance:
        instance = await self._repository.get_instance(instance_id)
        if instance is None:
            raise ConnectorRegistryError("instance_not_found", "Connector instance was not found.")
        return instance

    @staticmethod
    def _require_permission(context: ConnectorAccessContext, permission_id: str) -> None:
        if permission_id not in context.permissions:
            raise ConnectorRegistryError(
                "authorization_denied", "The current subject is not authorized for this operation."
            )

    @staticmethod
    def _require_organization(context: ConnectorAccessContext, organization_id: str) -> None:
        if context.organization_id != organization_id:
            raise ConnectorRegistryError(
                "organization_scope_mismatch",
                "The requested connector resource is outside the current organization scope.",
            )

    @staticmethod
    def _require_instance_scope(
        context: ConnectorAccessContext,
        *,
        environment_id: str,
        site_id: str,
        target_id: str,
    ) -> None:
        if (
            context.environment_id,
            context.site_id,
            context.target_id,
        ) != (environment_id, site_id, target_id):
            raise ConnectorRegistryError(
                "connector_scope_mismatch",
                "The requested connector resource is outside the authorized target scope.",
            )

    async def _audit(
        self,
        *,
        context: ConnectorAccessContext,
        event_type: str,
        permission_id: str,
        resource_type: str,
        scope_reference: str,
        outcome: str,
        result_code: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id=permission_id,
                resource_type=resource_type,
                scope_reference=scope_reference,
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
            )
        )
