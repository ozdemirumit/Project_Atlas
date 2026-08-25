import { apiFetch } from "./client";

export type OperationalKnowledgeReviewerAssignmentSource = {
  review_request_id: string;
  source_draft_id: string;
  source_draft_digest: string;
  organization_id: string;
  environment_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  source_ingestion_id: string;
  source_invocation_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  manifest_id: string;
  knowledge_lifecycle: "review_requested";
  canonical_digest: string;
  review_requested: true;
  reviewer_assigned: false;
  content_inspection_opened: false;
  domain_review_completed: false;
  security_review_completed: false;
};

export type OperationalKnowledgeReviewerAssignment = {
  assignment_set_id: string;
  schema_version: "atlas.operational-knowledge-reviewer-assignment.v1";
  version: 1;
  source_review_request_id: string;
  source_review_request_digest: string;
  source_draft_id: string;
  source_draft_digest: string;
  organization_id: string;
  environment_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  source_ingestion_id: string;
  source_invocation_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  knowledge_lifecycle: "reviewer_assigned";
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  encryption_profile_id: string;
  manifest_id: string;
  manifest_digest: string;
  domain_assignment_id: string;
  security_assignment_id: string;
  domain_reviewer_subject_digest: string;
  security_reviewer_subject_digest: string;
  domain_track_code: "review-track.domain";
  security_track_code: "review-track.security";
  domain_queue_id: string;
  security_queue_id: string;
  domain_status: "assigned";
  security_status: "assigned";
  assignment_policy_id: string;
  assignment_policy_digest: string;
  created_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_reviewers_assigned";
  canonical_digest: string;
  review_requested: true;
  reviewer_assigned: true;
  immutable_assignments_confirmed: true;
  encrypted_identity_references: true;
  transient_identity_buffers_erased: true;
  directory_channel_closed: true;
  content_inspection_opened: false;
  domain_review_completed: false;
  security_review_completed: false;
  correction_created: false;
  knowledge_approved: false;
  knowledge_published: false;
  chunks_created: false;
  embeddings_created: false;
  retrieval_published: false;
  model_context_available: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isSafeReviewerAssignment(
  value: unknown,
): value is { data: OperationalKnowledgeReviewerAssignment } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "draft_content",
    "evidence_content",
    "excerpt",
    "observation_values",
    "raw_output",
    "domain_reviewer_id",
    "security_reviewer_id",
    "reviewer_name",
    "reviewer_email",
    "reviewer_group",
    "directory_attributes",
    "review_decision",
    "storage_location",
    "encryption_key",
    "request_binding_digest",
    "idempotency_digest",
    "idempotency_key",
  ];
  return (
    record.schema_version === "atlas.operational-knowledge-reviewer-assignment.v1" &&
    record.version === 1 &&
    typeof record.assignment_set_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    typeof record.domain_reviewer_subject_digest === "string" &&
    typeof record.security_reviewer_subject_digest === "string" &&
    record.domain_reviewer_subject_digest !== record.security_reviewer_subject_digest &&
    record.instance_state === "operational_knowledge_reviewers_assigned" &&
    record.knowledge_lifecycle === "reviewer_assigned" &&
    record.review_requested === true &&
    record.reviewer_assigned === true &&
    record.immutable_assignments_confirmed === true &&
    record.encrypted_identity_references === true &&
    record.transient_identity_buffers_erased === true &&
    record.directory_channel_closed === true &&
    record.domain_status === "assigned" &&
    record.security_status === "assigned" &&
    record.content_inspection_opened === false &&
    record.domain_review_completed === false &&
    record.security_review_completed === false &&
    record.correction_created === false &&
    record.knowledge_approved === false &&
    record.knowledge_published === false &&
    record.chunks_created === false &&
    record.embeddings_created === false &&
    record.retrieval_published === false &&
    record.model_context_available === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbidden.every((field) => !(field in record))
  );
}

export async function createOperationalKnowledgeReviewerAssignment(input: {
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { reviewRequest, policyId, policyDigest, purpose } = input;
  if (
    !reviewRequest.review_requested ||
    reviewRequest.reviewer_assigned ||
    reviewRequest.knowledge_lifecycle !== "review_requested" ||
    reviewRequest.content_inspection_opened ||
    reviewRequest.domain_review_completed ||
    reviewRequest.security_review_completed
  )
    throw new Error("An exact unassigned operational knowledge review request is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact signed reviewer assignment policy is required");
  const response = await apiFetch("/api/v1/knowledge/operational-reviewer-assignments", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-reviewer-assignment.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-reviewer-assignment-input.v1",
      source_review_request_id: reviewRequest.review_request_id,
      source_review_request_digest: reviewRequest.canonical_digest,
      assignment_policy_id: policyId,
      assignment_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_assignment_opens_no_content_and_records_no_decision: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Operational knowledge reviewer assignment failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReviewerAssignment(payload))
    throw new Error("Reviewer assignment returned unsafe metadata");
  if (
    payload.data.source_review_request_id !== reviewRequest.review_request_id ||
    payload.data.source_review_request_digest !== reviewRequest.canonical_digest ||
    payload.data.source_draft_id !== reviewRequest.source_draft_id ||
    payload.data.source_draft_digest !== reviewRequest.source_draft_digest ||
    payload.data.knowledge_item_id !== reviewRequest.knowledge_item_id ||
    payload.data.manifest_id !== reviewRequest.manifest_id ||
    payload.data.connector_id !== reviewRequest.connector_id ||
    payload.data.instance_id !== reviewRequest.instance_id ||
    payload.data.capability_id !== reviewRequest.capability_id ||
    payload.data.assignment_policy_id !== policyId ||
    payload.data.assignment_policy_digest !== policyDigest
  )
    throw new Error("Reviewer assignment does not match the exact governed review request");
  return payload;
}
