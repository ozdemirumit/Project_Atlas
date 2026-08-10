import { apiFetch } from "./client";
import type { RecommendationHumanReviewFinding } from "./recommendationReviewFindings";
import type { RecommendationProtectedContent } from "./recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "./recommendationProtectedInspections";

export type RecommendationPresentedFinding = {
  category_code: string;
  severity_code: string;
  summary: string;
  detail: string;
};

export type RecommendationFindingPresentation = {
  finding_presentation_id: string;
  schema_version: "atlas.recommendation-finding-presentation.v1";
  version: 1;
  source_finding_packet_id: string;
  source_finding_digest: string;
  source_lease_id: string;
  source_presentation_id: string;
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
  track_code: "review-track.technical" | "review-track.service-impact";
  findings: RecommendationPresentedFinding[];
  finding_count: number;
  finding_bytes: number;
  finding_content_digest: string;
  finding_metadata_digest: string;
  lineage_digest: string;
  category_catalog_digest: string;
  severity_catalog_digest: string;
  presentation_policy_id: string;
  presentation_policy_digest: string;
  presentation_policy_version: string;
  presenter_id: string;
  presented_at: string;
  expires_at: string;
  state: "recommendation_human_review_finding_presented";
  purpose: string;
  canonical_digest: string;
  human_findings_recorded: true;
  human_findings_presented: true;
  technical_finding_recorded: boolean;
  service_impact_finding_recorded: boolean;
  technical_findings_presented: boolean;
  service_impact_findings_presented: boolean;
  exact_assignee_verified: true;
  browser_session_bound: true;
  source_integrity_verified: true;
  encrypted_source_verified: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  human_review_completed: false;
  correction_created: false;
  recommendation_approved: false;
  workflow_created: false;
  itsm_record_created: false;
  execution_authorized: false;
  deployment_authorized: false;
  infrastructure_mutated: false;
  reused: boolean;
};

const forbiddenFields = new Set([
  "finding_artifact_id",
  "artifact_location",
  "storage_coordinates",
  "decryption_key",
  "lease_holder_subject_digest",
  "browser_session_binding_digest",
  "raw_subject_id",
  "reviewer_name",
  "reviewer_email",
  "access_policy_id",
  "retention_policy_id",
  "encryption_profile_id",
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

function isFinding(value: unknown): value is RecommendationPresentedFinding {
  if (!value || typeof value !== "object") return false;
  const finding = value as Record<string, unknown>;
  return (
    typeof finding.category_code === "string" &&
    typeof finding.severity_code === "string" &&
    typeof finding.summary === "string" &&
    finding.summary.trim().length >= 10 &&
    finding.summary.length <= 200 &&
    typeof finding.detail === "string" &&
    finding.detail.trim().length >= 20 &&
    finding.detail.length <= 4000
  );
}

function isSafeFindingPresentation(
  value: unknown,
): value is { data: RecommendationFindingPresentation } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.recommendation-finding-presentation.v1" &&
    record.version === 1 &&
    typeof record.finding_presentation_id === "string" &&
    Array.isArray(record.findings) &&
    record.findings.length >= 1 &&
    record.findings.length <= 20 &&
    record.findings.every(isFinding) &&
    record.finding_count === record.findings.length &&
    typeof record.finding_bytes === "number" &&
    record.finding_bytes >= 1 &&
    /^[a-f0-9]{64}$/.test(String(record.finding_content_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.state === "recommendation_human_review_finding_presented" &&
    record.human_findings_recorded === true &&
    record.human_findings_presented === true &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.source_integrity_verified === true &&
    record.encrypted_source_verified === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
    record.human_review_completed === false &&
    record.correction_created === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.itsm_record_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false
  );
}

export async function createRecommendationFindingPresentation(input: {
  lease: RecommendationProtectedInspection;
  presentation: RecommendationProtectedContent;
  finding: RecommendationHumanReviewFinding;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { lease, presentation, finding, policyId, policyDigest, purpose } = input;
  if (
    presentation.source_lease_id !== lease.lease_id ||
    finding.source_lease_id !== lease.lease_id ||
    finding.source_presentation_id !== presentation.presentation_id ||
    finding.recommendation_id !== lease.recommendation_id ||
    finding.track_code !== lease.track_code ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact sealed recommendation finding packet is required");
  const response = await apiFetch(
    `/api/v1/recommendations/${encodeURIComponent(lease.recommendation_id)}/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}/presentations/${encodeURIComponent(presentation.presentation_id)}/findings/${encodeURIComponent(finding.finding_packet_id)}/presentations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-finding-presentation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-finding-presentation-input.v1",
        source_finding_digest: finding.canonical_digest,
        presentation_policy_id: policyId,
        presentation_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_findings_are_sensitive: true,
        acknowledged_finding_presentation_is_not_a_review_decision: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Recommendation finding presentation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeFindingPresentation(payload))
    throw new Error("Recommendation finding presentation returned unsafe content or authority");
  if (
    payload.data.source_finding_packet_id !== finding.finding_packet_id ||
    payload.data.source_finding_digest !== finding.canonical_digest ||
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_presentation_id !== presentation.presentation_id ||
    payload.data.recommendation_id !== lease.recommendation_id ||
    payload.data.track_code !== lease.track_code ||
    payload.data.presentation_policy_id !== policyId ||
    payload.data.presentation_policy_digest !== policyDigest ||
    payload.data.finding_count !== finding.finding_count ||
    payload.data.finding_content_digest !== finding.finding_content_digest
  )
    throw new Error("Finding presentation does not match the sealed recommendation packet");
  return payload;
}
