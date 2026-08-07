from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime

from atlas.modules.ai.application.protected_draft_adjudication_ports import (
    ProtectedDraftAdjudicationError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationInstruction,
    ProtectedDraftAdjudicationReceipt,
    ProtectedDraftAdjudicationRecord,
    ProtectedDraftAdjudicationReport,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelResponseDraft
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class SyntheticTrustedProtectedDraftAdjudicator:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._vault: dict[str, tuple[ProtectedDraftAdjudicationReport, str, str]] = {}
        self.calls: list[ProtectedDraftAdjudicationInstruction] = []

    async def adjudicate(
        self,
        instruction: ProtectedDraftAdjudicationInstruction,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedDraftAdjudicationReceipt, ProtectedDraftAdjudicationReport]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        allowed = {unit.evidence_reference_id for unit in context.evidence_units}
        prohibited = ("tool_call", "function_call", "password=", "secret=", "operation completed")
        checks = {
            "check.schema.closed": draft.response_schema_version != ""
            and draft.summary.strip() != "",
            "check.citations.authorized": len(draft.citation_references)
            >= instruction.minimum_citation_count
            and all(ref in allowed for ref in draft.citation_references),
            "check.unknowns.preserved": len(draft.unknowns) >= instruction.minimum_unknown_count,
            "check.summary.bounded": len(draft.summary) <= instruction.maximum_summary_characters,
            "check.output.prohibited": not any(
                token in draft.summary.lower() for token in prohibited
            ),
            "check.lineage.integrity": draft.canonical_digest == instruction.draft_digest
            and context.canonical_digest == instruction.context_package_digest,
        }
        now = self._clock()
        outcome = (
            "adjudication-outcome.eligible"
            if all(checks.values())
            else "adjudication-outcome.rejected"
        )
        codes = tuple(
            f"{code}.{'passed' if passed else 'failed'}" for code, passed in checks.items()
        )
        report = ProtectedDraftAdjudicationReport(
            adjudication_id=instruction.adjudication_id,
            invocation_id=instruction.invocation_id,
            draft_digest=draft.canonical_digest,
            outcome=outcome,
            check_codes=codes,
            citation_count=len(draft.citation_references),
            unknown_count=len(draft.unknowns),
            summary_character_count=len(draft.summary),
            generated_at=now,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        report = replace(report, canonical_digest=digest(payload(report)))
        suffix = instruction.adjudication_id.rsplit(".", 1)[-1]
        reference = f"protected-draft-adjudication-artifact.{suffix}"
        artifact_digest = digest(asdict(report))
        self._vault[reference] = (
            report,
            instruction.adjudication_authorization_digest,
            artifact_digest,
        )
        receipt = ProtectedDraftAdjudicationReceipt(
            adjudication_id=instruction.adjudication_id,
            schema_version="atlas.protected-draft-adjudication-receipt.v1",
            version=1,
            adjudicator_id="protected-draft-adjudicator.synthetic",
            attested_by="subject.protected-draft-adjudicator-attestor",
            invocation_id=instruction.invocation_id,
            invocation_digest=instruction.invocation_digest,
            context_digest=instruction.context_digest,
            draft_digest=draft.canonical_digest,
            adjudication_authorization_digest=instruction.adjudication_authorization_digest,
            policy_digest=instruction.policy_digest,
            protected_report_reference=reference,
            protected_report_digest=artifact_digest,
            report_digest=report.canonical_digest,
            check_set_digest=digest(codes),
            citation_coverage_digest=digest(draft.citation_references),
            unknown_preservation_digest=digest(draft.unknowns),
            prohibited_output_digest=digest(
                [instruction.prohibited_output_profile_digest, checks["check.output.prohibited"]]
            ),
            check_count=len(codes),
            citation_count=len(draft.citation_references),
            unknown_count=len(draft.unknowns),
            outcome=outcome,
            adjudicated_at=now,
            expires_at=instruction.expires_at,
            schema_verified=checks["check.schema.closed"],
            citations_verified=checks["check.citations.authorized"],
            unknowns_verified=checks["check.unknowns.preserved"],
            prohibited_output_verified=checks["check.output.prohibited"],
            no_model_used=True,
            protected_vault_write_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        return receipt, report

    async def rehydrate(
        self, *, record: ProtectedDraftAdjudicationRecord, adjudication_authorization_digest: str
    ) -> ProtectedDraftAdjudicationReport:
        stored = self._vault.get(record.protected_report_reference)
        if (
            stored is None
            or stored[1] != adjudication_authorization_digest
            or stored[2] != record.protected_report_digest
            or stored[0].canonical_digest != record.report_digest
            or self._clock() >= record.expires_at
        ):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_report_unavailable")
        return stored[0]


class UnavailableTrustedProtectedDraftAdjudicator:
    async def adjudicate(
        self,
        instruction: ProtectedDraftAdjudicationInstruction,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedDraftAdjudicationReceipt, ProtectedDraftAdjudicationReport]:
        del instruction, draft, context
        raise ProtectedDraftAdjudicationError(
            "protected_draft_adjudication_adjudicator_unavailable"
        )

    async def rehydrate(
        self, *, record: ProtectedDraftAdjudicationRecord, adjudication_authorization_digest: str
    ) -> ProtectedDraftAdjudicationReport:
        del record, adjudication_authorization_digest
        raise ProtectedDraftAdjudicationError("protected_draft_adjudication_report_unavailable")
