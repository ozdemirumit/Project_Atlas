from __future__ import annotations

import json
from dataclasses import asdict, replace

from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactEntry,
    ProtectedCandidateImpactInstruction,
    ProtectedCandidateImpactPath,
    ProtectedCandidateImpactReceipt,
    ProtectedCandidateImpactRecord,
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.graph.domain.models import StorageImpactResult


class SyntheticTrustedProtectedCandidateImpactAnalyzer:
    def __init__(self) -> None:
        self.calls: list[ProtectedCandidateImpactInstruction] = []
        self._vault: dict[
            str, tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]
        ] = {}

    async def analyze(
        self,
        instruction: ProtectedCandidateImpactInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        graph_result: StorageImpactResult,
    ) -> tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        graph_digest = digest(payload(graph_result))
        if (
            candidate_set.candidate_set_id != instruction.candidate_set_id
            or candidate_set.canonical_digest != instruction.candidate_set_digest
            or candidate_set.source_binding_digest != instruction.candidate_source_binding_digest
            or graph_result.snapshot_id != instruction.graph_snapshot_id
            or graph_digest != instruction.graph_snapshot_digest
            or graph_result.start_entity_id != instruction.start_entity_id
            or graph_result.max_depth != instruction.maximum_depth
            or graph_result.outage_confirmed
            or not graph_result.unknowns
            or not graph_result.known_gaps
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_source_invalid")

        paths = tuple(
            ProtectedCandidateImpactPath(
                scope=item.scope.value,
                entity_ids=item.entity_ids,
                relationship_ids=item.relationship_ids,
                evidence_references=item.evidence_references,
                canonical_digest=digest(payload(item)),
            )
            for item in graph_result.paths
        )
        entries: list[ProtectedCandidateImpactEntry] = []
        for candidate in candidate_set.candidates:
            entry = ProtectedCandidateImpactEntry(
                candidate_id=candidate.candidate_id,
                candidate_digest=candidate.canonical_digest,
                paths=paths,
                direct_entity_ids=graph_result.direct_entity_ids,
                possible_entity_ids=graph_result.possible_entity_ids,
                technical_service_ids=graph_result.technical_service_ids,
                business_service_ids=graph_result.business_service_ids,
                known_gaps=graph_result.known_gaps,
                unknowns=graph_result.unknowns,
                canonical_digest="0" * 64,
            )
            entries.append(replace(entry, canonical_digest=digest(payload(entry))))

        modeled_entity_ids = tuple(entity.entity_id for entity in graph_result.entities)
        coverage_digest = digest(
            [
                tuple(candidate.candidate_id for candidate in candidate_set.candidates),
                modeled_entity_ids,
                graph_result.technical_service_ids,
                graph_result.business_service_ids,
                tuple(path.canonical_digest for path in paths),
            ]
        )
        gap_digest = digest(graph_result.known_gaps)
        unknown_digest = digest(graph_result.unknowns)
        safety_digest = digest(
            [instruction.safety_profile_digest, graph_result.safety_notice, "no-outage-claim"]
        )
        encoded = json.dumps(
            GovernedProtectedModelInvocationService._normalize(
                [asdict(entry) for entry in entries]
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        service_count = len(graph_result.technical_service_ids) + len(
            graph_result.business_service_ids
        )
        if (
            len(entries) > instruction.maximum_candidate_count
            or len(paths) > instruction.maximum_path_count
            or len(modeled_entity_ids) > instruction.maximum_entity_count
            or service_count > instruction.maximum_service_count
            or len(graph_result.known_gaps) > instruction.maximum_gap_count
            or len(graph_result.unknowns) > instruction.maximum_unknown_count
            or len(encoded) > instruction.maximum_output_bytes
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_content_invalid")

        report = ProtectedCandidateImpactReport(
            impact_analysis_id=instruction.impact_analysis_id,
            schema_version=instruction.required_report_schema,
            version=1,
            candidate_set_id=instruction.candidate_set_id,
            candidate_set_digest=instruction.candidate_set_digest,
            policy_digest=instruction.policy_digest,
            graph_snapshot_id=instruction.graph_snapshot_id,
            graph_snapshot_digest=instruction.graph_snapshot_digest,
            graph_snapshot_generated_at=graph_result.snapshot_generated_at,
            graph_freshness=graph_result.freshness.value,
            graph_completeness=graph_result.completeness,
            graph_maturity=graph_result.digital_twin_maturity,
            entries=tuple(entries),
            modeled_entity_ids=modeled_entity_ids,
            technical_service_ids=graph_result.technical_service_ids,
            business_service_ids=graph_result.business_service_ids,
            graph_gap_digest=gap_digest,
            unknown_digest=unknown_digest,
            safety_digest=safety_digest,
            byte_count=len(encoded),
            analyzed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        report = replace(report, canonical_digest=digest(payload(report)))
        cleanup_digest = digest([instruction.impact_analysis_id, "cleanup-verified"])
        receipt = ProtectedCandidateImpactReceipt(
            impact_analysis_id=instruction.impact_analysis_id,
            schema_version="atlas.protected-candidate-impact-receipt.v1",
            version=1,
            analyzer_id="protected-candidate-impact-analyzer.synthetic",
            attested_by="subject.protected-candidate-impact-analyzer-attestor",
            candidate_set_id=instruction.candidate_set_id,
            candidate_set_digest=instruction.candidate_set_digest,
            impact_authorization_digest=instruction.impact_authorization_digest,
            policy_digest=instruction.policy_digest,
            graph_snapshot_id=instruction.graph_snapshot_id,
            graph_snapshot_digest=instruction.graph_snapshot_digest,
            report_digest=report.canonical_digest,
            coverage_digest=coverage_digest,
            unknown_digest=unknown_digest,
            safety_digest=safety_digest,
            cleanup_digest=cleanup_digest,
            candidate_count=len(entries),
            path_count=len(paths),
            modeled_entity_count=len(modeled_entity_ids),
            technical_service_count=len(graph_result.technical_service_ids),
            business_service_count=len(graph_result.business_service_ids),
            gap_count=len(graph_result.known_gaps),
            unknown_count=len(graph_result.unknowns),
            byte_count=len(encoded),
            analyzed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            candidate_source_verified=True,
            graph_snapshot_verified=True,
            bounded_traversal_verified=True,
            complete_candidate_coverage_verified=True,
            unknowns_preserved=True,
            no_outage_claim_verified=True,
            no_preference_assigned=True,
            no_model_used=True,
            cleanup_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        self._vault[instruction.impact_analysis_id] = (receipt, report)
        return receipt, report

    async def rehydrate(
        self,
        *,
        record: ProtectedCandidateImpactRecord,
        impact_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        graph_result: StorageImpactResult,
    ) -> tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]:
        stored = self._vault.get(record.impact_analysis_id)
        if stored is None:
            raise ProtectedCandidateImpactError("protected_candidate_impact_content_unavailable")
        receipt, report = stored
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        if (
            impact_authorization_digest != record.impact_authorization_digest
            or candidate_set.canonical_digest != record.candidate_set_digest
            or candidate_set.source_binding_digest != record.candidate_source_binding_digest
            or digest(payload(graph_result)) != record.graph_snapshot_digest
            or report.canonical_digest != record.protected_report_digest
            or receipt.canonical_digest != record.analysis_receipt_digest
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_integrity_failed")
        return receipt, report


class UnavailableTrustedProtectedCandidateImpactAnalyzer:
    async def analyze(
        self,
        instruction: ProtectedCandidateImpactInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        graph_result: StorageImpactResult,
    ) -> tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]:
        del instruction, candidate_set, graph_result
        raise ProtectedCandidateImpactError("protected_candidate_impact_analyzer_unavailable")

    async def rehydrate(
        self,
        *,
        record: ProtectedCandidateImpactRecord,
        impact_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        graph_result: StorageImpactResult,
    ) -> tuple[ProtectedCandidateImpactReceipt, ProtectedCandidateImpactReport]:
        del record, impact_authorization_digest, candidate_set, graph_result
        raise ProtectedCandidateImpactError("protected_candidate_impact_content_unavailable")
