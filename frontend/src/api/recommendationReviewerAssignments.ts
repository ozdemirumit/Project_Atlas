import { apiFetch } from "./client";
import type { RecommendationReviewRequestResult } from "./recommendationReviewRequests";

export type RecommendationReviewerAssignmentResult = {
  assignment: {
    assignment_set_id: string;
    review_request_id: string;
    recommendation_id: string;
    schema_version: "atlas.recommendation-reviewer-assignment.v1";
    version: 1;
    readiness_assessment_id: string;
    promotion_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    assignment_policy_id: string;
    assignment_policy_version: string;
    assignment_adapter_id: string;
    source_outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    track_assignments: [string, string, string, string, "assigned"][];
    manifest_digest: string;
    state: "reviewers_assigned";
    assigned_at: string;
    expires_at: string;
    purpose: string;
    canonical_digest: string;
    review_requested: true;
    reviewer_assigned: true;
    immutable_assignments_confirmed: true;
    encrypted_identity_references: true;
    transient_identity_buffers_erased: true;
    directory_channel_closed: true;
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
    assignment_set_id: string;
    review_request_id: string;
    recommendation_id: string;
    track_assignments: [string, string, string, string, "assigned"][];
    state: "reviewers_assigned";
    assigned_at: string;
    expires_at: string;
    reviewer_assigned: true;
  };
};

const forbiddenFields = new Set([
  "claim_id",
  "requester_subject_digest",
  "browser_session_binding_digest",
  "assignment_policy_digest",
  "assignment_receipt_digest",
  "source_review_request_digest",
  "source_binding_digest",
  "routing_digest",
  "eligibility_digest",
  "separation_digest",
  "artifact_digest",
  "directory_source_id",
  "directory_source_digest",
  "reviewer_id",
  "reviewer_name",
  "reviewer_email",
  "decision",
  "approval",
  "command",
  "tool_call",
]);

function hasForbiddenField(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenField);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) => forbiddenFields.has(key) || hasForbiddenField(child),
  );
}

function isTrackAssignment(value: unknown): value is [string, string, string, string, "assigned"] {
  return (
    Array.isArray(value) &&
    value.length === 5 &&
    value.slice(0, 4).every((item) => typeof item === "string") &&
    /^[a-f0-9]{64}$/.test(value[3] as string) &&
    value[4] === "assigned"
  );
}

function isSafeReviewerAssignmentResult(
  value: unknown,
): value is { data: RecommendationReviewerAssignmentResult } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const assignment = (data as Record<string, unknown>).assignment as
    | Record<string, unknown>
    | undefined;
  const tracks = assignment?.track_assignments;
  const trackItems = Array.isArray(tracks) ? (tracks as unknown[]) : [];
  const firstTrack: unknown = trackItems[0];
  const secondTrack: unknown = trackItems[1];
  return (
    assignment?.schema_version === "atlas.recommendation-reviewer-assignment.v1" &&
    assignment.state === "reviewers_assigned" &&
    assignment.review_requested === true &&
    assignment.reviewer_assigned === true &&
    assignment.immutable_assignments_confirmed === true &&
    assignment.encrypted_identity_references === true &&
    assignment.transient_identity_buffers_erased === true &&
    assignment.directory_channel_closed === true &&
    assignment.content_inspection_opened === false &&
    assignment.human_review_completed === false &&
    assignment.recommendation_approved === false &&
    assignment.workflow_created === false &&
    assignment.itsm_record_created === false &&
    assignment.execution_authorized === false &&
    assignment.deployment_authorized === false &&
    assignment.infrastructure_mutated === false &&
    Array.isArray(tracks) &&
    tracks.length === 2 &&
    tracks.every(isTrackAssignment) &&
    isTrackAssignment(firstTrack) &&
    isTrackAssignment(secondTrack) &&
    firstTrack[0] === "review-track.technical" &&
    secondTrack[0] === "review-track.service-impact" &&
    firstTrack[3] !== secondTrack[3]
  );
}

export async function createRecommendationReviewerAssignment(input: {
  reviewRequestResult: RecommendationReviewRequestResult;
  policyId: string;
  policyDigest: string;
}) {
  const { reviewRequestResult, policyId, policyDigest } = input;
  const request = reviewRequestResult.request;
  if (
    request.state !== "review_requested" ||
    !request.review_requested ||
    request.reviewer_assigned ||
    request.content_inspection_opened ||
    request.human_review_completed ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact unassigned recommendation review request is required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(request.recommendation_id)}/reviewer-assignments`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-reviewer-assignment.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-reviewer-assignment-input.v1",
        review_request_id: request.review_request_id,
        review_request_digest: request.canonical_digest,
        assignment_policy_id: policyId,
        assignment_policy_digest: policyDigest,
        purpose: request.purpose,
        acknowledged_caller_cannot_select_reviewers: true,
        acknowledged_distinct_reviewers_required: true,
        acknowledged_no_inspection_decision_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation reviewer assignment failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReviewerAssignmentResult(payload))
    throw new Error("Recommendation reviewer assignment returned unsafe metadata");
  if (
    payload.data.assignment.review_request_id !== request.review_request_id ||
    payload.data.assignment.recommendation_id !== request.recommendation_id ||
    payload.data.assignment.readiness_assessment_id !== request.readiness_assessment_id ||
    payload.data.assignment.promotion_id !== request.promotion_id ||
    payload.data.assignment.assignment_policy_id !== policyId
  )
    throw new Error("Reviewer assignment does not match the exact governed review request");
  return payload;
}
