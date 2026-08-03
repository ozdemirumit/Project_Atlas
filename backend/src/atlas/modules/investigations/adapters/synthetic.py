from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from atlas.core.classification import DataClassification
from atlas.modules.investigations.domain.models import (
    Claim,
    ConfidenceCategory,
    DiscriminatingCheck,
    EpistemicType,
    EvidenceUnit,
    FreshnessState,
    Hypothesis,
    HypothesisState,
    InvestigationRequest,
    ReasoningArtifact,
    ReasoningSummary,
    TimelineEvent,
)

SUPPORTED_TARGETS = {
    "asset.storage.lab.b28": ("VSP One B28", "controller path warning"),
    "asset.storage.lab.g400": ("VSP G400", "capacity threshold warning"),
}

SAFETY_NOTICE = (
    "Decision support only. This artifact does not confirm root cause or outage and does not "
    "authorize or execute an infrastructure change."
)


class SyntheticInvestigationAssembler:
    def build(
        self,
        request: InvestigationRequest,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> ReasoningArtifact:
        target = SUPPORTED_TARGETS.get(request.target_id)
        if target is None:
            raise KeyError(request.target_id)
        model, symptom = target
        health_at = created_at - timedelta(minutes=5)
        graph_at = created_at - timedelta(minutes=45)
        peer_at = created_at - timedelta(minutes=4)
        vendor_at = created_at - timedelta(days=2)
        auth_ref = "/".join((organization_id, environment_id, site_id, request.target_id))

        evidence = (
            EvidenceUnit(
                evidence_id="evidence.investigation.health.latest",
                artifact_version="health-run.v1",
                source_type="connector_observation",
                source_system="synthetic-hitachi-ops-center",
                source_version="1.0.0",
                target_id=request.target_id,
                observed_at=health_at,
                applicable_from=health_at,
                applicable_to=None,
                freshness=FreshnessState.CURRENT,
                classification=DataClassification.INTERNAL,
                authorization_reference=auth_ref,
                collection_method="allowlisted C1 read-only health check",
                summary=f"The {model} reported a {symptom}; the bounded run was partial.",
                integrity="synthetic signed fixture",
                completeness="partial",
                quality_limitations=("Current event-log evidence was not collected.",),
                citation="health-check://storage/latest",
            ),
            EvidenceUnit(
                evidence_id="evidence.investigation.graph.path",
                artifact_version="graph-snapshot.v1",
                source_type="graph_snapshot",
                source_system="synthetic-cmdb-and-opscenter",
                source_version="lab-graph-1.0",
                target_id=request.target_id,
                observed_at=graph_at,
                applicable_from=graph_at,
                applicable_to=None,
                freshness=FreshnessState.AGING,
                classification=DataClassification.INTERNAL,
                authorization_reference=auth_ref,
                collection_method="bounded authorized graph traversal",
                summary=(
                    "The target has authorized downstream infrastructure relationships; runtime "
                    "availability and SAN redundancy are not represented."
                ),
                integrity="reconciled synthetic topology",
                completeness="partial",
                quality_limitations=(
                    "Graph reachability does not prove current service impact.",
                    "SAN fabric redundancy is not represented.",
                ),
                citation="graph://storage-impact/current",
            ),
            EvidenceUnit(
                evidence_id="evidence.investigation.vendor.guidance",
                artifact_version="kb-synthetic-1.0",
                source_type="governed_knowledge",
                source_system="synthetic-vendor-knowledge",
                source_version="storage-path-guidance-1.0",
                target_id=request.target_id,
                observed_at=vendor_at,
                applicable_from=vendor_at,
                applicable_to=None,
                freshness=FreshnessState.CURRENT,
                classification=DataClassification.INTERNAL,
                authorization_reference=auth_ref,
                collection_method="ACL-filtered governed retrieval",
                summary=(
                    "Applicable guidance requires controller, event-log, host-path, and fabric "
                    "evidence before attributing a path warning to a root cause."
                ),
                integrity="approved synthetic knowledge fixture",
                completeness="complete for the cited guidance",
                quality_limitations=("This fixture is not production vendor documentation.",),
                citation="knowledge://storage/path-diagnostics/1.0",
            ),
            EvidenceUnit(
                evidence_id="evidence.investigation.peer.signal",
                artifact_version="health-peer.v1",
                source_type="connector_observation",
                source_system="synthetic-hitachi-ops-center",
                source_version="1.0.0",
                target_id=request.target_id,
                observed_at=peer_at,
                applicable_from=peer_at,
                applicable_to=None,
                freshness=FreshnessState.CURRENT,
                classification=DataClassification.INTERNAL,
                authorization_reference=auth_ref,
                collection_method="allowlisted C1 peer-state read",
                summary="The peer controller remained available and no outage signal was observed.",
                integrity="synthetic signed fixture",
                completeness="partial",
                quality_limitations=("Application-level telemetry is unavailable.",),
                citation="health-check://storage/peer/latest",
            ),
        )

        timeline = (
            TimelineEvent(
                event_id="timeline.graph.snapshot",
                event_type="topology_observed",
                summary="The bounded dependency snapshot was observed before the health warning.",
                occurred_at=graph_at,
                observed_at=graph_at,
                ingested_at=graph_at + timedelta(seconds=20),
                evidence_references=("evidence.investigation.graph.path",),
                clock_quality="synthetic UTC clock; no measured skew",
            ),
            TimelineEvent(
                event_id="timeline.health.warning",
                event_type="health_warning_observed",
                summary=f"A {symptom} was observed on {model}.",
                occurred_at=health_at,
                observed_at=health_at,
                ingested_at=health_at + timedelta(seconds=8),
                evidence_references=("evidence.investigation.health.latest",),
                clock_quality="synthetic UTC clock; no measured skew",
            ),
            TimelineEvent(
                event_id="timeline.peer.available",
                event_type="peer_state_observed",
                summary="The peer state was observed as available after the warning.",
                occurred_at=peer_at,
                observed_at=peer_at,
                ingested_at=peer_at + timedelta(seconds=7),
                evidence_references=("evidence.investigation.peer.signal",),
                clock_quality="synthetic UTC clock; no measured skew",
            ),
        )

        claims = (
            self._claim(
                request,
                "claim.health.warning",
                EpistemicType.OBSERVATION,
                f"The latest bounded health run observed a {symptom} on {model}.",
                ("evidence.investigation.health.latest",),
                ConfidenceCategory.HIGH,
                ("Current direct C1 observation.",),
                ("The health run did not include current event logs.",),
            ),
            self._claim(
                request,
                "claim.vendor.requirements",
                EpistemicType.RETRIEVED_FACT,
                (
                    "The applicable diagnostic guidance requires corroborating path and event "
                    "evidence."
                ),
                ("evidence.investigation.vendor.guidance",),
                ConfidenceCategory.HIGH,
                ("Governed applicable guidance was retrieved.",),
                ("The source is a synthetic lab fixture.",),
            ),
            self._claim(
                request,
                "claim.available.controllers",
                EpistemicType.CALCULATED_FINDING,
                "One warning signal and one available peer signal are present in the bounded set.",
                (
                    "evidence.investigation.health.latest",
                    "evidence.investigation.peer.signal",
                ),
                ConfidenceCategory.HIGH,
                ("Deterministic count from two current observations.",),
                ("The calculation does not describe end-to-end path redundancy.",),
            ),
            self._claim(
                request,
                "claim.temporal.association",
                EpistemicType.CORRELATION,
                "The path warning and available peer state occur in the same analysis window.",
                (
                    "evidence.investigation.health.latest",
                    "evidence.investigation.peer.signal",
                ),
                ConfidenceCategory.MODERATE,
                ("Both observations use comparable UTC timestamps.",),
                ("Temporal association does not establish causality.",),
            ),
            Claim(
                claim_id="claim.redundancy.inference",
                epistemic_type=EpistemicType.INFERENCE,
                text=(
                    "The warning may indicate reduced component redundancy, but current service "
                    "impact cannot be inferred from the available evidence."
                ),
                scope=request.target_id,
                window_start=request.window_start,
                window_end=request.window_end,
                supporting_evidence=(
                    "evidence.investigation.health.latest",
                    "evidence.investigation.graph.path",
                ),
                contradicting_evidence=("evidence.investigation.peer.signal",),
                assumptions=("The synthetic component-state mapping is applicable to the target.",),
                confidence=ConfidenceCategory.LOW,
                supporting_factors=("A direct warning and downstream relationships are present.",),
                limiting_factors=(
                    "Peer availability weakens an outage interpretation.",
                    "Host path and SAN fabric telemetry are absent.",
                ),
                validation_state="provisional",
            ),
            Claim(
                claim_id="claim.mapping.assumption",
                epistemic_type=EpistemicType.ASSUMPTION,
                text=(
                    "The aging graph mapping is assumed applicable for this bounded investigation."
                ),
                scope=request.target_id,
                window_start=request.window_start,
                window_end=request.window_end,
                supporting_evidence=(),
                contradicting_evidence=(),
                assumptions=("The CMDB relationship has not changed since observation.",),
                confidence=ConfidenceCategory.LOW,
                supporting_factors=(),
                limiting_factors=("The graph snapshot is aging and partial.",),
                validation_state="declared",
            ),
            Claim(
                claim_id="claim.current.impact.unknown",
                epistemic_type=EpistemicType.UNKNOWN,
                text="Current application impact and end-to-end SAN path state are unknown.",
                scope=request.target_id,
                window_start=request.window_start,
                window_end=request.window_end,
                supporting_evidence=(),
                contradicting_evidence=(),
                assumptions=(),
                confidence=ConfidenceCategory.INSUFFICIENT,
                supporting_factors=(),
                limiting_factors=("Required telemetry is unavailable.",),
                validation_state="open",
            ),
            self._claim(
                request,
                "claim.next.check",
                EpistemicType.RECOMMENDATION,
                (
                    "Collect a bounded read-only path and event-log snapshot before remediation "
                    "planning."
                ),
                ("evidence.investigation.vendor.guidance",),
                ConfidenceCategory.HIGH,
                ("The check directly addresses the most important evidence gap.",),
                ("The connector capability must remain allowlisted and authorized.",),
            ),
        )

        path_check = DiscriminatingCheck(
            check_id="check.read.path-and-events",
            title="Read current path and event evidence",
            rationale="Distinguishes transient component warning from persistent path degradation.",
            capability_id="hitachi.opscenter.storage.path-events.read",
            capability_class="C1",
            target_id=request.target_id,
            expected_if_supported="Repeated path errors or degraded path state are present.",
            expected_if_not_supported="Paths are current and no related event sequence is present.",
            timeout_seconds=30,
            stop_condition=(
                "Stop on timeout, authorization failure, scope mismatch, or output limit."
            ),
        )
        service_check = DiscriminatingCheck(
            check_id="check.read.service-telemetry",
            title="Read current authorized service telemetry",
            rationale="Tests whether downstream service symptoms accompany the storage warning.",
            capability_id="atlas.telemetry.service-health.read",
            capability_class="C1",
            target_id=request.target_id,
            expected_if_supported="Latency or availability symptoms align with the warning window.",
            expected_if_not_supported="No scoped service symptom is observed in the same window.",
            timeout_seconds=20,
            stop_condition="Stop on stale data, scope mismatch, or unavailable telemetry.",
        )
        hypotheses = (
            Hypothesis(
                hypothesis_id="hypothesis.path.degradation",
                statement=(
                    "A storage path or controller condition may be contributing to degradation."
                ),
                state=HypothesisState.SUPPORTED,
                expected_consequences=(
                    "Repeated path events would be present.",
                    "A subset of authorized hosts may show degraded path state.",
                ),
                supporting_evidence=("evidence.investigation.health.latest",),
                contradicting_evidence=("evidence.investigation.peer.signal",),
                assumptions=("The warning maps to the same target and time window.",),
                confidence=ConfidenceCategory.LOW,
                confidence_rationale=(
                    "One direct warning supports the hypothesis, while peer availability and "
                    "missing "
                    "path evidence prevent a stronger conclusion."
                ),
                limiting_factors=("No current host-path or fabric evidence.",),
                discriminating_checks=(path_check,),
            ),
            Hypothesis(
                hypothesis_id="hypothesis.transient.observation",
                statement="The warning may be transient or isolated to the observation source.",
                state=HypothesisState.UNRESOLVED,
                expected_consequences=(
                    "A repeat read would not reproduce the warning.",
                    "No related service symptom or event sequence would be present.",
                ),
                supporting_evidence=("evidence.investigation.peer.signal",),
                contradicting_evidence=("evidence.investigation.health.latest",),
                assumptions=(
                    "The peer signal is independent enough to weaken an outage interpretation.",
                ),
                confidence=ConfidenceCategory.LOW,
                confidence_rationale=(
                    "Peer availability supports an alternative explanation, but the original "
                    "warning "
                    "has not yet been repeated or reconciled."
                ),
                limiting_factors=("No repeat observation and no current service telemetry.",),
                discriminating_checks=(path_check, service_check),
            ),
        )

        return ReasoningArtifact(
            artifact_id=f"investigation_{uuid4().hex}",
            version=version,
            prior_version_id=prior_version_id,
            requested_by=requested_by,
            created_at=created_at,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            target_id=request.target_id,
            question=request.question,
            intended_decision=request.intended_decision,
            window_start=request.window_start,
            window_end=request.window_end,
            evidence=evidence,
            timeline=timeline,
            claims=claims,
            hypotheses=hypotheses,
            assumptions=("The aging graph mapping remains applicable to this target.",),
            unknowns=(
                "Current host multipathing and SAN fabric state are unavailable.",
                "Current application latency and availability are unavailable.",
                "The initiating event sequence is unavailable.",
            ),
            conflicts=(
                "A component warning is present while the peer remains available; this does not "
                "resolve whether redundancy or service is degraded.",
            ),
            excluded_evidence=(
                "Restricted graph relationships were excluded before assembly.",
                "Evidence outside the requested time and authorization scope was not used.",
            ),
            stop_reason=(
                "Evidence is sufficient to frame alternatives but insufficient to confirm root "
                "cause "
                "or current service impact."
            ),
            recommended_next_evidence=(
                "Current bounded path and event-log snapshot.",
                "Authorized service telemetry for the same UTC window.",
            ),
            component_versions=(
                "investigation-contract.v1",
                "synthetic-investigation-assembler.v1",
                "graph-snapshot.v1",
                "health-run.v1",
            ),
            summary=ReasoningSummary(
                known=(
                    f"A current bounded health run observed a {symptom} on {model}.",
                    "The peer controller remained available in the bounded evidence set.",
                ),
                inferred=(
                    "Reduced redundancy is plausible, but service impact is not established.",
                ),
                alternatives=(
                    "Persistent path degradation.",
                    "A transient or observation-source-specific warning.",
                ),
                unknowns=(
                    "Current end-to-end path state, event sequence, and application impact.",
                ),
                confidence=ConfidenceCategory.LOW,
                confidence_rationale=(
                    "Current direct observations exist, but material path, event, and service "
                    "evidence is missing and the available signals conflict."
                ),
                safest_next_check="Run the bounded C1 path and event evidence read.",
                supported_decision="Collect more read-only evidence and continue human review.",
                unsupported_decision="Do not declare root cause, outage, or remediation readiness.",
            ),
            data_profile="synthetic_lab",
            root_cause_confirmed=False,
            outage_confirmed=False,
            safety_notice=SAFETY_NOTICE,
        )

    @staticmethod
    def _claim(
        request: InvestigationRequest,
        claim_id: str,
        epistemic_type: EpistemicType,
        text: str,
        evidence: tuple[str, ...],
        confidence: ConfidenceCategory,
        supporting_factors: tuple[str, ...],
        limiting_factors: tuple[str, ...],
    ) -> Claim:
        return Claim(
            claim_id=claim_id,
            epistemic_type=epistemic_type,
            text=text,
            scope=request.target_id,
            window_start=request.window_start,
            window_end=request.window_end,
            supporting_evidence=evidence,
            contradicting_evidence=(),
            assumptions=(),
            confidence=confidence,
            supporting_factors=supporting_factors,
            limiting_factors=limiting_factors,
            validation_state="validated" if evidence else "declared",
        )
