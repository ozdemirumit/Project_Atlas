import { apiFetch } from "./client";

export type FinalRecommendationDispositionCode =
  | "recommendation-disposition.accepted"
  | "recommendation-disposition.rejected";

export type FinalRecommendationDisposition = {
  disposition_id: string;
  schema_version: "atlas.final-recommendation-disposition.v1";
  version: 1;
  review_request_id: string;
  review_request_digest: string;
  recommendation_id: string;
  recommendation_digest: string;
  promotion_id: string;
  readiness_assessment_id: string;
  assignment_set_id: string;
  decision_ids: [string, string];
  decision_digests: [string, string];
  decision_aggregate_digest: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  disposition_code: FinalRecommendationDispositionCode;
  basis_codes: string[];
  basis_digest: string;
  disposition_policy_id: string;
  disposition_policy_digest: string;
  disposition_policy_version: string;
  attestor_id: string;
  attestation_digest: string;
  resolved_at: string;
  state: "recommendation_final_accepted" | "recommendation_final_rejected";
  purpose: string;
  canonical_digest: string;
  technical_review_completed: true;
  service_impact_review_completed: true;
  technical_review_passed: true;
  service_impact_review_passed: true;
  correction_required: false;
  correction_created: false;
  final_disposition_recorded: true;
  recommendation_approved: boolean;
  workflow_handoff_eligible: boolean;
  workflow_created: false;
  itsm_record_created: false;
  change_approved: false;
  execution_authorized: false;
  deployment_authorized: false;
  infrastructure_mutated: false;
  reused: boolean;
};

const digest = /^[a-f0-9]{64}$/;
const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const forbiddenResponseFields = new Set([
  "recommendation_content",
  "findings",
  "summary",
  "detail",
  "artifact_location",
  "artifact_uri",
  "approved_by",
  "approved_by_subject_digest",
  "browser_session_binding_digest",
  "reviewer_id",
  "decided_by_subject_digest",
  "command",
  "credential",
  "workflow_payload",
  "change_request",
]);

function hasForbiddenField(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenField);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) => forbiddenResponseFields.has(key) || hasForbiddenField(child),
  );
}

function isSafeFinalDisposition(
  value: unknown,
): value is { data: FinalRecommendationDisposition } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const accepted = record.disposition_code === "recommendation-disposition.accepted";
  const rejected = record.disposition_code === "recommendation-disposition.rejected";
  const requiredIds = [
    record.disposition_id,
    record.review_request_id,
    record.recommendation_id,
    record.promotion_id,
    record.readiness_assessment_id,
    record.assignment_set_id,
    record.organization_id,
    record.environment_id,
    record.classification,
    record.disposition_policy_id,
    record.disposition_policy_version,
    record.attestor_id,
  ];
  return (
    record.schema_version === "atlas.final-recommendation-disposition.v1" &&
    record.version === 1 &&
    requiredIds.every((item) => typeof item === "string" && stableId.test(item)) &&
    (accepted || rejected) &&
    record.state ===
      (accepted ? "recommendation_final_accepted" : "recommendation_final_rejected") &&
    Array.isArray(record.decision_ids) &&
    record.decision_ids.length === 2 &&
    new Set(record.decision_ids).size === 2 &&
    record.decision_ids.every((item) => typeof item === "string" && stableId.test(item)) &&
    Array.isArray(record.decision_digests) &&
    record.decision_digests.length === 2 &&
    new Set(record.decision_digests).size === 2 &&
    record.decision_digests.every((item) => digest.test(String(item))) &&
    Array.isArray(record.basis_codes) &&
    record.basis_codes.length >= 1 &&
    record.basis_codes.length <= 8 &&
    record.basis_codes.every((item) => typeof item === "string" && stableId.test(item)) &&
    digest.test(String(record.review_request_digest)) &&
    digest.test(String(record.recommendation_digest)) &&
    digest.test(String(record.decision_aggregate_digest)) &&
    digest.test(String(record.basis_digest)) &&
    digest.test(String(record.disposition_policy_digest)) &&
    digest.test(String(record.attestation_digest)) &&
    digest.test(String(record.canonical_digest)) &&
    typeof record.resolved_at === "string" &&
    Number.isFinite(Date.parse(record.resolved_at)) &&
    typeof record.purpose === "string" &&
    record.purpose.trim().length >= 20 &&
    record.purpose.length <= 1000 &&
    record.technical_review_completed === true &&
    record.service_impact_review_completed === true &&
    record.technical_review_passed === true &&
    record.service_impact_review_passed === true &&
    record.correction_required === false &&
    record.correction_created === false &&
    record.final_disposition_recorded === true &&
    record.recommendation_approved === accepted &&
    record.workflow_handoff_eligible === accepted &&
    record.workflow_created === false &&
    record.itsm_record_created === false &&
    record.change_approved === false &&
    record.execution_authorized === false &&
    record.deployment_authorized === false &&
    record.infrastructure_mutated === false &&
    typeof record.reused === "boolean"
  );
}

export async function createFinalRecommendationDisposition(input: {
  reviewRequestId: string;
  reviewRequestDigest: string;
  recommendationId: string;
  recommendationDigest: string;
  decisions: [
    { decisionId: string; canonicalDigest: string },
    { decisionId: string; canonicalDigest: string },
  ];
  disposition: FinalRecommendationDispositionCode;
  basisCodes: string[];
  dispositionPolicyId: string;
  dispositionPolicyDigest: string;
  purpose: string;
}) {
  const decisionIds = input.decisions.map((item) => item.decisionId);
  const decisionDigests = input.decisions.map((item) => item.canonicalDigest);
  const decisionBindings = new Set(
    input.decisions.map((item) => `${item.decisionId}:${item.canonicalDigest}`),
  );
  const basisCodes = [...new Set(input.basisCodes)].sort();
  const basisSet = new Set(basisCodes);
  if (
    !stableId.test(input.reviewRequestId) ||
    !stableId.test(input.recommendationId) ||
    !stableId.test(input.dispositionPolicyId) ||
    !digest.test(input.reviewRequestDigest) ||
    !digest.test(input.recommendationDigest) ||
    !digest.test(input.dispositionPolicyDigest) ||
    new Set(decisionIds).size !== 2 ||
    decisionIds.some((item) => !stableId.test(item)) ||
    new Set(decisionDigests).size !== 2 ||
    decisionDigests.some((item) => !digest.test(item)) ||
    basisCodes.length < 1 ||
    basisCodes.length > 8 ||
    basisCodes.some((item) => !stableId.test(item)) ||
    input.purpose.trim().length < 20
  )
    throw new Error("Exact passed review lineage and a bounded final disposition are required");
  const response = await apiFetch(
    `/api/v1/recommendations/review-requests/${encodeURIComponent(input.reviewRequestId)}/final-dispositions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `final-recommendation-disposition.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.final-recommendation-disposition-input.v1",
        review_request_digest: input.reviewRequestDigest,
        recommendation_id: input.recommendationId,
        recommendation_digest: input.recommendationDigest,
        decision_ids: decisionIds,
        decision_digests: decisionDigests,
        disposition_code: input.disposition,
        basis_codes: basisCodes,
        disposition_policy_id: input.dispositionPolicyId,
        disposition_policy_digest: input.dispositionPolicyDigest,
        purpose: input.purpose.trim(),
        acknowledged_immutable_review_generation: true,
        acknowledged_recommendation_level_decision_only: true,
        acknowledged_handoff_eligibility_only: true,
        acknowledged_no_workflow_itsm_change_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Final recommendation disposition failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeFinalDisposition(payload))
    throw new Error("Final recommendation disposition returned unsafe content or authority");
  if (
    payload.data.review_request_id !== input.reviewRequestId ||
    payload.data.review_request_digest !== input.reviewRequestDigest ||
    payload.data.recommendation_id !== input.recommendationId ||
    payload.data.recommendation_digest !== input.recommendationDigest ||
    payload.data.disposition_code !== input.disposition ||
    payload.data.disposition_policy_id !== input.dispositionPolicyId ||
    payload.data.disposition_policy_digest !== input.dispositionPolicyDigest ||
    payload.data.purpose !== input.purpose.trim() ||
    payload.data.basis_codes.length !== basisSet.size ||
    payload.data.basis_codes.some((item) => !basisSet.has(item)) ||
    payload.data.decision_ids.some(
      (item, index) =>
        !decisionBindings.has(`${item}:${payload.data.decision_digests[index]}`),
    )
  )
    throw new Error("Final recommendation disposition does not match the exact review generation");
  return payload;
}
