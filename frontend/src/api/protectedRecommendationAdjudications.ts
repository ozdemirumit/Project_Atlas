import { apiFetch } from "./client";
import type { ProtectedCandidateRiskRecoveryResult } from "./protectedCandidateRiskRecovery";

export type ProtectedRecommendationAdjudicationResult = {
  adjudication: {
    adjudication_id: string;
    schema_version: "atlas.protected-recommendation-adjudication.v1";
    version: 1;
    completion_id: string;
    completion_digest: string;
    impact_analysis_id: string;
    candidate_set_id: string;
    candidate_set_digest: string;
    presentation_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    adjudication_policy_id: string;
    adjudication_policy_digest: string;
    adjudication_policy_version: string;
    adjudicator_id: string;
    adjudication_receipt_digest: string;
    candidate_count: number;
    dimension_count: number;
    eligible_count: number;
    excluded_count: number;
    preferred_count: number;
    alternative_count: number;
    tie: boolean;
    no_supportable_candidate: boolean;
    maximum_risk: "low" | "moderate" | "high" | "critical" | "unknown";
    interruption_possible_count: number;
    recovery_feasible_count: number;
    gap_count: number;
    unknown_count: number;
    comparison_digest: string;
    eligibility_digest: string;
    exclusion_digest: string;
    preference_digest: string;
    safety_digest: string;
    cleanup_digest: string;
    byte_count: number;
    adjudicated_at: string;
    expires_at: string;
    instance_state: "protected_recommendation_adjudicated";
    purpose: string;
    safety_notice: string;
    canonical_digest: string;
    service_impact_analyzed: true;
    impact_complete: true;
    interruption_established: true;
    duration_established: true;
    risk_completed: true;
    recovery_completed: true;
    recommendation_complete: true;
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
    adjudication_id: string;
    completion_id: string;
    candidate_set_id: string;
    candidate_count: number;
    dimension_count: number;
    eligible_count: number;
    excluded_count: number;
    preferred_count: number;
    alternative_count: number;
    tie: boolean;
    no_supportable_candidate: boolean;
    maximum_risk: "low" | "moderate" | "high" | "critical" | "unknown";
    interruption_possible_count: number;
    recovery_feasible_count: number;
    gap_count: number;
    unknown_count: number;
    comparison_digest: string;
    eligibility_digest: string;
    exclusion_digest: string;
    preference_digest: string;
    safety_digest: string;
    adjudicated_at: string;
    expires_at: string;
    safety_notice: string;
  };
};

const forbiddenFields = [
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "adjudication_authorization_digest",
  "protected_report_digest",
  "candidate_entries",
  "candidate_id",
  "preferred_candidate_id",
  "category",
  "dimensions",
  "comparison_values",
  "exclusion_reasons",
  "preference_rationale",
];

function isSafeAdjudicationResult(
  value: unknown,
): value is { data: ProtectedRecommendationAdjudicationResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const adjudication = result.adjudication;
  const manifest = result.manifest;
  if (
    !adjudication ||
    typeof adjudication !== "object" ||
    !manifest ||
    typeof manifest !== "object"
  )
    return false;
  const record = adjudication as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-recommendation-adjudication.v1" &&
    record.service_impact_analyzed === true &&
    record.impact_complete === true &&
    record.interruption_established === true &&
    record.duration_established === true &&
    record.risk_completed === true &&
    record.recovery_completed === true &&
    record.recommendation_complete === true &&
    record.recommendation_presented === false &&
    record.recommendation_ready_for_review === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false &&
    typeof safeManifest.candidate_count === "number" &&
    typeof safeManifest.dimension_count === "number" &&
    typeof safeManifest.tie === "boolean" &&
    typeof safeManifest.no_supportable_candidate === "boolean" &&
    typeof safeManifest.safety_notice === "string" &&
    forbiddenFields.every((field) => !(field in record) && !(field in safeManifest))
  );
}

export async function createProtectedRecommendationAdjudication(input: {
  completionResult: ProtectedCandidateRiskRecoveryResult;
  policyId: string;
  policyDigest: string;
}) {
  const { completionResult, policyId, policyDigest } = input;
  const completion = completionResult.completion;
  if (
    !completion.risk_completed ||
    !completion.recovery_completed ||
    completion.recommendation_complete ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact protected risk-recovery completion is required");
  const response = await apiFetch(
    `/api/v1/ai/candidate-risk-recovery-completions/${encodeURIComponent(completion.completion_id)}/adjudications`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-recommendation-adjudication.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-recommendation-adjudication-input.v1",
        completion_digest: completion.canonical_digest,
        adjudication_policy_id: policyId,
        adjudication_policy_digest: policyDigest,
        purpose: completion.purpose,
        acknowledged_preference_is_not_approval: true,
        acknowledged_tie_or_no_support_is_valid: true,
        acknowledged_no_presentation_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Protected recommendation adjudication failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeAdjudicationResult(payload))
    throw new Error("Recommendation adjudication returned protected content or authority");
  return payload;
}
