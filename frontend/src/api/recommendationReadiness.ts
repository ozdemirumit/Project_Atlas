import { apiFetch } from "./client";
import type { RecommendationPromotionResult } from "./recommendationPromotions";

export type RecommendationReadinessResult = {
  assessment: {
    assessment_id: string;
    recommendation_id: string;
    schema_version: "atlas.recommendation-readiness-assessment.v1";
    version: 1;
    promotion_id: string;
    presentation_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    readiness_policy_id: string;
    readiness_policy_version: string;
    evaluator_id: string;
    source_outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    evaluation_outcome: "ready" | "blocked";
    reason_codes: string[];
    check_count: number;
    passed_check_count: number;
    state: "ready_for_review" | "blocked";
    assessed_at: string;
    expires_at: string;
    purpose: string;
    canonical_digest: string;
    recommendation_ready_for_review: boolean;
    human_review_completed: false;
    recommendation_approved: false;
    workflow_created: false;
    itsm_record_created: false;
    execution_authorized: false;
    deployment_authorized: false;
    infrastructure_mutated: false;
    reused: boolean;
  };
  manifest: {
    assessment_id: string;
    recommendation_id: string;
    promotion_id: string;
    source_outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    evaluation_outcome: "ready" | "blocked";
    reason_codes: string[];
    check_count: number;
    passed_check_count: number;
    state: "ready_for_review" | "blocked";
    assessed_at: string;
    expires_at: string;
    recommendation_ready_for_review: boolean;
  };
};

const forbiddenFields = new Set([
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "readiness_receipt_digest",
  "readiness_authorization_digest",
  "source_artifact_digest",
  "source_binding_digest",
  "readiness_policy_digest",
  "reviewer_id",
  "command",
  "endpoint",
  "tool_call",
]);

function hasForbiddenField(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenField);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) => forbiddenFields.has(key) || hasForbiddenField(child),
  );
}

function isSafeReadinessResult(value: unknown): value is { data: RecommendationReadinessResult } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const assessment = (data as Record<string, unknown>).assessment as
    | Record<string, unknown>
    | undefined;
  return (
    assessment?.schema_version === "atlas.recommendation-readiness-assessment.v1" &&
    (assessment.state === "ready_for_review" || assessment.state === "blocked") &&
    assessment.human_review_completed === false &&
    assessment.recommendation_approved === false &&
    assessment.workflow_created === false &&
    assessment.itsm_record_created === false &&
    assessment.execution_authorized === false &&
    assessment.deployment_authorized === false &&
    assessment.infrastructure_mutated === false
  );
}

export async function createRecommendationReadiness(input: {
  promotionResult: RecommendationPromotionResult;
  policyId: string;
  policyDigest: string;
}) {
  const { promotionResult, policyId, policyDigest } = input;
  const recommendation = promotionResult.recommendation;
  if (
    !recommendation.recommendation_promoted ||
    recommendation.recommendation_ready_for_review ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact promoted recommendation draft is required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(recommendation.recommendation_id)}/review-readiness-assessments`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-readiness.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-readiness-input.v1",
        recommendation_digest: recommendation.canonical_digest,
        readiness_policy_id: policyId,
        readiness_policy_digest: policyDigest,
        purpose: recommendation.purpose,
        acknowledged_readiness_is_not_review: true,
        acknowledged_blocked_requires_new_version: true,
        acknowledged_no_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation review-readiness assessment failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReadinessResult(payload))
    throw new Error("Recommendation readiness returned protected content or authority");
  return payload;
}
