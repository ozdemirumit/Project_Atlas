from __future__ import annotations

import hashlib
import re
from datetime import datetime

from atlas.core.classification import DataClassification
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
    HitachiConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.hitachi_ops_center.client import (
    HitachiConnectorError,
    HitachiOpsCenterClient,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.domain import (
    HealthSeverity,
    HitachiComponentHealth,
    HitachiHealthResult,
    HitachiInventoryResult,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType
from atlas.modules.investigations.domain.models import EvidenceUnit, FreshnessState, TimelineEvent
from atlas.modules.rca.domain.models import (
    CauseType,
    ConfirmationLevel,
    DiagnosticStep,
    HumanReview,
    ImpactScope,
    IncidentReference,
    NormalizedSymptom,
    ProvisionalCauseStatement,
    RcaCase,
    RcaCaseState,
    RcaCreateRequest,
    RcaFinding,
    RcaHypothesis,
    RcaSeverity,
    ReviewStatus,
)

FAULT_FAMILIES = (
    "storage_controller_or_path_degradation",
    "transient_or_observation_source_failure",
)
SAFETY_NOTICE = (
    "Decision support only. This provisional RCA does not confirm root cause, service impact, or "
    "remediation readiness and cannot authorize or execute an infrastructure change."
)
_DATA_PROFILE = "configured_hitachi_read_only"
_MAX_ALLOWED_STORAGE_TARGETS = 25
_TARGET_PREFIX = "asset.storage."
_STORAGE_DEVICE_ID = re.compile(r"^[A-Za-z0-9]{6,32}$")
_RCA_SEVERITY: dict[HealthSeverity, RcaSeverity] = {
    HealthSeverity.CRITICAL: RcaSeverity.CRITICAL,
    HealthSeverity.DEGRADED: RcaSeverity.WARNING,
    HealthSeverity.WARNING: RcaSeverity.WARNING,
    HealthSeverity.UNKNOWN: RcaSeverity.UNKNOWN,
}


def _identity(*parts: str) -> str:
    # Matches atlas.modules.storage.adapters.configured_hitachi._identity exactly, so an RCA
    # target_id agrees with the same real storage system's asset_id and graph entity_id.
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredHitachiRcaAssembler:
    """Builds a provisional RCA case from a real, single, current Hitachi hardware-health read.

    Keeps the two expert-authored fault-family hypothesis templates (controller/path degradation;
    transient or observation-source failure) and their governed C1 diagnostic-step recommendations
    unchanged -- those are domain reasoning content, not data, and this connector has no real
    hypothesis-ranking engine to substitute. What becomes real is the target, component, severity,
    and evidence the templates are populated with. See ATLAS-IMP-258.
    """

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: HitachiConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
        connector_version: str = "0.1.0",
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
        max_targets: int = _MAX_ALLOWED_STORAGE_TARGETS,
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
        self._connector_version = connector_version
        self._runtime_state_repository = runtime_state_repository
        self._max_targets = max_targets
        self._timeout_seconds = timeout_seconds

    async def build(
        self,
        request: RcaCreateRequest,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> RcaCase:
        configuration = await self._single_active_configuration()
        if configuration is None:
            raise KeyError(request.target_id)
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
                raise KeyError(request.target_id)
        storage_ids = await self._allowed_storage_ids()
        if not storage_ids:
            raise KeyError(request.target_id)
        storage_device_id = self._resolve_storage_device_id(request.target_id, storage_ids)
        if storage_device_id is None:
            raise KeyError(request.target_id)

        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(self._timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    trust_profile_id=configuration.trust_profile_id,
                    authorization_header_provider=lease.authorization_header,
                    timeout_seconds=self._timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = HitachiOpsCenterClient(
                    transport=transport,
                    allowed_storage_device_ids=frozenset({storage_device_id}),
                    maximum_arrays=500,
                    maximum_components=5_000,
                    maximum_response_bytes=1_048_576,
                )
                inventory = await client.read_inventory()
                health = await client.read_hardware_health(storage_device_id)
        except (ConnectorConnectionTestError, HitachiConnectorError, TimeoutError, ValueError) as exc:
            raise KeyError(request.target_id) from exc

        model = next(
            (array.model for array in inventory.arrays if array.storage_device_id == storage_device_id),
            "unknown model",
        )
        return self._assemble_case(
            request=request,
            requested_by=requested_by,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            created_at=created_at,
            version=version,
            prior_version_id=prior_version_id,
            model=model,
            inventory=inventory,
            health=health,
        )

    def _resolve_storage_device_id(
        self, target_id: str, storage_ids: frozenset[str]
    ) -> str | None:
        if not target_id.startswith(_TARGET_PREFIX):
            return None
        suffix = target_id[len(_TARGET_PREFIX) :]
        return next(
            (storage_id for storage_id in storage_ids if _identity(storage_id) == suffix),
            None,
        )

    def _assemble_case(
        self,
        *,
        request: RcaCreateRequest,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
        model: str,
        inventory: HitachiInventoryResult,
        health: HitachiHealthResult,
    ) -> RcaCase:
        authorization_reference = "/".join(
            (organization_id, environment_id, site_id, request.target_id)
        )
        health_evidence = EvidenceUnit(
            evidence_id=f"evidence.rca.health.{_identity(request.target_id, str(health.observed_at))}",
            artifact_version="1",
            source_type="storage_hardware_health",
            source_system="Hitachi Ops Center",
            source_version=self._connector_version,
            target_id=request.target_id,
            observed_at=health.observed_at,
            applicable_from=health.observed_at,
            applicable_to=None,
            freshness=FreshnessState.CURRENT,
            classification=DataClassification.INTERNAL,
            authorization_reference=authorization_reference,
            collection_method="Hitachi Ops Center allowlisted C1 hardware-health read",
            summary=(
                f"{model} reported overall severity '{health.overall_severity.value}' across "
                f"{len(health.components)} observed component(s)."
            ),
            integrity="Digest-only evidence from an allowlisted C1 HTTPS GET response",
            completeness="A single current read; no repeat read or historical trend is included.",
            quality_limitations=(
                "No repeat read was performed to confirm persistence.",
                "No path, event-log, fabric, or peer-array evidence is included.",
            ),
            citation=f"Hitachi Ops Center hardware-health read for {model}.",
        )
        inventory_evidence = EvidenceUnit(
            evidence_id=f"evidence.rca.inventory.{_identity(request.target_id, str(inventory.observed_at))}",
            artifact_version="1",
            source_type="storage_inventory",
            source_system="Hitachi Ops Center",
            source_version=self._connector_version,
            target_id=request.target_id,
            observed_at=inventory.observed_at,
            applicable_from=inventory.observed_at,
            applicable_to=None,
            freshness=FreshnessState.CURRENT,
            classification=DataClassification.INTERNAL,
            authorization_reference=authorization_reference,
            collection_method="Hitachi Ops Center allowlisted C1 inventory read",
            summary=f"Confirmed the identity and model ({model}) of the requested storage system.",
            integrity="Digest-only evidence from an allowlisted C1 HTTPS GET response",
            completeness="Array identity only; no capacity or configuration detail is included.",
            quality_limitations=(),
            citation=f"Hitachi Ops Center inventory read confirming {model}.",
        )
        timeline = (
            TimelineEvent(
                event_id=f"timeline.rca.{_identity(request.target_id, str(health.observed_at))}",
                event_type="storage_hardware_health_read",
                summary=health_evidence.summary,
                occurred_at=health.observed_at,
                observed_at=health.observed_at,
                ingested_at=health.observed_at,
                evidence_references=(health_evidence.evidence_id,),
                clock_quality="connector-reported, not independently synchronized",
            ),
        )
        non_normal = tuple(
            component for component in health.components if component.severity is not HealthSeverity.NORMAL
        )
        evidence = (health_evidence, inventory_evidence)

        if not non_normal:
            return self._no_active_finding_case(
                request=request,
                requested_by=requested_by,
                organization_id=organization_id,
                environment_id=environment_id,
                site_id=site_id,
                created_at=created_at,
                version=version,
                prior_version_id=prior_version_id,
                evidence=evidence,
                timeline=timeline,
                health_evidence_id=health_evidence.evidence_id,
            )

        component = self._worst_component(non_normal)
        return self._active_finding_case(
            request=request,
            requested_by=requested_by,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            created_at=created_at,
            version=version,
            prior_version_id=prior_version_id,
            model=model,
            component=component,
            evidence=evidence,
            timeline=timeline,
            health_evidence_id=health_evidence.evidence_id,
        )

    @staticmethod
    def _worst_component(components: tuple[HitachiComponentHealth, ...]) -> HitachiComponentHealth:
        rank = {
            HealthSeverity.CRITICAL: 0,
            HealthSeverity.DEGRADED: 1,
            HealthSeverity.WARNING: 2,
            HealthSeverity.UNKNOWN: 3,
        }
        return min(components, key=lambda item: rank.get(item.severity, 4))

    def _active_finding_case(
        self,
        *,
        request: RcaCreateRequest,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
        model: str,
        component: HitachiComponentHealth,
        evidence: tuple[EvidenceUnit, ...],
        timeline: tuple[TimelineEvent, ...],
        health_evidence_id: str,
    ) -> RcaCase:
        component_label = f"{component.category}:{component.location}"
        severity = _RCA_SEVERITY.get(component.severity, RcaSeverity.UNKNOWN)
        path_step = self._diagnostic_step(
            step_id="diagnostic.path-events",
            question="Is the warning reproduced by current path or event evidence?",
            target_id=request.target_id,
            capability_id="hitachi.opscenter.storage.path-events.read",
            evidence_source="Hitachi Ops Center allowlisted read-only capability",
            expected_if_supported="Repeated path errors or degraded path state are present.",
            expected_if_not_supported="No related current path error or event sequence is present.",
            supported_branch="Increase support for controller or path degradation.",
            unsupported_branch="Weaken degradation and evaluate observation failure.",
            timeout_seconds=30,
            max_output_records=20,
        )
        service_step = self._diagnostic_step(
            step_id="diagnostic.service-telemetry",
            question="Does authorized service telemetry align with the warning window?",
            target_id=request.target_id,
            capability_id="atlas.telemetry.service-health.read",
            evidence_source="Atlas authorized service telemetry projection",
            expected_if_supported="A scoped latency or availability symptom aligns with the window.",
            expected_if_not_supported="No scoped service symptom is observed in the same window.",
            supported_branch="Retain possible impact and continue dependency validation.",
            unsupported_branch="Do not infer service impact from graph reachability.",
            timeout_seconds=20,
            max_output_records=12,
        )
        repeat_step = self._diagnostic_step(
            step_id="diagnostic.repeat-health",
            question="Does a repeat bounded health read reproduce the warning?",
            target_id=request.target_id,
            capability_id="hitachi.opscenter.storage.hardware.read",
            evidence_source="Hitachi Ops Center allowlisted hardware-health capability",
            expected_if_supported="The same scoped component warning is reproduced.",
            expected_if_not_supported="The warning is absent from the repeat read.",
            supported_branch="Weaken transient observation failure.",
            unsupported_branch="Increase support for transient or observation-source failure.",
            timeout_seconds=15,
            max_output_records=8,
        )
        hypotheses = (
            RcaHypothesis(
                hypothesis_id="rca-hypothesis.controller-path-degradation",
                rank=1,
                fault_family=FAULT_FAMILIES[0],
                cause_type=CauseType.CONTRIBUTING_CAUSE,
                statement=(
                    f"A controller or path condition on {model} ({component_label}, vendor status "
                    f"'{component.vendor_status}') may be contributing to the warning."
                ),
                mechanism=(
                    "A degraded component or path could reduce redundancy and generate the "
                    "observed warning before a confirmed service symptom appears."
                ),
                expected_affected_entities=(request.target_id, component_label),
                expected_unaffected_entities=(),
                expected_sequence=(
                    "Component or path condition begins.",
                    "The bounded health source observes a warning.",
                    "Related path events may appear if the condition persists.",
                ),
                supporting_evidence=(health_evidence_id,),
                contradicting_evidence=(),
                missing_expected_observations=(
                    "Current host multipathing state.",
                    "Current SAN fabric and storage event sequence.",
                    "Time-aligned application telemetry.",
                    "A repeat health read confirming persistence.",
                ),
                confounders=(
                    "This environment has no CMDB or hypervisor mapping, so downstream service "
                    "impact cannot be evaluated.",
                    "The observation source may report a transient warning.",
                ),
                assumptions=(
                    "The health response maps to the same target and component in the case scope.",
                ),
                confirmation_level=ConfirmationLevel.SUPPORTED,
                confidence_rationale=(
                    "A current, direct hardware-health warning and an applicable mechanism support "
                    "the hypothesis, but only one read was taken and no independent path or peer "
                    "evidence is available."
                ),
                diagnostic_steps=(path_step, service_step),
            ),
            RcaHypothesis(
                hypothesis_id="rca-hypothesis.transient-observation",
                rank=2,
                fault_family=FAULT_FAMILIES[1],
                cause_type=CauseType.OBSERVATION_FAILURE,
                statement="The warning may be transient or specific to the observation source.",
                mechanism=(
                    "A short-lived state or collection limitation could produce a warning without "
                    "a persistent infrastructure or service condition."
                ),
                expected_affected_entities=(component_label,),
                expected_unaffected_entities=(),
                expected_sequence=(
                    "A transient state or collection anomaly occurs.",
                    "One bounded source records the warning.",
                    "A repeat read and service telemetry remain normal.",
                ),
                supporting_evidence=(),
                contradicting_evidence=(health_evidence_id,),
                missing_expected_observations=(
                    "A repeat health observation.",
                    "Observation-source health and parsing diagnostics.",
                ),
                confounders=("A single read cannot distinguish a persistent from a transient state.",),
                assumptions=("The connector's read reflects the array's true current state.",),
                confirmation_level=ConfirmationLevel.SUSPECTED,
                confidence_rationale=(
                    "No repeat read has been taken to reconcile the direct warning against this "
                    "hypothesis, so it remains only suspected."
                ),
                diagnostic_steps=(repeat_step, service_step),
            ),
        )

        return RcaCase(
            case_id=f"rca_{_identity(request.target_id, request.incident_id, str(created_at))}",
            version=version,
            prior_version_id=prior_version_id,
            owner="Storage Operations",
            requested_by=requested_by,
            state=RcaCaseState.PROVISIONAL,
            severity=severity,
            created_at=created_at,
            updated_at=created_at,
            incident_references=(
                IncidentReference(
                    reference_type="incident",
                    reference_id=request.incident_id,
                    authority=(
                        "user-provided incident reference; ITSM linkage not yet authoritative"
                    ),
                ),
            ),
            user_report=request.user_report,
            expected_behavior=request.expected_behavior,
            actual_behavior=request.actual_behavior,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            target_id=request.target_id,
            window_start=request.window_start,
            window_end=request.window_end,
            fault_families=FAULT_FAMILIES,
            symptoms=(
                NormalizedSymptom(
                    symptom_id="symptom.storage.warning",
                    statement=request.actual_behavior,
                    first_observed_at=timeline[0].occurred_at,
                    current_state="observed warning; persistence and impact unknown",
                    evidence_references=(health_evidence_id,),
                ),
            ),
            impact_scope=ImpactScope(
                affected_entities=(request.target_id, component_label),
                possibly_affected_services=(),
                explicitly_unaffected_entities=(),
                current_impact=(
                    "A component warning is observed. No service outage is confirmed; reduced "
                    "redundancy remains possible."
                ),
                business_criticality=(
                    "Unknown -- no service, VM, or business-mapping data is available in this "
                    "environment."
                ),
                impact_confirmed=False,
                limitations=(
                    "No CMDB or hypervisor mapping exists in this environment, so downstream "
                    "service impact cannot be evaluated.",
                    "No path, event-log, fabric, or application telemetry is available.",
                ),
            ),
            source_investigation_artifact_id=(
                f"investigation.rca.{_identity(request.target_id, str(created_at))}"
            ),
            source_investigation_version=1,
            evidence=evidence,
            timeline=timeline,
            hypotheses=hypotheses,
            findings=(
                RcaFinding(
                    finding_id="rca-finding.warning-supported",
                    cause_type=CauseType.CONTRIBUTING_CAUSE,
                    statement=(
                        "A controller or path degradation mechanism is supported as a candidate "
                        "contributing condition, not a confirmed root cause."
                    ),
                    confirmation_level=ConfirmationLevel.SUPPORTED,
                    evidence_references=(health_evidence_id,),
                    residual_uncertainty=(
                        "No current path, event-log, fabric, or service evidence confirms "
                        "mechanism.",
                    ),
                ),
            ),
            assumptions=(
                "The connector's allowlisted read-only capability reflects the array's current "
                "state.",
            ),
            unknowns=(
                "Whether the warning is persistent or transient.",
                "Whether any downstream service is affected.",
            ),
            conflicts=(),
            evidence_gaps=(
                "Current path and event-log evidence is missing.",
                "Current SAN fabric and host multipathing evidence is missing.",
                "Current authorized application telemetry is missing.",
                "No authoritative recent-change record is linked.",
            ),
            blocker=(
                "Safe evidence is insufficient to distinguish persistent path degradation from a "
                "transient observation failure."
            ),
            safest_next_step="Run the allowlisted C1 path/event and repeat-health reads.",
            provisional_statement=ProvisionalCauseStatement(
                statement=(
                    "No root cause is confirmed. Current evidence supports controller or path "
                    "degradation as the leading candidate contributing condition."
                ),
                confirmation_level=ConfirmationLevel.SUPPORTED,
                supporting_evidence=(health_evidence_id,),
                contradicting_evidence=(),
                residual_uncertainty=(
                    "The warned state has not been reproduced.",
                    "A causal path to service impact is not observed.",
                ),
                alternatives_not_ruled_out=(
                    "Transient component state.",
                    "Observation-source or parsing limitation.",
                    "An independent downstream condition not represented in current evidence.",
                ),
                prevention_or_verification_implication=(
                    "Collect current path, event, and service evidence before remediation or "
                    "preventive-change planning."
                ),
            ),
            human_review=HumanReview(
                status=ReviewStatus.PENDING,
                reviewer_id=None,
                reviewed_at=None,
                decision_reason=None,
                domain_confirmation_criterion=None,
            ),
            component_versions=(
                "rca-case-contract.v1",
                "storage-fault-model.v1",
                f"hitachi-ops-center-connector.{self._connector_version}",
            ),
            data_profile=_DATA_PROFILE,
            root_cause_confirmed=False,
            safety_notice=SAFETY_NOTICE,
        )

    def _no_active_finding_case(
        self,
        *,
        request: RcaCreateRequest,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
        evidence: tuple[EvidenceUnit, ...],
        timeline: tuple[TimelineEvent, ...],
        health_evidence_id: str,
    ) -> RcaCase:
        return RcaCase(
            case_id=f"rca_{_identity(request.target_id, request.incident_id, str(created_at))}",
            version=version,
            prior_version_id=prior_version_id,
            owner="Storage Operations",
            requested_by=requested_by,
            state=RcaCaseState.INCONCLUSIVE,
            severity=RcaSeverity.UNKNOWN,
            created_at=created_at,
            updated_at=created_at,
            incident_references=(
                IncidentReference(
                    reference_type="incident",
                    reference_id=request.incident_id,
                    authority=(
                        "user-provided incident reference; ITSM linkage not yet authoritative"
                    ),
                ),
            ),
            user_report=request.user_report,
            expected_behavior=request.expected_behavior,
            actual_behavior=request.actual_behavior,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            target_id=request.target_id,
            window_start=request.window_start,
            window_end=request.window_end,
            fault_families=(),
            symptoms=(),
            impact_scope=ImpactScope(
                affected_entities=(),
                possibly_affected_services=(),
                explicitly_unaffected_entities=(request.target_id,),
                current_impact="No active hardware finding was observed for this target.",
                business_criticality="Unknown -- no active finding to assess.",
                impact_confirmed=False,
                limitations=(
                    "A single current read cannot rule out an intermittent or already-resolved "
                    "condition.",
                ),
            ),
            source_investigation_artifact_id=(
                f"investigation.rca.{_identity(request.target_id, str(created_at))}"
            ),
            source_investigation_version=1,
            evidence=evidence,
            timeline=timeline,
            hypotheses=(),
            findings=(),
            assumptions=(
                "The connector's allowlisted read-only capability reflects the array's current "
                "state.",
            ),
            unknowns=(
                "Whether the reported symptom was transient, already resolved, or unrelated to "
                "storage hardware health.",
            ),
            conflicts=(),
            evidence_gaps=(
                "A repeat read across the reported window was not collected.",
                "No path, event-log, or application telemetry is available.",
            ),
            blocker=(
                "No active hardware finding exists to investigate; the reported symptom may be "
                "intermittent, already resolved, or unrelated to storage hardware health."
            ),
            safest_next_step=(
                "Re-run this RCA if the symptom recurs, or expand evidence to a repeat read across "
                "the reported window."
            ),
            provisional_statement=ProvisionalCauseStatement(
                statement=(
                    "No root cause is confirmed. The current hardware-health read shows no active "
                    "finding for this target."
                ),
                confirmation_level=ConfirmationLevel.INCONCLUSIVE,
                supporting_evidence=(health_evidence_id,),
                contradicting_evidence=(),
                residual_uncertainty=("The reported symptom was not reproduced in this read.",),
                alternatives_not_ruled_out=(
                    "An intermittent or already-resolved condition.",
                    "A cause outside storage hardware health.",
                ),
                prevention_or_verification_implication=(
                    "Collect a repeat read across the reported window if the symptom recurs."
                ),
            ),
            human_review=HumanReview(
                status=ReviewStatus.PENDING,
                reviewer_id=None,
                reviewed_at=None,
                decision_reason=None,
                domain_confirmation_criterion=None,
            ),
            component_versions=(
                "rca-case-contract.v1",
                "storage-fault-model.v1",
                f"hitachi-ops-center-connector.{self._connector_version}",
            ),
            data_profile=_DATA_PROFILE,
            root_cause_confirmed=False,
            safety_notice=SAFETY_NOTICE,
        )

    @staticmethod
    def _diagnostic_step(
        *,
        step_id: str,
        question: str,
        target_id: str,
        capability_id: str,
        evidence_source: str,
        expected_if_supported: str,
        expected_if_not_supported: str,
        supported_branch: str,
        unsupported_branch: str,
        timeout_seconds: int,
        max_output_records: int,
    ) -> DiagnosticStep:
        return DiagnosticStep(
            step_id=step_id,
            question=question,
            target_id=target_id,
            scope=f"exact storage target {target_id}",
            capability_id=capability_id,
            capability_class="C1",
            evidence_source=evidence_source,
            preconditions=(
                "Exact target authorization remains valid.",
                "Connector and audit services are healthy.",
            ),
            expected_duration_seconds=timeout_seconds,
            expected_load="One bounded read-only request; no target state change.",
            max_output_records=max_output_records,
            expected_if_supported=expected_if_supported,
            expected_if_not_supported=expected_if_not_supported,
            timeout_seconds=timeout_seconds,
            stop_condition=(
                "Stop on timeout, authorization or scope failure, stale response, or output limit."
            ),
            required_role="role.development.operator",
            policy_reference="policy.rca.diagnostic.c1-read-only.v1",
            approval_required=False,
            classification=DataClassification.INTERNAL,
            retention="Retain evidence reference under the RCA case retention policy.",
            supported_branch=supported_branch,
            unsupported_branch=unsupported_branch,
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

    async def _allowed_storage_ids(self) -> frozenset[str]:
        devices = await self._inventory_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            query=None,
            limit=500,
        )
        identifiers = (
            device.serial_number
            for device in devices
            if device.device_type is InventoryDeviceType.STORAGE
            and "hitachi" in device.vendor.lower()
            and device.serial_number is not None
            and _STORAGE_DEVICE_ID.fullmatch(device.serial_number)
        )
        return frozenset(tuple(identifiers)[: self._max_targets])
