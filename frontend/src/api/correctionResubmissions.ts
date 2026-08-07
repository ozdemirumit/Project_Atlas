import { apiFetch } from "./client";
import type { OperationalKnowledgeTrackReviewDecision } from "./reviewDecisions";

export type OperationalKnowledgeCorrection = {
  correction_id: string;
  schema_version: "atlas.operational-knowledge-correction-resubmission.v1";
  version: 1;
  source_review_request_id: string;
  source_review_request_digest: string;
  source_draft_id: string;
  source_draft_digest: string;
  source_decision_ids: [string, string];
  source_decision_digests: [string, string];
  decision_aggregate_digest: string;
  organization_id: string;
  environment_id: string;
  knowledge_item_id: string;
  prior_draft_version_id: string;
  title: string;
  classification: string;
  correction_submission_id: string;
  correction_submission_digest: string;
  correction_policy_id: string;
  correction_policy_digest: string;
  correction_policy_version: string;
  adapter_id: string;
  attestation_digest: string;
  new_draft_id: string;
  new_draft_version_id: string;
  new_draft_content_digest: string;
  new_review_request_id: string;
  new_manifest_id: string;
  domain_status: "awaiting_reviewer";
  security_status: "awaiting_reviewer";
  review_generation: number;
  instance_state: "operational_knowledge_correction_resubmitted";
  canonical_digest: string;
  correction_created: true;
  corrected_draft_created: true;
  review_resubmitted: true;
  reviewer_assigned: false;
  content_inspection_opened: false;
  domain_review_completed: false;
  security_review_completed: false;
  knowledge_approved: false;
  knowledge_published: false;
  retrieval_published: false;
  model_context_available: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const forbiddenResponseFields = [
  "corrected_content",
  "correction_patch",
  "finding_summary",
  "new_draft_artifact_id",
  "new_manifest_artifact_id",
  "corrected_by_subject_digest",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafeCorrection(value: unknown): value is { data: OperationalKnowledgeCorrection } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-correction-resubmission.v1" &&
    record.version === 1 &&
    typeof record.correction_id === "string" &&
    Array.isArray(record.source_decision_ids) &&
    record.source_decision_ids.length === 2 &&
    Array.isArray(record.source_decision_digests) &&
    record.source_decision_digests.length === 2 &&
    record.source_decision_digests.every((item) => /^[a-f0-9]{64}$/.test(String(item))) &&
    /^[a-f0-9]{64}$/.test(String(record.attestation_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.instance_state === "operational_knowledge_correction_resubmitted" &&
    typeof record.review_generation === "number" &&
    record.review_generation >= 2 &&
    record.correction_created === true &&
    record.corrected_draft_created === true &&
    record.review_resubmitted === true &&
    record.domain_status === "awaiting_reviewer" &&
    record.security_status === "awaiting_reviewer" &&
    record.reviewer_assigned === false &&
    record.content_inspection_opened === false &&
    record.domain_review_completed === false &&
    record.security_review_completed === false &&
    record.knowledge_approved === false &&
    record.knowledge_published === false &&
    record.retrieval_published === false &&
    record.model_context_available === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbiddenResponseFields.every((field) => !(field in record))
  );
}

export async function createOperationalKnowledgeCorrection(input: {
  decision: OperationalKnowledgeTrackReviewDecision;
  correctionSubmissionId: string;
  correctionSubmissionDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const {
    decision,
    correctionSubmissionId,
    correctionSubmissionDigest,
    policyId,
    policyDigest,
    purpose,
  } = input;
  const bindings = [...decision.track_decisions].sort((a, b) =>
    a.track_code.localeCompare(b.track_code),
  );
  if (
    !decision.all_tracks_decided ||
    !decision.any_correction_required ||
    bindings.length !== 2 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(correctionSubmissionId) ||
    !/^[a-f0-9]{64}$/.test(correctionSubmissionDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("A fully decided changes-required review generation is required");
  const endpoint =
    `/api/v1/knowledge/review-requests/${encodeURIComponent(decision.review_request_id)}` +
    "/corrections";
  const response = await apiFetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-correction.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-correction-input.v1",
      source_review_request_digest: decision.source_review_request_digest,
      source_decision_ids: bindings.map((item) => item.decision_id),
      source_decision_digests: bindings.map((item) => item.canonical_digest),
      correction_submission_id: correctionSubmissionId,
      correction_submission_digest: correctionSubmissionDigest,
      correction_policy_id: policyId,
      correction_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_exact_change_requirements_addressed: true,
      acknowledged_new_immutable_review_generation: true,
      acknowledged_no_approval_or_operational_authority: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Operational knowledge correction failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeCorrection(payload))
    throw new Error("Correction returned unsafe content or authority-bearing data");
  if (
    payload.data.source_review_request_id !== decision.review_request_id ||
    payload.data.source_review_request_digest !== decision.source_review_request_digest ||
    payload.data.correction_submission_id !== correctionSubmissionId ||
    payload.data.correction_submission_digest !== correctionSubmissionDigest ||
    payload.data.correction_policy_id !== policyId ||
    payload.data.correction_policy_digest !== policyDigest
  )
    throw new Error("Correction does not match the exact review generation");
  return payload;
}
