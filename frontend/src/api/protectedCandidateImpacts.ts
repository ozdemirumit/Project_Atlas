import { apiFetch } from "./client";
import type { ProtectedRecommendationCandidateResult } from "./protectedRecommendationCandidates";

export type ProtectedCandidateImpactResult = {
  impact_analysis: {
    impact_analysis_id: string;
    schema_version: "atlas.protected-candidate-impact-analysis.v1";
    version: 1;
    candidate_set_id: string;
    candidate_set_digest: string;
    presentation_id: string;
    answer_digest: string;
    adjudication_id: string;
    invocation_id: string;
    context_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    impact_policy_id: string;
    impact_policy_digest: string;
    impact_policy_version: string;
    analyzer_id: string;
    analysis_receipt_digest: string;
    graph_snapshot_id: string;
    graph_snapshot_digest: string;
    graph_snapshot_generated_at: string;
    graph_freshness: string;
    graph_completeness: string;
    graph_maturity: string;
    coverage_digest: string;
    graph_gap_digest: string;
    unknown_digest: string;
    safety_digest: string;
    cleanup_digest: string;
    candidate_count: number;
    path_count: number;
    modeled_entity_count: number;
    technical_service_count: number;
    business_service_count: number;
    gap_count: number;
    unknown_count: number;
    byte_count: number;
    analyzed_at: string;
    expires_at: string;
    instance_state: "protected_candidate_service_impact_analyzed";
    purpose: string;
    safety_notice: string;
    canonical_digest: string;
    service_impact_analyzed: true;
    impact_complete: false;
    outage_confirmed: false;
    interruption_established: false;
    duration_established: false;
    risk_completed: false;
    recovery_completed: false;
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
    impact_analysis_id: string;
    candidate_set_id: string;
    presentation_id: string;
    graph_snapshot_id: string;
    graph_snapshot_digest: string;
    graph_snapshot_generated_at: string;
    graph_freshness: string;
    graph_completeness: string;
    graph_maturity: string;
    candidate_count: number;
    path_count: number;
    modeled_entity_count: number;
    technical_service_count: number;
    business_service_count: number;
    gap_count: number;
    unknown_count: number;
    coverage_digest: string;
    graph_gap_digest: string;
    unknown_digest: string;
    safety_digest: string;
    analyzed_at: string;
    expires_at: string;
    safety_notice: string;
  };
};

const forbiddenFields = [
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "impact_authorization_digest",
  "protected_report_digest",
  "candidate_source_binding_digest",
  "paths",
  "entities",
  "services",
  "known_gaps",
  "unknowns",
  "evidence_references",
  "candidate_id",
  "candidate_content",
];

function isSafeImpactResult(value: unknown): value is { data: ProtectedCandidateImpactResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const impact = result.impact_analysis;
  const manifest = result.manifest;
  if (!impact || typeof impact !== "object" || !manifest || typeof manifest !== "object")
    return false;
  const record = impact as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-candidate-impact-analysis.v1" &&
    record.service_impact_analyzed === true &&
    record.impact_complete === false &&
    record.outage_confirmed === false &&
    record.interruption_established === false &&
    record.duration_established === false &&
    record.risk_completed === false &&
    record.recovery_completed === false &&
    record.recommendation_complete === false &&
    record.recommendation_presented === false &&
    record.recommendation_ready_for_review === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false &&
    typeof safeManifest.path_count === "number" &&
    typeof safeManifest.modeled_entity_count === "number" &&
    typeof safeManifest.safety_notice === "string" &&
    forbiddenFields.every((field) => !(field in record) && !(field in safeManifest))
  );
}

export async function createProtectedCandidateImpact(input: {
  candidateResult: ProtectedRecommendationCandidateResult;
  policyId: string;
  policyDigest: string;
}) {
  const { candidateResult, policyId, policyDigest } = input;
  const candidateSet = candidateResult.candidate_set;
  if (
    !candidateSet.recommendation_candidates_generated ||
    candidateSet.service_impact_analyzed ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact protected recommendation candidate set is required");
  const response = await apiFetch(
    `/api/v1/ai/recommendation-candidate-sets/${encodeURIComponent(candidateSet.candidate_set_id)}/impact-analyses`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-candidate-impact.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-candidate-impact-input.v1",
        candidate_set_digest: candidateSet.candidate_content_digest,
        impact_policy_id: policyId,
        impact_policy_digest: policyDigest,
        purpose: candidateSet.purpose,
        acknowledged_reachability_is_not_outage_evidence: true,
        acknowledged_impact_remains_provisional: true,
        acknowledged_no_recommendation_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Protected candidate impact enrichment failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeImpactResult(payload))
    throw new Error("Candidate impact enrichment returned protected content or authority");
  return payload;
}
