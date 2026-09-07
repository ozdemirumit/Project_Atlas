"""ATLAS-047 SS31: Observability."""

from __future__ import annotations

from enum import StrEnum


class GuardrailMetricCategory(StrEnum):
    """SS31's nine named metric categories. "Metrics exclude raw secrets and unauthorized
    content" (SS31) is an operational property of whatever emits these, not something a category
    label alone can enforce -- so it isn't restated here as a hardcoded-`False` function; it's
    the same guarantee `GUARDRAIL_INVARIANT_SUMMARIES[GRD-010]` already names."""

    DECISIONS_BY_DIMENSION = "decisions_by_dimension"
    INJECTION_DLP_SECRET_SIGNALS = "injection_dlp_secret_signals"
    APPEAL_AND_OVERTURN_RATES = "appeal_and_overturn_rates"
    OUTPUT_REPAIR_AND_REJECTION = "output_repair_and_rejection"
    TOOL_DENIAL_AND_MISMATCH = "tool_denial_and_mismatch"
    SERVICE_AVAILABILITY_AND_LATENCY = "service_availability_and_latency"
    ACTIVE_EXCEPTIONS = "active_exceptions"
    GENERATED_ARTIFACT_VALIDATION = "generated_artifact_validation"
    CONTROL_DRIFT_AND_COVERAGE = "control_drift_and_coverage"
