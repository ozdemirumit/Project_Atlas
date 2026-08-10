import { apiFetch } from "./client";
import type { RecommendationProtectedInspection } from "./recommendationProtectedInspections";

export type RecommendationProtectedContent = {
  presentation_id: string;
  schema_version: "atlas.recommendation-protected-content-presentation.v1";
  version: 1;
  source_lease_id: string;
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
  track_code: "review-track.technical" | "review-track.service-impact";
  opaque_assignment_id: string;
  output_media_type: "media-type.text-plain";
  language: string;
  content: string;
  presented_content_digest: string;
  protected_content_bytes_returned: number;
  redaction_digest: string;
  truncation_digest: string;
  cleanup_digest: string;
  presentation_policy_id: string;
  presentation_policy_digest: string;
  presentation_policy_version: string;
  presenter_id: string;
  presented_at: string;
  expires_at: string;
  state: "recommendation_protected_content_presented";
  purpose: string;
  canonical_digest: string;
  review_requested: true;
  reviewer_assigned: true;
  content_inspection_opened: true;
  content_disclosed: true;
  exact_assignee_verified: true;
  browser_session_bound: true;
  source_integrity_verified: true;
  redaction_applied: true;
  truncated: boolean;
  active_content_rejected: true;
  transient_buffers_erased: true;
  presenter_channel_closed: true;
  human_findings_recorded: false;
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
  "lease_secret_digest",
  "browser_session_id",
  "browser_session_binding_digest",
  "lease_holder_subject_digest",
  "raw_subject_id",
  "reviewer_name",
  "reviewer_email",
  "request_binding_digest",
  "idempotency_digest",
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
): value is { data: RecommendationProtectedContent } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.recommendation-protected-content-presentation.v1" &&
    record.version === 1 &&
    typeof record.presentation_id === "string" &&
    typeof record.content === "string" &&
    record.content.length > 0 &&
    typeof record.protected_content_bytes_returned === "number" &&
    record.protected_content_bytes_returned > 0 &&
    record.output_media_type === "media-type.text-plain" &&
    /^[a-f0-9]{64}$/.test(String(record.presented_content_digest)) &&
    record.state === "recommendation_protected_content_presented" &&
    record.review_requested === true &&
    record.reviewer_assigned === true &&
    record.content_inspection_opened === true &&
    record.content_disclosed === true &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.source_integrity_verified === true &&
    record.redaction_applied === true &&
    record.active_content_rejected === true &&
    record.transient_buffers_erased === true &&
    record.presenter_channel_closed === true &&
    record.human_findings_recorded === false &&
    record.human_review_completed === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.itsm_record_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false
  );
}

export async function createRecommendationProtectedContent(input: {
  lease: RecommendationProtectedInspection;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { lease, policyId, policyDigest, purpose } = input;
  if (
    lease.content_disclosed ||
    lease.protected_content_bytes_returned !== 0 ||
    !lease.content_inspection_opened ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An active exact-track inspection lease and signed policy are required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(lease.recommendation_id)}/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}/presentations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-protected-content.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-protected-content-input.v1",
        source_lease_digest: lease.canonical_digest,
        presentation_policy_id: policyId,
        presentation_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_sensitive_read_only_content: true,
        acknowledged_no_finding_decision_approval_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation protected content failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeResponse(payload))
    throw new Error("Recommendation protected content returned an unsafe presentation");
  if (
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_assignment_set_id !== lease.source_assignment_set_id ||
    payload.data.recommendation_id !== lease.recommendation_id ||
    payload.data.review_request_id !== lease.review_request_id ||
    payload.data.readiness_assessment_id !== lease.readiness_assessment_id ||
    payload.data.promotion_id !== lease.promotion_id ||
    payload.data.track_code !== lease.track_code ||
    payload.data.opaque_assignment_id !== lease.opaque_assignment_id ||
    payload.data.presentation_policy_id !== policyId ||
    payload.data.presentation_policy_digest !== policyDigest
  )
    throw new Error("Protected content does not match the exact recommendation inspection lease");
  return payload;
}
