from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas.modules.recommendations.domain.models import (
    OptionState,
    RecommendationArtifact,
    RecommendationOption,
)
from atlas.modules.reports.domain.models import (
    HandoffState,
    ItsmFieldMapping,
    ItsmHandoffDraft,
    RedactionState,
    ReportRequest,
    ReportReview,
    ReportSection,
    ReportSourceLineage,
    ReportState,
    ReviewStatus,
    SectionState,
    TechnicalReport,
)

SAFETY_NOTICE = (
    "Decision support only. Report generation and ITSM handoff preparation do not authorize "
    "Atlas to execute infrastructure changes or mutate an external ticket."
)


class SyntheticTechnicalReportAssembler:
    def build(
        self,
        request: ReportRequest,
        source: RecommendationArtifact,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> TechnicalReport:
        report_id = f"report_{uuid4().hex}"
        evidence_ids = tuple(item.evidence_id for item in source.source_evidence)
        preferred = next(
            (option for option in source.options if option.option_id == source.preferred_option_id),
            None,
        )
        sections = self._sections(source, preferred)
        lineage = ReportSourceLineage(
            recommendation_id=source.recommendation_id,
            recommendation_version=source.version,
            recommendation_state=source.state.value,
            recommendation_created_at=source.created_at,
            recommendation_expires_at=source.expires_at,
            rca_case_id=source.source_case_id,
            rca_case_version=source.source_case_version,
            target_id=source.target_id,
            evidence_ids=evidence_ids,
            component_versions=source.component_versions,
        )
        markdown = self._render_markdown(
            report_id=report_id,
            version=version,
            created_at=created_at,
            request=request,
            source=source,
            sections=sections,
        )
        handoff = self._handoff(
            request,
            source,
            report_id=report_id,
            report_version=version,
            sections=sections,
        )
        return TechnicalReport(
            report_id=report_id,
            version=version,
            prior_version_id=prior_version_id,
            owner="Storage Operations",
            state=ReportState.READY_FOR_REVIEW,
            requested_by=requested_by,
            created_at=created_at,
            expires_at=min(source.expires_at, created_at + timedelta(hours=4)),
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            target_id=request.target_id,
            report_type=request.report_type,
            audience=request.audience,
            classification=request.classification,
            redaction_state=RedactionState.COMPLETE,
            source=lineage,
            sections=sections,
            review=ReportReview(ReviewStatus.PENDING, None, None, None),
            itsm_handoff=handoff,
            rendered_markdown=markdown,
            content_digest=sha256(markdown.encode("utf-8")).hexdigest(),
            component_versions=(
                "technical-decision-report.v1",
                "itsm-handoff-draft.v1",
                *source.component_versions,
            ),
            data_profile="synthetic_lab",
            execution_authorized=False,
            external_mutation_authorized=False,
            safety_notice=SAFETY_NOTICE,
        )

    @staticmethod
    def _sections(
        source: RecommendationArtifact,
        preferred: RecommendationOption | None,
    ) -> tuple[ReportSection, ...]:
        source_limitations = (
            f"Source RCA remains {source.source_case_state}.",
            f"Recommendation review remains {source.human_review.status.value}.",
        )
        scope = ReportSection(
            section_id="report.section.scope",
            title="Scope and source lineage",
            state=SectionState.COMPLETE,
            statements=(
                f"Target: {source.target_id}.",
                f"Recommendation: {source.recommendation_id} version {source.version}.",
                f"RCA case: {source.source_case_id} version {source.source_case_version}.",
                f"Decision question: {source.decision_question}",
            ),
            evidence_references=(),
            limitations=(),
        )
        known = ReportSection(
            section_id="report.section.decision-context",
            title="Decision context and evidence boundary",
            state=SectionState.PARTIAL,
            statements=(
                f"The recommendation compares {len(source.options)} explicit options.",
                f"The artifact contains {len(source.source_evidence)} attributable evidence units.",
                "Graph reachability and provisional RCA do not confirm a service outage.",
            ),
            evidence_references=tuple(item.evidence_id for item in source.source_evidence),
            limitations=source_limitations,
        )
        if preferred is None:
            preference = ReportSection(
                section_id="report.section.preference",
                title="Preferred option",
                state=SectionState.FAILED,
                statements=("No supportable preferred option is available.",),
                evidence_references=(),
                limitations=("The source recommendation does not identify a preferred option.",),
            )
        else:
            preference = ReportSection(
                section_id="report.section.preference",
                title="Preferred option",
                state=SectionState.PARTIAL,
                statements=(
                    preferred.title,
                    preferred.intended_outcome,
                    source.preference_rationale,
                    (
                        f"Expected duration: {preferred.duration.minimum_minutes}-"
                        f"{preferred.duration.maximum_minutes} minutes."
                    ),
                    f"Expected interruption: {preferred.interruption.expected_mode}.",
                ),
                evidence_references=tuple(
                    dict.fromkeys(preferred.supporting_evidence + preferred.contradicting_evidence)
                ),
                limitations=(
                    *preferred.unknowns,
                    *preferred.impact.gaps,
                    "Duration and interruption are estimates, not guarantees.",
                ),
            )
        alternatives = tuple(
            option for option in source.options if option.option_id != source.preferred_option_id
        )
        alternative_statements = tuple(
            (
                f"{option.category.value}: {option.title}; state {option.state.value}; "
                f"risk {option.overall_risk.value}; policy {option.policy_outcome}."
            )
            for option in alternatives
        )
        alternative_evidence = tuple(
            dict.fromkeys(
                reference
                for option in alternatives
                for reference in option.supporting_evidence + option.contradicting_evidence
            )
        )
        blocked_reasons = tuple(
            reason
            for option in alternatives
            if option.state is OptionState.BLOCKED
            for reason in option.exclusion_reasons
        )
        alternatives_section = ReportSection(
            section_id="report.section.alternatives",
            title="Alternatives and exclusions",
            state=SectionState.PARTIAL if blocked_reasons else SectionState.COMPLETE,
            statements=alternative_statements or ("No alternative option was produced.",),
            evidence_references=alternative_evidence,
            limitations=blocked_reasons,
        )
        risk_statements: tuple[str, ...]
        risk_evidence: tuple[str, ...]
        risk_limitations: tuple[str, ...]
        if preferred is None:
            risk_statements = ("Preferred-option risk cannot be summarized.",)
            risk_evidence = ()
            risk_limitations = ("No preferred option is available.",)
        else:
            risk_statements = (
                f"Overall preferred-option risk: {preferred.overall_risk.value}.",
                f"Blast radius: {preferred.impact.blast_radius}",
                f"Redundancy: {preferred.impact.redundancy_effect}",
                f"Data protection: {preferred.impact.data_protection_effect}",
                f"Recovery strategy: {preferred.recovery.strategy}",
                (
                    "Rollback is credible."
                    if preferred.recovery.rollback_feasible
                    else "Rollback is not established."
                ),
            )
            risk_evidence = tuple(
                dict.fromkeys(preferred.supporting_evidence + preferred.contradicting_evidence)
            )
            risk_limitations = (
                *preferred.impact.gaps,
                *preferred.recovery.gaps,
                *preferred.residual_risk,
            )
        risk = ReportSection(
            section_id="report.section.risk-impact-recovery",
            title="Risk, impact, interruption, and recovery",
            state=SectionState.PARTIAL,
            statements=risk_statements,
            evidence_references=risk_evidence,
            limitations=risk_limitations,
        )
        governance = ReportSection(
            section_id="report.section.governance",
            title="Governance and review boundary",
            state=SectionState.PARTIAL,
            statements=(
                *source.policy_constraints,
                "No Atlas execution authority is present.",
                "Report review does not grant RBAC, approval, or runtime authority.",
            ),
            evidence_references=(),
            limitations=("An accountable human review remains pending.",),
        )
        return scope, known, preference, alternatives_section, risk, governance

    @staticmethod
    def _render_markdown(
        *,
        report_id: str,
        version: int,
        created_at: datetime,
        request: ReportRequest,
        source: RecommendationArtifact,
        sections: tuple[ReportSection, ...],
    ) -> str:
        lines = [
            "# Atlas Technical Decision Report",
            "",
            f"- Report: `{report_id}` version {version}",
            f"- Created: {created_at.isoformat()}",
            f"- Target: `{request.target_id}`",
            f"- Audience: {request.audience.value}",
            f"- Classification: {request.classification.value}",
            (f"- Source recommendation: `{source.recommendation_id}` version {source.version}"),
            f"- Human review: {source.human_review.status.value}",
            "",
        ]
        for section in sections:
            lines.extend((f"## {section.title}", "", f"Status: **{section.state.value}**", ""))
            lines.extend(f"- {statement}" for statement in section.statements)
            if section.evidence_references:
                lines.extend(("", "Evidence:"))
                lines.extend(f"- `{reference}`" for reference in section.evidence_references)
            if section.limitations:
                lines.extend(("", "Limitations:"))
                lines.extend(f"- {limitation}" for limitation in section.limitations)
            lines.append("")
        lines.extend(("## Safety Boundary", "", SAFETY_NOTICE, ""))
        return "\n".join(lines)

    @staticmethod
    def _handoff(
        request: ReportRequest,
        source: RecommendationArtifact,
        *,
        report_id: str,
        report_version: int,
        sections: tuple[ReportSection, ...],
    ) -> ItsmHandoffDraft | None:
        if not request.include_itsm_handoff:
            return None
        assert request.incident_reference is not None
        key_material = "|".join(
            (
                request.target_id,
                source.recommendation_id,
                str(source.version),
                request.incident_reference,
                request.report_type.value,
                request.audience.value,
            )
        )
        preference = next(
            section for section in sections if section.section_id == "report.section.preference"
        )
        return ItsmHandoffDraft(
            draft_id=f"itsm_draft_{uuid4().hex}",
            idempotency_key=sha256(key_material.encode("utf-8")).hexdigest(),
            state=HandoffState.REVIEW_REQUIRED,
            external_system="unconfigured_itsm",
            operation="append_labeled_analysis",
            incident_reference=request.incident_reference,
            report_id=report_id,
            report_version=report_version,
            generated_content_label="Atlas generated decision-support draft",
            field_mappings=(
                ItsmFieldMapping(
                    "work_notes",
                    preference.statements[0],
                    preference.section_id,
                ),
                ItsmFieldMapping(
                    "u_atlas_report_reference",
                    f"{report_id}:v{report_version}",
                    report_id,
                ),
                ItsmFieldMapping(
                    "u_atlas_review_state",
                    "pending",
                    source.recommendation_id,
                ),
            ),
            artifact_references=(
                f"recommendation:{source.recommendation_id}:v{source.version}",
                f"rca:{source.source_case_id}:v{source.source_case_version}",
                f"report:{report_id}:v{report_version}",
            ),
            classification=request.classification,
            redaction_state=RedactionState.COMPLETE,
            human_review_required=True,
            dispatch_authorized=False,
            external_record_mutated=False,
        )
