import { apiFetch } from "./client";
import type {
  PresentedRecommendationOption,
  ProtectedRecommendationPresentationResult,
} from "./protectedRecommendationPresentations";

export type RecommendationPromotionResult = {
  recommendation: {
    promotion_id: string;
    recommendation_id: string;
    schema_version: "atlas.promoted-recommendation-artifact.v1";
    version: 1;
    presentation_id: string;
    adjudication_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    promotion_policy_id: string;
    promotion_policy_version: string;
    promoter_id: string;
    outcome: "preferred" | "tie" | "no_support";
    headline: string;
    safety_notice: string;
    options: PresentedRecommendationOption[];
    evidence_needs: string[];
    state: "draft";
    promoted_at: string;
    expires_at: string;
    purpose: string;
    byte_count: number;
    canonical_digest: string;
    recommendation_promoted: true;
    recommendation_ready_for_review: false;
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
    promotion_id: string;
    recommendation_id: string;
    presentation_id: string;
    adjudication_id: string;
    outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    state: "draft";
    promoted_at: string;
    expires_at: string;
    safety_notice: string;
  };
};

const forbiddenFields = new Set([
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "promotion_authorization_digest",
  "source_binding_digest",
  "promotion_receipt_digest",
  "candidate_id",
  "capability_id",
  "entity_id",
  "entity_ids",
  "relationship_id",
  "relationship_ids",
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

function isSafePromotionResult(value: unknown): value is { data: RecommendationPromotionResult } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const recommendation = (data as Record<string, unknown>).recommendation as
    | Record<string, unknown>
    | undefined;
  const options = recommendation?.options;
  return (
    recommendation?.schema_version === "atlas.promoted-recommendation-artifact.v1" &&
    recommendation.state === "draft" &&
    recommendation.recommendation_promoted === true &&
    recommendation.recommendation_ready_for_review === false &&
    recommendation.human_review_completed === false &&
    recommendation.recommendation_approved === false &&
    recommendation.workflow_created === false &&
    recommendation.itsm_record_created === false &&
    recommendation.execution_authorized === false &&
    recommendation.deployment_authorized === false &&
    recommendation.infrastructure_mutated === false &&
    Array.isArray(options) &&
    options.length > 0
  );
}

export async function createRecommendationPromotion(input: {
  presentationResult: ProtectedRecommendationPresentationResult;
  policyId: string;
  policyDigest: string;
}) {
  const { presentationResult, policyId, policyDigest } = input;
  const presentation = presentationResult.presentation;
  if (
    !presentation.recommendation_presented ||
    presentation.recommendation_ready_for_review ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact protected recommendation presentation is required");
  const response = await apiFetch(
    `/api/v1/recommendation-presentations/${encodeURIComponent(presentation.presentation_id)}/promotions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-promotion.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-promotion-input.v1",
        presentation_digest: presentation.canonical_digest,
        promotion_policy_id: policyId,
        promotion_policy_digest: policyDigest,
        purpose: presentation.purpose,
        acknowledged_draft_only: true,
        acknowledged_no_review_or_approval: true,
        acknowledged_no_operational_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Recommendation promotion failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafePromotionResult(payload))
    throw new Error("Recommendation promotion returned protected content or authority");
  return payload;
}
