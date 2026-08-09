import { apiFetch } from "./client";
import type { RecommendationReadinessResult } from "./recommendationReadiness";

export type RecommendationReviewRequestResult = {
  request: {
    review_request_id: string;
    recommendation_id: string;
    schema_version: "atlas.recommendation-review-request.v1";
    version: 1;
    readiness_assessment_id: string;
    promotion_id: string;
    presentation_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    review_request_policy_id: string;
    review_request_policy_version: string;
    orchestrator_id: string;
    source_outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    track_codes: string[];
    queue_ids: string[];
    track_statuses: [string, "awaiting_reviewer"][];
    routing_profile: string;
    sla_class: string;
    manifest_digest: string;
    state: "review_requested";
    requested_at: string;
    expires_at: string;
    purpose: string;
    canonical_digest: string;
    review_requested: true;
    reviewer_assigned: false;
    content_inspection_opened: false;
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
    review_request_id: string;
    recommendation_id: string;
    readiness_assessment_id: string;
    promotion_id: string;
    source_outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    track_codes: string[];
    queue_ids: string[];
    track_statuses: [string, "awaiting_reviewer"][];
    routing_profile: string;
    sla_class: string;
    state: "review_requested";
    requested_at: string;
    expires_at: string;
    review_requested: true;
  };
};

const forbiddenFields = new Set([
  "claim_id",
  "requester_subject_digest",
  "browser_session_binding_digest",
  "review_request_receipt_digest",
  "review_request_authorization_digest",
  "source_assessment_digest",
  "source_recommendation_digest",
  "source_binding_digest",
  "review_request_policy_digest",
  "reviewer_id",
  "decision",
  "approval",
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

function isSafeReviewRequestResult(
  value: unknown,
): value is { data: RecommendationReviewRequestResult } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const request = (data as Record<string, unknown>).request as Record<string, unknown> | undefined;
  return (
    request?.schema_version === "atlas.recommendation-review-request.v1" &&
    request.state === "review_requested" &&
    request.review_requested === true &&
    request.reviewer_assigned === false &&
    request.content_inspection_opened === false &&
    request.human_review_completed === false &&
    request.recommendation_approved === false &&
    request.workflow_created === false &&
    request.itsm_record_created === false &&
    request.execution_authorized === false &&
    request.deployment_authorized === false &&
    request.infrastructure_mutated === false
  );
}

export async function createRecommendationReviewRequest(input: {
  readinessResult: RecommendationReadinessResult;
  recommendationDigest: string;
  policyId: string;
  policyDigest: string;
}) {
  const { readinessResult, recommendationDigest, policyId, policyDigest } = input;
  const assessment = readinessResult.assessment;
  if (
    assessment.state !== "ready_for_review" ||
    !assessment.recommendation_ready_for_review ||
    !/^[a-f0-9]{64}$/.test(recommendationDigest) ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact ready recommendation assessment is required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(assessment.recommendation_id)}/human-review-requests`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-review-request.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-review-request-input.v1",
        recommendation_digest: recommendationDigest,
        readiness_assessment_id: assessment.assessment_id,
        readiness_assessment_digest: assessment.canonical_digest,
        review_request_policy_id: policyId,
        review_request_policy_digest: policyDigest,
        purpose: assessment.purpose,
        acknowledged_request_is_not_assignment_or_review: true,
        acknowledged_routing_is_policy_owned: true,
        acknowledged_no_approval_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation human-review request failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReviewRequestResult(payload))
    throw new Error("Recommendation review request returned protected content or authority");
  return payload;
}
