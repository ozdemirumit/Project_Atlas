import { apiFetch } from "./client";
import type { ProtectedCandidateImpactResult } from "./protectedCandidateImpacts";

export type ProtectedCandidateRiskRecoveryResult = {
  completion: {
    completion_id: string;
    schema_version: "atlas.protected-candidate-risk-recovery-completion.v1";
    version: 1;
    impact_analysis_id: string;
    impact_digest: string;
    candidate_set_id: string;
    presentation_id: string;
    environment_id: string;
    completion_policy_id: string;
    completion_policy_digest: string;
    completion_policy_version: string;
    assessor_id: string;
    evidence_snapshot_id: string;
    evidence_snapshot_digest: string;
    evidence_snapshot_generated_at: string;
    evidence_freshness: string;
    evidence_completeness: string;
    candidate_count: number;
    evidence_item_count: number;
    low_risk_count: number;
    moderate_risk_count: number;
    high_risk_count: number;
    critical_risk_count: number;
    unknown_risk_count: number;
    maximum_risk: "low" | "moderate" | "high" | "critical" | "unknown";
    interruption_possible_count: number;
    recovery_feasible_count: number;
    recovery_unknown_count: number;
    recovery_blocked_count: number;
    work_minimum_minutes: number;
    work_maximum_minutes: number;
    interruption_minimum_minutes: number;
    interruption_maximum_minutes: number;
    recovery_minimum_minutes: number;
    recovery_maximum_minutes: number;
    gap_count: number;
    unknown_count: number;
    completed_at: string;
    expires_at: string;
    instance_state: "protected_candidate_risk_recovery_completed";
    purpose: string;
    safety_notice: string;
    canonical_digest: string;
    service_impact_analyzed: true;
    impact_complete: true;
    outage_confirmed: false;
    interruption_established: true;
    duration_established: true;
    risk_completed: true;
    recovery_completed: true;
    recommendation_complete: false;
    recommendation_presented: false;
    recommendation_ready_for_review: false;
    recommendation_approved: false;
    workflow_created: false;
    execution_authorized: false;
    deployment_authorized: false;
    infrastructure_mutated: false;
    reused: boolean;
  };
  manifest: {
    completion_id: string;
    impact_analysis_id: string;
    candidate_set_id: string;
    presentation_id: string;
    evidence_snapshot_id: string;
    evidence_snapshot_digest: string;
    evidence_snapshot_generated_at: string;
    evidence_freshness: string;
    evidence_completeness: string;
    candidate_count: number;
    evidence_item_count: number;
    low_risk_count: number;
    moderate_risk_count: number;
    high_risk_count: number;
    critical_risk_count: number;
    unknown_risk_count: number;
    maximum_risk: "low" | "moderate" | "high" | "critical" | "unknown";
    interruption_possible_count: number;
    recovery_feasible_count: number;
    recovery_unknown_count: number;
    recovery_blocked_count: number;
    work_minimum_minutes: number;
    work_maximum_minutes: number;
    interruption_minimum_minutes: number;
    interruption_maximum_minutes: number;
    recovery_minimum_minutes: number;
    recovery_maximum_minutes: number;
    gap_count: number;
    unknown_count: number;
    safety_notice: string;
  };
};

const forbiddenFields = [
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "completion_authorization_digest",
  "protected_report_digest",
  "risk_dimensions",
  "candidate_entries",
  "candidate_id",
  "evidence_references",
  "trigger_conditions",
  "point_of_no_return",
  "recovery_strategy",
];

function isSafeCompletionResult(
  value: unknown,
): value is { data: ProtectedCandidateRiskRecoveryResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const completion = result.completion;
  const manifest = result.manifest;
  if (!completion || typeof completion !== "object" || !manifest || typeof manifest !== "object")
    return false;
  const record = completion as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-candidate-risk-recovery-completion.v1" &&
    record.service_impact_analyzed === true &&
    record.impact_complete === true &&
    record.outage_confirmed === false &&
    record.interruption_established === true &&
    record.duration_established === true &&
    record.risk_completed === true &&
    record.recovery_completed === true &&
    record.recommendation_complete === false &&
    record.recommendation_presented === false &&
    record.recommendation_ready_for_review === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false &&
    typeof safeManifest.maximum_risk === "string" &&
    typeof safeManifest.work_maximum_minutes === "number" &&
    typeof safeManifest.safety_notice === "string" &&
    forbiddenFields.every((field) => !(field in record) && !(field in safeManifest))
  );
}

export async function createProtectedCandidateRiskRecovery(input: {
  impactResult: ProtectedCandidateImpactResult;
  policyId: string;
  policyDigest: string;
}) {
  const { impactResult, policyId, policyDigest } = input;
  const impact = impactResult.impact_analysis;
  if (
    !impact.service_impact_analyzed ||
    impact.impact_complete ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact protected candidate impact analysis is required");
  const response = await apiFetch(
    `/api/v1/ai/candidate-impact-analyses/${encodeURIComponent(impact.impact_analysis_id)}/risk-recovery-completions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-candidate-risk-recovery.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-candidate-risk-recovery-input.v1",
        impact_digest: impact.canonical_digest,
        completion_policy_id: policyId,
        completion_policy_digest: policyDigest,
        purpose: impact.purpose,
        acknowledged_estimates_are_not_guarantees: true,
        acknowledged_unknowns_cannot_lower_risk: true,
        acknowledged_no_preference_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Protected candidate risk-recovery completion failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeCompletionResult(payload))
    throw new Error("Risk-recovery completion returned protected content or authority");
  return payload;
}
