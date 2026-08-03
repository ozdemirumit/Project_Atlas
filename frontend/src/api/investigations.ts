export type EpistemicType =
  | "observation"
  | "retrieved_fact"
  | "calculated_finding"
  | "correlation"
  | "inference"
  | "hypothesis"
  | "assumption"
  | "unknown"
  | "recommendation";

export type InvestigationEvidence = {
  evidence_id: string;
  artifact_version: string;
  source_type: string;
  source_system: string;
  source_version: string;
  target_id: string;
  observed_at: string;
  applicable_from: string;
  applicable_to: string | null;
  freshness: "current" | "aging" | "stale" | "unknown";
  classification: string;
  authorization_reference: string;
  collection_method: string;
  summary: string;
  integrity: string;
  completeness: string;
  quality_limitations: string[];
  citation: string;
};

export type InvestigationClaim = {
  claim_id: string;
  epistemic_type: EpistemicType;
  text: string;
  scope: string;
  window_start: string;
  window_end: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  assumptions: string[];
  confidence: "insufficient" | "low" | "moderate" | "high";
  supporting_factors: string[];
  limiting_factors: string[];
  validation_state: string;
};

export type InvestigationArtifact = {
  artifact_id: string;
  version: number;
  prior_version_id: string | null;
  requested_by: string;
  created_at: string;
  organization_id: string;
  environment_id: string;
  site_id: string;
  target_id: string;
  question: string;
  intended_decision: string;
  window_start: string;
  window_end: string;
  evidence: InvestigationEvidence[];
  timeline: Array<{
    event_id: string;
    event_type: string;
    summary: string;
    occurred_at: string;
    observed_at: string;
    ingested_at: string;
    evidence_references: string[];
    clock_quality: string;
  }>;
  claims: InvestigationClaim[];
  hypotheses: Array<{
    hypothesis_id: string;
    statement: string;
    state: string;
    expected_consequences: string[];
    supporting_evidence: string[];
    contradicting_evidence: string[];
    assumptions: string[];
    confidence: string;
    confidence_rationale: string;
    limiting_factors: string[];
    discriminating_checks: Array<{
      check_id: string;
      title: string;
      rationale: string;
      capability_id: string;
      capability_class: string;
      target_id: string;
      expected_if_supported: string;
      expected_if_not_supported: string;
      timeout_seconds: number;
      stop_condition: string;
    }>;
  }>;
  assumptions: string[];
  unknowns: string[];
  conflicts: string[];
  excluded_evidence: string[];
  stop_reason: string;
  recommended_next_evidence: string[];
  component_versions: string[];
  summary: {
    known: string[];
    inferred: string[];
    alternatives: string[];
    unknowns: string[];
    confidence: string;
    confidence_rationale: string;
    safest_next_check: string;
    supported_decision: string;
    unsupported_decision: string;
  };
  data_profile: string;
  root_cause_confirmed: boolean;
  outage_confirmed: boolean;
  safety_notice: string;
};

type InvestigationResponse = {
  data: InvestigationArtifact;
  meta: { correlation_id: string; generated_at: string };
};

export async function createStorageInvestigation(
  targetId: string,
  question: string,
): Promise<InvestigationResponse> {
  const windowEnd = new Date();
  const windowStart = new Date(windowEnd.getTime() - 24 * 60 * 60 * 1000);
  const response = await fetch(`/api/v1/investigations/storage/${encodeURIComponent(targetId)}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      intended_decision: "Decide which safe read-only evidence to collect next.",
      window_start: windowStart.toISOString(),
      window_end: windowEnd.toISOString(),
      max_evidence_records: 12,
    }),
  });
  if (!response.ok) {
    throw new Error(`Investigation request failed with ${response.status}`);
  }
  return (await response.json()) as InvestigationResponse;
}
