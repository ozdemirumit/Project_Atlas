import { apiFetch } from "./client";
import type { ProtectedAnswerPresentationResult } from "./protectedAnswerPresentation";

export type ProtectedRecommendationCandidateResult = {
  candidate_set: {
    candidate_set_id: string;
    schema_version: "atlas.protected-recommendation-candidate-set.v1";
    version: 1;
    presentation_id: string;
    presentation_digest: string;
    answer_digest: string;
    adjudication_id: string;
    adjudication_digest: string;
    invocation_id: string;
    invocation_digest: string;
    context_id: string;
    context_digest: string;
    draft_digest: string;
    report_digest: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    generation_policy_id: string;
    generation_policy_digest: string;
    generation_policy_version: string;
    generator_id: string;
    generation_receipt_digest: string;
    candidate_content_digest: string;
    source_binding_digest: string;
    citation_set_digest: string;
    unknown_set_digest: string;
    safety_digest: string;
    cleanup_digest: string;
    candidate_categories: string[];
    maximum_capability_class: "C0" | "C1";
    candidate_count: number;
    step_count: number;
    citation_count: number;
    unknown_count: number;
    byte_count: number;
    generated_at: string;
    expires_at: string;
    instance_state: "protected_recommendation_candidates_generated";
    purpose: string;
    canonical_digest: string;
    recommendation_candidates_generated: true;
    service_impact_analyzed: false;
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
    candidate_set_id: string;
    presentation_id: string;
    adjudication_id: string;
    invocation_id: string;
    context_id: string;
    candidate_categories: string[];
    maximum_capability_class: "C0" | "C1";
    candidate_count: number;
    step_count: number;
    citation_count: number;
    unknown_count: number;
    byte_count: number;
    candidate_content_digest: string;
    source_binding_digest: string;
    citation_set_digest: string;
    unknown_set_digest: string;
    safety_digest: string;
    cleanup_digest: string;
    generated_at: string;
    expires_at: string;
  };
};

const forbiddenFields = [
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "generation_authorization_digest",
  "protected_candidate_reference",
  "candidates",
  "title",
  "expected_outcome",
  "steps",
  "capability_id",
  "command",
  "tool_call",
  "impact",
  "recovery",
  "preference",
];

function isSafeCandidateResult(
  value: unknown,
): value is { data: ProtectedRecommendationCandidateResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const candidateSet = result.candidate_set;
  const manifest = result.manifest;
  if (
    !candidateSet ||
    typeof candidateSet !== "object" ||
    !manifest ||
    typeof manifest !== "object"
  )
    return false;
  const record = candidateSet as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-recommendation-candidate-set.v1" &&
    record.recommendation_candidates_generated === true &&
    record.service_impact_analyzed === false &&
    record.recommendation_complete === false &&
    record.recommendation_presented === false &&
    record.recommendation_ready_for_review === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false &&
    typeof safeManifest.candidate_count === "number" &&
    Array.isArray(safeManifest.candidate_categories) &&
    forbiddenFields.every((field) => !(field in record) && !(field in safeManifest))
  );
}

export async function createProtectedRecommendationCandidates(input: {
  presentationResult: ProtectedAnswerPresentationResult;
  policyId: string;
  policyDigest: string;
}) {
  const { presentationResult, policyId, policyDigest } = input;
  const presentation = presentationResult.presentation;
  if (
    !presentation.answer_presented ||
    presentation.recommendation_generated ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact protected answer presentation is required");
  const response = await apiFetch(
    `/api/v1/ai/answer-presentations/${encodeURIComponent(presentation.presentation_id)}/recommendation-candidate-sets`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-recommendation-candidates.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-recommendation-candidate-input.v1",
        presentation_digest: presentation.canonical_digest,
        generation_policy_id: policyId,
        generation_policy_digest: policyDigest,
        purpose: presentation.purpose,
        acknowledged_candidates_are_incomplete: true,
        acknowledged_impact_and_recovery_are_unverified: true,
        acknowledged_no_recommendation_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Protected recommendation candidate generation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeCandidateResult(payload))
    throw new Error("Recommendation candidate generation returned protected content or authority");
  return payload;
}
