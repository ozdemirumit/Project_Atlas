import { apiFetch } from "./client";
import type { RecommendationReviewerAssignmentResult } from "./recommendationReviewerAssignments";

export type RecommendationInspectionTrack =
  | "review-track.technical"
  | "review-track.service-impact";

export type RecommendationProtectedInspection = {
  lease_id: string;
  schema_version: "atlas.recommendation-protected-inspection-lease.v1";
  version: 1;
  source_assignment_set_id: string;
  recommendation_id: string;
  review_request_id: string;
  readiness_assessment_id: string;
  promotion_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  source_outcome: "preferred" | "tie" | "no_support";
  option_count: number;
  preferred_count: number;
  track_code: RecommendationInspectionTrack;
  opaque_assignment_id: string;
  lease_holder_subject_digest: string;
  lease_digest: string;
  assignment_binding_digest: string;
  policy_binding_digest: string;
  cleanup_digest: string;
  inspection_policy_id: string;
  inspection_policy_digest: string;
  inspection_policy_version: string;
  lease_broker_id: string;
  issued_at: string;
  expires_at: string;
  state: "recommendation_protected_inspection_leased";
  purpose: string;
  canonical_digest: string;
  review_requested: true;
  reviewer_assigned: true;
  content_inspection_opened: true;
  content_disclosed: false;
  protected_content_bytes_returned: 0;
  exact_assignee_verified: true;
  browser_session_bound: true;
  non_transferable: true;
  refresh_disabled: true;
  plaintext_secret_buffer_erased: true;
  broker_channel_closed: true;
  human_review_completed: false;
  recommendation_approved: false;
  workflow_created: false;
  itsm_record_created: false;
  execution_authorized: false;
  deployment_authorized: false;
  infrastructure_mutated: false;
  reused: boolean;
};

const forbiddenFields = new Set([
  "lease_secret",
  "browser_session_binding_digest",
  "lease_secret_digest",
  "claim_id",
  "request_binding_digest",
  "idempotency_digest",
  "content",
  "finding",
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

function isSafeResponse(
  value: unknown,
): value is { data: RecommendationProtectedInspection } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const lease = data as Record<string, unknown>;
  return (
    lease.schema_version === "atlas.recommendation-protected-inspection-lease.v1" &&
    lease.state === "recommendation_protected_inspection_leased" &&
    lease.review_requested === true &&
    lease.reviewer_assigned === true &&
    lease.content_inspection_opened === true &&
    lease.content_disclosed === false &&
    lease.protected_content_bytes_returned === 0 &&
    lease.exact_assignee_verified === true &&
    lease.browser_session_bound === true &&
    lease.non_transferable === true &&
    lease.refresh_disabled === true &&
    lease.plaintext_secret_buffer_erased === true &&
    lease.broker_channel_closed === true &&
    lease.human_review_completed === false &&
    lease.recommendation_approved === false &&
    lease.workflow_created === false &&
    lease.itsm_record_created === false &&
    lease.execution_authorized === false &&
    lease.deployment_authorized === false &&
    lease.infrastructure_mutated === false
  );
}

export async function createRecommendationProtectedInspection(input: {
  assignmentResult: RecommendationReviewerAssignmentResult;
  trackCode: RecommendationInspectionTrack;
  policyId: string;
  policyDigest: string;
}) {
  const { assignmentResult, trackCode, policyId, policyDigest } = input;
  const assignment = assignmentResult.assignment;
  const selected = assignment.track_assignments.find(([track]) => track === trackCode);
  if (
    assignment.state !== "reviewers_assigned" ||
    !assignment.reviewer_assigned ||
    assignment.content_inspection_opened ||
    !selected ||
    selected[4] !== "assigned" ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact active reviewer assignment and track are required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(assignment.recommendation_id)}/protected-inspections/leases`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-protected-inspection.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-protected-inspection-input.v1",
        source_assignment_set_id: assignment.assignment_set_id,
        source_assignment_set_digest: assignment.canonical_digest,
        track_code: trackCode,
        opaque_assignment_id: selected[2],
        inspection_policy_id: policyId,
        inspection_policy_digest: policyDigest,
        purpose: assignment.purpose,
        acknowledged_exact_assignee_and_track_required: true,
        acknowledged_lease_returns_no_content_or_secret_in_json: true,
        acknowledged_no_decision_approval_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation protected inspection failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeResponse(payload))
    throw new Error("Recommendation protected inspection returned unsafe metadata");
  if (
    payload.data.source_assignment_set_id !== assignment.assignment_set_id ||
    payload.data.recommendation_id !== assignment.recommendation_id ||
    payload.data.track_code !== trackCode ||
    payload.data.opaque_assignment_id !== selected[2] ||
    payload.data.lease_holder_subject_digest !== selected[3] ||
    payload.data.inspection_policy_id !== policyId
  )
    throw new Error("Inspection lease does not match the exact assigned review track");
  return payload;
}
