import { apiFetch } from "./client";
import type { RecommendationProtectedContent } from "./recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "./recommendationProtectedInspections";

export type RecommendationFindingTrack =
  | "review-track.technical"
  | "review-track.service-impact";

export type RecommendationHumanReviewFindingItem = {
  category_code: string;
  severity_code: string;
  summary: string;
  detail: string;
};

export type RecommendationHumanReviewFinding = {
  finding_packet_id: string;
  schema_version: "atlas.recommendation-human-review-finding.v1";
  version: 1;
  source_lease_id: string;
  source_presentation_id: string;
  source_presentation_digest: string;
  source_assignment_set_id: string;
  recommendation_id: string;
  readiness_assessment_id: string;
  promotion_id: string;
  organization_id: string;
  environment_id: string;
  review_request_id: string;
  classification: string;
  source_outcome: "preferred" | "tie" | "no_support";
  option_count: number;
  preferred_count: number;
  track_code: RecommendationFindingTrack;
  finding_count: number;
  finding_bytes: number;
  finding_content_digest: string;
  finding_metadata_digest: string;
  lineage_digest: string;
  category_catalog_digest: string;
  severity_catalog_digest: string;
  finding_policy_id: string;
  finding_policy_digest: string;
  finding_policy_version: string;
  recorder_id: string;
  created_at: string;
  expires_at: string;
  state: "recommendation_human_review_finding_recorded";
  purpose: string;
  canonical_digest: string;
  human_findings_recorded: true;
  technical_finding_recorded: boolean;
  service_impact_finding_recorded: boolean;
  exact_assignee_verified: true;
  browser_session_bound: true;
  source_integrity_verified: true;
  immutable_finding_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  human_review_completed: false;
  recommendation_approved: false;
  correction_created: false;
  workflow_created: false;
  itsm_record_created: false;
  execution_authorized: false;
  deployment_authorized: false;
  infrastructure_mutated: false;
  reused: boolean;
};

const forbiddenFields = new Set([
  "summary",
  "detail",
  "findings",
  "finding_artifact_id",
  "lease_holder_subject_digest",
  "browser_session_binding_digest",
  "raw_subject_id",
  "reviewer_name",
  "reviewer_email",
  "storage_location",
  "idempotency_key",
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

function isSafeReviewFinding(
  value: unknown,
): value is { data: RecommendationHumanReviewFinding } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.recommendation-human-review-finding.v1" &&
    record.version === 1 &&
    typeof record.finding_packet_id === "string" &&
    typeof record.finding_count === "number" &&
    record.finding_count >= 1 &&
    typeof record.finding_bytes === "number" &&
    record.finding_bytes >= 1 &&
    /^[a-f0-9]{64}$/.test(String(record.finding_content_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.state === "recommendation_human_review_finding_recorded" &&
    record.human_findings_recorded === true &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.source_integrity_verified === true &&
    record.immutable_finding_confirmed === true &&
    record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
    record.human_review_completed === false &&
    record.recommendation_approved === false &&
    record.correction_created === false &&
    record.workflow_created === false &&
    record.itsm_record_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false
  );
}

export async function createRecommendationHumanReviewFinding(input: {
  lease: RecommendationProtectedInspection;
  presentation: RecommendationProtectedContent;
  policyId: string;
  policyDigest: string;
  findings: readonly RecommendationHumanReviewFindingItem[];
  purpose: string;
}) {
  const { lease, presentation, policyId, policyDigest, findings, purpose } = input;
  if (
    presentation.source_lease_id !== lease.lease_id ||
    presentation.recommendation_id !== lease.recommendation_id ||
    presentation.track_code !== lease.track_code ||
    findings.length < 1 ||
    findings.length > 20 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact active recommendation presentation and finding packet are required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(lease.recommendation_id)}/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}/presentations/${encodeURIComponent(presentation.presentation_id)}/findings`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-human-review-finding.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-human-review-finding-input.v1",
        source_presentation_digest: presentation.canonical_digest,
        finding_policy_id: policyId,
        finding_policy_digest: policyDigest,
        findings: findings.map((finding) => ({
          category_code: finding.category_code,
          severity_code: finding.severity_code,
          summary: finding.summary.trim(),
          detail: finding.detail.trim(),
        })),
        purpose: purpose.trim(),
        acknowledged_evidence_was_reviewed: true,
        acknowledged_finding_is_not_a_review_decision: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation human review finding failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReviewFinding(payload))
    throw new Error("Recommendation finding returned an unsafe or authority-bearing record");
  if (
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_presentation_id !== presentation.presentation_id ||
    payload.data.source_presentation_digest !== presentation.canonical_digest ||
    payload.data.recommendation_id !== lease.recommendation_id ||
    payload.data.track_code !== presentation.track_code ||
    payload.data.finding_policy_id !== policyId ||
    payload.data.finding_policy_digest !== policyDigest ||
    payload.data.finding_count !== findings.length
  )
    throw new Error("Finding record does not match the exact recommendation presentation");
  return payload;
}
