import type { InvestigationEvidence } from "./investigations";

export type RcaDiagnosticStep = {
  step_id: string;
  question: string;
  target_id: string;
  scope: string;
  capability_id: string;
  capability_class: "C0" | "C1";
  evidence_source: string;
  preconditions: string[];
  expected_duration_seconds: number;
  expected_load: string;
  max_output_records: number;
  expected_if_supported: string;
  expected_if_not_supported: string;
  timeout_seconds: number;
  stop_condition: string;
  required_role: string;
  policy_reference: string;
  approval_required: boolean;
  classification: string;
  retention: string;
  supported_branch: string;
  unsupported_branch: string;
};

export type RcaCase = {
  case_id: string;
  version: number;
  prior_version_id: string | null;
  owner: string;
  requested_by: string;
  state: "provisional" | "inconclusive" | "reviewed";
  severity: "warning" | "critical" | "unknown";
  created_at: string;
  updated_at: string;
  incident_references: Array<{
    reference_type: string;
    reference_id: string;
    authority: string;
  }>;
  user_report: string;
  expected_behavior: string;
  actual_behavior: string;
  target_id: string;
  fault_families: string[];
  symptoms: Array<{
    symptom_id: string;
    statement: string;
    first_observed_at: string;
    current_state: string;
    evidence_references: string[];
  }>;
  impact_scope: {
    affected_entities: string[];
    possibly_affected_services: string[];
    explicitly_unaffected_entities: string[];
    current_impact: string;
    business_criticality: string;
    impact_confirmed: boolean;
    limitations: string[];
  };
  source_investigation_artifact_id: string;
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
  hypotheses: Array<{
    hypothesis_id: string;
    rank: number;
    fault_family: string;
    cause_type: string;
    statement: string;
    mechanism: string;
    expected_affected_entities: string[];
    expected_unaffected_entities: string[];
    expected_sequence: string[];
    supporting_evidence: string[];
    contradicting_evidence: string[];
    missing_expected_observations: string[];
    confounders: string[];
    assumptions: string[];
    confirmation_level: string;
    confidence_rationale: string;
    diagnostic_steps: RcaDiagnosticStep[];
  }>;
  evidence_gaps: string[];
  blocker: string;
  safest_next_step: string;
  provisional_statement: {
    statement: string;
    confirmation_level: string;
    supporting_evidence: string[];
    contradicting_evidence: string[];
    residual_uncertainty: string[];
    alternatives_not_ruled_out: string[];
    prevention_or_verification_implication: string;
  };
  human_review: {
    status: "pending" | "accepted" | "disputed" | "corrected";
    reviewer_id: string | null;
    reviewed_at: string | null;
    decision_reason: string | null;
    domain_confirmation_criterion: string | null;
  };
  data_profile: string;
  root_cause_confirmed: boolean;
  safety_notice: string;
};

type RcaResponse = {
  data: RcaCase;
  meta: { correlation_id: string; generated_at: string };
};

export async function createStorageRca(
  targetId: string,
  actualBehavior: string,
): Promise<RcaResponse> {
  const windowEnd = new Date();
  const windowStart = new Date(windowEnd.getTime() - 24 * 60 * 60 * 1000);
  const response = await fetch(`/api/v1/rca/storage/${encodeURIComponent(targetId)}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      incident_id: `INC-LOCAL-${targetId.split(".").at(-1)?.toUpperCase() ?? "STORAGE"}`,
      user_report: actualBehavior,
      expected_behavior: "Storage paths and controllers remain healthy and redundant.",
      actual_behavior: actualBehavior,
      window_start: windowStart.toISOString(),
      window_end: windowEnd.toISOString(),
      max_evidence_records: 12,
    }),
  });
  if (!response.ok) {
    throw new Error(`RCA request failed with ${response.status}`);
  }
  return (await response.json()) as RcaResponse;
}
