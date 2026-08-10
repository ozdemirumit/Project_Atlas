import { apiFetch } from "./client";

export type RecommendationCorrection = {
  correction_id: string;
  schema_version: "atlas.recommendation-correction-resubmission.v1";
  version: 1;
  source_review_request_id: string;
  source_review_request_digest: string;
  source_recommendation_id: string;
  source_recommendation_digest: string;
  source_promotion_id: string;
  source_readiness_assessment_id: string;
  source_assignment_set_id: string;
  source_decision_ids: [string, string];
  source_decision_digests: [string, string];
  decision_aggregate_digest: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  correction_submission_id: string;
  correction_submission_digest: string;
  correction_policy_id: string;
  correction_policy_digest: string;
  correction_policy_version: string;
  adapter_id: string;
  attestation_digest: string;
  new_recommendation_id: string;
  new_promotion_id: string;
  new_artifact_digest: string;
  source_binding_digest: string;
  created_at: string;
  expires_at: string;
  state: "recommendation_correction_resubmitted";
  purpose: string;
  canonical_digest: string;
  recommendation_promoted: true;
  correction_created: true;
  readiness_assessed: false;
  review_requested: false;
  reviewer_assigned: false;
  protected_inspection_opened: false;
  human_findings_recorded: false;
  technical_review_completed: false;
  service_impact_review_completed: false;
  final_disposition_recorded: false;
  recommendation_approved: false;
  workflow_created: false;
  itsm_record_created: false;
  execution_authorized: false;
  deployment_authorized: false;
  infrastructure_mutated: false;
  reused: boolean;
};

const digest = /^[a-f0-9]{64}$/;
const forbiddenResponseFields = new Set([
  "findings",
  "corrected_content",
  "patch",
  "options",
  "headline",
  "safety_notice",
  "artifact_location",
  "artifact_uri",
  "reviewer_id",
  "decided_by_subject_digest",
  "corrected_by_subject_digest",
  "browser_session_binding_digest",
  "command",
  "credential",
]);

function hasForbiddenField(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenField);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) => forbiddenResponseFields.has(key) || hasForbiddenField(child),
  );
}

function isSafeCorrection(value: unknown): value is { data: RecommendationCorrection } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.recommendation-correction-resubmission.v1" &&
    record.version === 1 &&
    record.state === "recommendation_correction_resubmitted" &&
    typeof record.correction_id === "string" &&
    typeof record.source_review_request_id === "string" &&
    typeof record.source_recommendation_id === "string" &&
    typeof record.new_recommendation_id === "string" &&
    typeof record.new_promotion_id === "string" &&
    digest.test(String(record.source_review_request_digest)) &&
    digest.test(String(record.source_recommendation_digest)) &&
    digest.test(String(record.decision_aggregate_digest)) &&
    digest.test(String(record.new_artifact_digest)) &&
    digest.test(String(record.canonical_digest)) &&
    Array.isArray(record.source_decision_ids) &&
    record.source_decision_ids.length === 2 &&
    Array.isArray(record.source_decision_digests) &&
    record.source_decision_digests.length === 2 &&
    record.source_decision_digests.every((item) => digest.test(String(item))) &&
    record.recommendation_promoted === true &&
    record.correction_created === true &&
    record.readiness_assessed === false &&
    record.review_requested === false &&
    record.reviewer_assigned === false &&
    record.protected_inspection_opened === false &&
    record.human_findings_recorded === false &&
    record.technical_review_completed === false &&
    record.service_impact_review_completed === false &&
    record.final_disposition_recorded === false &&
    record.recommendation_approved === false &&
    record.workflow_created === false &&
    record.itsm_record_created === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false
  );
}

export async function createRecommendationCorrection(input: {
  sourceReviewRequestId: string;
  sourceReviewRequestDigest: string;
  sourceRecommendationId: string;
  sourceRecommendationDigest: string;
  sourceDecisions: [
    { decisionId: string; canonicalDigest: string },
    { decisionId: string; canonicalDigest: string },
  ];
  correctionSubmissionId: string;
  correctionSubmissionDigest: string;
  correctionPolicyId: string;
  correctionPolicyDigest: string;
  purpose: string;
}) {
  const decisionIds = input.sourceDecisions.map((item) => item.decisionId);
  const decisionDigests = input.sourceDecisions.map((item) => item.canonicalDigest);
  if (
    new Set(decisionIds).size !== 2 ||
    new Set(decisionDigests).size !== 2 ||
    !digest.test(input.sourceReviewRequestDigest) ||
    !digest.test(input.sourceRecommendationDigest) ||
    !digest.test(input.correctionSubmissionDigest) ||
    !digest.test(input.correctionPolicyDigest) ||
    decisionDigests.some((item) => !digest.test(item)) ||
    input.purpose.trim().length < 20
  )
    throw new Error("Exact recommendation correction lineage is required");
  const response = await apiFetch(
    `/api/v1/recommendations/review-requests/${encodeURIComponent(input.sourceReviewRequestId)}/corrections`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `recommendation-correction.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.recommendation-correction-input.v1",
        source_review_request_digest: input.sourceReviewRequestDigest,
        source_recommendation_id: input.sourceRecommendationId,
        source_recommendation_digest: input.sourceRecommendationDigest,
        source_decision_ids: decisionIds,
        source_decision_digests: decisionDigests,
        correction_submission_id: input.correctionSubmissionId,
        correction_submission_digest: input.correctionSubmissionDigest,
        correction_policy_id: input.correctionPolicyId,
        correction_policy_digest: input.correctionPolicyDigest,
        purpose: input.purpose.trim(),
        acknowledged_exact_change_requirements_addressed: true,
        acknowledged_new_immutable_recommendation_version: true,
        acknowledged_fresh_readiness_required: true,
        acknowledged_no_review_approval_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Recommendation correction failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeCorrection(payload))
    throw new Error("Recommendation correction returned unsafe content or authority");
  if (
    payload.data.source_review_request_id !== input.sourceReviewRequestId ||
    payload.data.source_review_request_digest !== input.sourceReviewRequestDigest ||
    payload.data.source_recommendation_id !== input.sourceRecommendationId ||
    payload.data.source_recommendation_digest !== input.sourceRecommendationDigest ||
    payload.data.correction_submission_id !== input.correctionSubmissionId ||
    payload.data.correction_submission_digest !== input.correctionSubmissionDigest ||
    payload.data.correction_policy_id !== input.correctionPolicyId ||
    payload.data.correction_policy_digest !== input.correctionPolicyDigest
  )
    throw new Error("Recommendation correction does not match the exact rejected generation");
  return payload;
}
