from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.knowledge.application.ports import KnowledgeRetriever
from atlas.modules.knowledge.domain.models import RetrievalRequest


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    case_id: str
    request: RetrievalRequest
    expected_references: frozenset[str]
    forbidden_references: frozenset[str]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationResult:
    case_count: int
    passed_case_count: int
    expected_reference_count: int
    resolved_expected_count: int
    access_control_leakage_count: int

    @property
    def citation_recall(self) -> float:
        if self.expected_reference_count == 0:
            return 1.0
        return self.resolved_expected_count / self.expected_reference_count

    @property
    def passed(self) -> bool:
        return self.passed_case_count == self.case_count and self.access_control_leakage_count == 0


async def evaluate_retrieval(
    retriever: KnowledgeRetriever, cases: tuple[RetrievalEvaluationCase, ...]
) -> RetrievalEvaluationResult:
    resolved_expected = 0
    expected_total = 0
    leakage = 0
    passed_cases = 0
    for case in cases:
        result = await retriever.retrieve(case.request)
        returned = result.citation_references
        expected_total += len(case.expected_references)
        resolved_expected += len(returned & case.expected_references)
        case_leakage = len(returned & case.forbidden_references)
        leakage += case_leakage
        if case.expected_references <= returned and case_leakage == 0:
            passed_cases += 1
    return RetrievalEvaluationResult(
        case_count=len(cases),
        passed_case_count=passed_cases,
        expected_reference_count=expected_total,
        resolved_expected_count=resolved_expected,
        access_control_leakage_count=leakage,
    )
