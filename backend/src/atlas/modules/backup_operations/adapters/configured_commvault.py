from __future__ import annotations

import hashlib
from datetime import datetime

from atlas.modules.backup_operations.domain.models import (
    BackupFinding,
    BackupInvestigation,
    BackupOverview,
    BackupProtectedClient,
    BackupReport,
    BackupStoragePolicy,
    EvidenceRecord,
    FindingSeverity,
    FreshnessState,
    InvestigationState,
)
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    CommvaultConnectionTestTransportFactory,
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.commvault.client import (
    CommvaultClient,
    CommvaultConnectorError,
)
from atlas.modules.connectors.vendors.commvault.domain import (
    CommvaultClientListResult,
    CommvaultStoragePolicyListResult,
)
from atlas.modules.connectors.vendors.commvault.manifest import PACKAGE_ID
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

_DATA_PROFILE = "configured_commvault_read_only"
_SAFETY_NOTICE = (
    "Decision support only. No infrastructure change or service-impacting action is authorized."
)
_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "malformed_vendor_response",
        "target_timeout",
        "target_unavailable",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)


def _connector_failure_reason(exc: CommvaultConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Commvault read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredCommvaultBackupOverviewProvider:
    """Serves the backup overview from the single configured, enabled Commvault MCP, reading real
    client and storage-policy inventory. No recovery-point/browse catalog is represented: no
    confirmed real JSON response shape for Commvault's Browse API was found during construction
    (unlike Job/Client/StoragePolicy, which each have a literal confirmed example response) --
    stated plainly rather than guessed. See ATLAS-IMP-269.
    """

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: CommvaultConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
        target_id: str = "target.commvault.commserve.configured",
        connector_version: str = "0.1.0",
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._configuration_repository = configuration_repository
        self._instance_repository = instance_repository
        self._inventory_repository = inventory_repository
        self._credential_materializer = credential_materializer
        self._transport_factory = transport_factory
        self._organization_id = organization_id
        self._environment_id = environment_id
        self._site_id = site_id
        self._target_id = target_id
        self._connector_version = connector_version
        self._runtime_state_repository = runtime_state_repository
        self._timeout_seconds = timeout_seconds

    async def get_overview(self, *, requested_at: datetime) -> BackupOverview:
        configuration = await self._single_active_configuration()
        if configuration is None:
            return self._unavailable_overview(
                requested_at,
                reason="A single active configured Commvault MCP is required to read "
                "client and storage-policy inventory.",
            )
        if self._runtime_state_repository is not None:
            runtime_state = await self._runtime_state_repository.get(
                organization_id=self._organization_id,
                environment_id=self._environment_id,
                instance_id=configuration.instance_id,
            )
            if (
                runtime_state is None
                or runtime_state.state != ENABLED_READ_ONLY
                or runtime_state.configuration_id != configuration.configuration_id
            ):
                return self._unavailable_overview(
                    requested_at,
                    reason="The configured Commvault MCP must be enabled for read-only "
                    "inventory polling.",
                )
        if not await self._commvault_is_allowlisted():
            return self._unavailable_overview(
                requested_at, reason="No active Commvault CommServe is allowlisted in inventory."
            )

        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(self._timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    trust_profile_id=configuration.trust_profile_id,
                    credential_provider=lease.authorization_header,
                    timeout_seconds=self._timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = CommvaultClient(transport=transport, maximum_response_bytes=1_048_576)
                clients = await client.read_client_inventory()
                policies = await client.read_storage_policies()
        except ConnectorConnectionTestError:
            return self._unavailable_overview(
                requested_at,
                reason="The Commvault credential reference is unavailable for this backup read.",
            )
        except CommvaultConnectorError as exc:
            return self._unavailable_overview(requested_at, reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_overview(
                requested_at, reason="The configured Commvault backup read failed safely."
            )

        return self._build_overview(clients=clients, policies=policies, requested_at=requested_at)

    def _build_overview(
        self,
        *,
        clients: CommvaultClientListResult,
        policies: CommvaultStoragePolicyListResult,
        requested_at: datetime,
    ) -> BackupOverview:
        client_evidence = EvidenceRecord(
            reference=f"evidence.backup.client.{_identity(clients.evidence_references[0])}",
            source="Commvault client-inventory read",
            source_version=self._connector_version,
            observed_at=clients.observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis=(
                "Digest-only evidence from an allowlisted C1 REST API response "
                f"({clients.evidence_references[0]})"
            ),
        )
        policy_evidence = EvidenceRecord(
            reference=f"evidence.backup.policy.{_identity(policies.evidence_references[0])}",
            source="Commvault storage-policy-inventory read",
            source_version=self._connector_version,
            observed_at=policies.observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis=(
                "Digest-only evidence from an allowlisted C1 REST API response "
                f"({policies.evidence_references[0]})"
            ),
        )
        evidence = (client_evidence, policy_evidence)

        backup_clients = tuple(
            BackupProtectedClient(
                client_id=item.client_id,
                client_name=item.client_name,
                host_name=item.host_name,
                os_type=item.os_type,
                is_deleted=item.is_deleted,
                observed_at=clients.observed_at,
                evidence_references=(client_evidence.reference,),
            )
            for item in clients.clients
        )
        backup_policies = tuple(
            BackupStoragePolicy(
                policy_id=item.policy_id,
                policy_name=item.policy_name,
                number_of_copies=item.number_of_copies,
                number_of_streams=item.number_of_streams,
                observed_at=policies.observed_at,
                evidence_references=(policy_evidence.reference,),
            )
            for item in policies.policies
        )

        findings: list[BackupFinding] = []
        for record in backup_clients:
            if not record.is_deleted:
                continue
            findings.append(
                BackupFinding(
                    finding_id=f"finding.backup.client.{_identity(record.client_id)}",
                    subject_id=f"client.{record.client_id}",
                    severity=FindingSeverity.WARNING,
                    component=f"client:{record.client_name}",
                    summary=(
                        f"Protected client {record.client_name} is marked deleted in Commvault."
                    ),
                    observed_at=clients.observed_at,
                    evidence_references=(client_evidence.reference,),
                )
            )
        for policy in backup_policies:
            if policy.number_of_copies != 0:
                continue
            findings.append(
                BackupFinding(
                    finding_id=f"finding.backup.policy.{_identity(policy.policy_id)}",
                    subject_id=f"policy.{policy.policy_id}",
                    severity=FindingSeverity.WARNING,
                    component=f"policy:{policy.policy_name}",
                    summary=(
                        f"Storage policy {policy.policy_name} retains zero copies of "
                        "backed-up data."
                    ),
                    observed_at=policies.observed_at,
                    evidence_references=(policy_evidence.reference,),
                )
            )

        unknowns = (
            "No recovery-point/browse catalog is represented: no confirmed real API response "
            "shape was found for Commvault's Browse operation during construction.",
            "No job-outcome correlation is made here; job status is a separate, already-real "
            "health_checks signal (see health_checks/adapters/commvault.py).",
        )
        if findings:
            summary = (
                f"{len(findings)} protection-coverage finding(s) were observed across "
                f"{len(backup_clients)} client(s) and {len(backup_policies)} storage "
                "policy(ies) in this scope."
            )
        else:
            summary = (
                f"No protection-coverage findings were observed across {len(backup_clients)} "
                f"client(s) and {len(backup_policies)} storage policy(ies) in this scope."
            )
        investigation_evidence = tuple(item.reference for item in evidence)
        investigation = BackupInvestigation(
            investigation_id=f"investigation.backup.{_identity(str(requested_at))}",
            title="Configured Commvault protection coverage read",
            state=InvestigationState.PROVISIONAL,
            summary=summary,
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Repeat the read-only client and storage-policy inventory to confirm "
                "persistence of any open finding.",
                "Review recent job history for any client or policy with an open finding.",
            ),
            evidence_references=investigation_evidence,
            updated_at=requested_at,
        )
        confirmed_facts = (
            f"{len(backup_clients)} registered client(s) were read via the configured connector.",
            f"{len(backup_policies)} storage polic(y/ies) were read via the configured connector.",
            f"{len(findings)} finding(s) were observed."
            if findings
            else "No deleted clients or zero-copy policies were observed.",
        )
        report = BackupReport(
            report_id=f"report.backup.{_identity(str(requested_at))}",
            title="Configured Commvault protection coverage assessment",
            generated_at=requested_at,
            executive_summary=summary,
            confirmed_facts=confirmed_facts,
            provisional_findings=tuple(finding.summary for finding in findings),
            unknowns=unknowns,
            evidence_references=investigation_evidence,
            safety_notice=_SAFETY_NOTICE,
        )

        return BackupOverview(
            snapshot_id=f"snapshot.backup.{_identity(str(requested_at))}",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            target_id=self._target_id,
            data_profile=_DATA_PROFILE,
            generated_at=requested_at,
            clients=backup_clients,
            policies=backup_policies,
            findings=tuple(findings),
            evidence=evidence,
            investigation=investigation,
            report=report,
        )

    def _unavailable_overview(self, requested_at: datetime, *, reason: str) -> BackupOverview:
        meta_reference = (
            f"atlas-config://{self._organization_id}/{self._environment_id}"
            f"#{_identity(reason, requested_at.isoformat())}"
        )
        evidence = (
            EvidenceRecord(
                reference=meta_reference,
                source="Atlas connector configuration and inventory state",
                source_version=self._connector_version,
                observed_at=requested_at,
                freshness=FreshnessState.UNKNOWN,
                trust_basis=(
                    "Live query of Atlas connector configuration, runtime state, and "
                    "inventory repositories"
                ),
            ),
        )
        unknowns = (
            reason,
            "Backup protection coverage is unknown because no read-only Commvault connector "
            "read completed.",
        )
        investigation = BackupInvestigation(
            investigation_id=f"investigation.backup.{_identity(reason, str(requested_at))}",
            title="Configured Commvault protection coverage read",
            state=InvestigationState.INCONCLUSIVE,
            summary=(
                "Client and storage-policy inventory could not be read from the configured "
                f"Commvault connector: {reason}"
            ),
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Configure and enable exactly one read-only Commvault connector instance for "
                "this environment.",
                "Allowlist an active Commvault CommServe device in inventory.",
            ),
            evidence_references=(meta_reference,),
            updated_at=requested_at,
        )
        report = BackupReport(
            report_id=f"report.backup.{_identity(reason, str(requested_at))}",
            title="Configured Commvault protection coverage assessment",
            generated_at=requested_at,
            executive_summary=investigation.summary,
            confirmed_facts=(),
            provisional_findings=(),
            unknowns=unknowns,
            evidence_references=(meta_reference,),
            safety_notice=_SAFETY_NOTICE,
        )
        return BackupOverview(
            snapshot_id=f"snapshot.backup.{_identity(reason, str(requested_at))}",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            target_id=self._target_id,
            data_profile=_DATA_PROFILE,
            generated_at=requested_at,
            clients=(),
            policies=(),
            findings=(),
            evidence=evidence,
            investigation=investigation,
            report=report,
        )

    async def _single_active_configuration(self) -> BundledConnectionConfiguration | None:
        instances = await self._instance_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
        )
        active_ids = {
            instance.instance_id
            for instance in instances
            if instance.connector_id == PACKAGE_ID
            and instance.instance_state == DISABLED_UNCONFIGURED
        }
        configurations = await self._configuration_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
        )
        candidates = tuple(
            item
            for item in configurations
            if item.connector_id == PACKAGE_ID and item.instance_id in active_ids
        )
        return candidates[0] if len(candidates) == 1 else None

    async def _commvault_is_allowlisted(self) -> bool:
        devices = await self._inventory_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            query=None,
            limit=500,
        )
        return any(
            device.device_type is InventoryDeviceType.BACKUP
            and "commvault" in device.vendor.lower()
            for device in devices
        )
