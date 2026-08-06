import { apiFetch } from "./client";
import type { OperationalKnowledgeReviewerAssignment } from "./reviewerAssignments";

export type InspectionTrack = "review-track.domain" | "review-track.security";

export type OperationalKnowledgeProtectedInspectionLease = {
  lease_id: string;
  schema_version: "atlas.operational-knowledge-protected-inspection-lease.v1";
  version: 1;
  source_assignment_set_id: string;
  source_assignment_set_digest: string;
  organization_id: string;
  environment_id: string;
  review_request_id: string;
  source_draft_id: string;
  source_draft_digest: string;
  knowledge_item_id: string;
  draft_version_id: string;
  source_ingestion_id: string;
  source_invocation_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  encryption_profile_id: string;
  manifest_id: string;
  manifest_digest: string;
  track_code: InspectionTrack;
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
  instance_state: "operational_knowledge_protected_inspection_leased";
  purpose: string;
  canonical_digest: string;
  review_requested: true;
  reviewer_assigned: true;
  content_inspection_opened: true;
  content_disclosed: false;
  content_bytes_read: 0;
  exact_assignee_verified: true;
  browser_session_bound: true;
  non_transferable: true;
  refresh_disabled: true;
  plaintext_secret_buffer_erased: true;
  broker_channel_closed: true;
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

function isSafeProtectedInspectionLease(
  value: unknown,
): value is { data: OperationalKnowledgeProtectedInspectionLease } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "lease_secret",
    "lease_secret_digest",
    "browser_session_id",
    "browser_session_binding_digest",
    "raw_subject_id",
    "reviewer_name",
    "reviewer_email",
    "reviewer_group",
    "directory_attributes",
    "draft_content",
    "evidence_content",
    "excerpt",
    "observation_values",
    "storage_location",
    "encryption_key",
    "request_binding_digest",
    "idempotency_digest",
    "idempotency_key",
  ];
  return (
    record.schema_version === "atlas.operational-knowledge-protected-inspection-lease.v1" &&
    record.version === 1 &&
    typeof record.lease_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    (record.track_code === "review-track.domain" ||
      record.track_code === "review-track.security") &&
    record.instance_state === "operational_knowledge_protected_inspection_leased" &&
    record.review_requested === true &&
    record.reviewer_assigned === true &&
    record.content_inspection_opened === true &&
    record.content_disclosed === false &&
    record.content_bytes_read === 0 &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.non_transferable === true &&
    record.refresh_disabled === true &&
    record.plaintext_secret_buffer_erased === true &&
    record.broker_channel_closed === true &&
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

export async function createOperationalKnowledgeProtectedInspectionLease(input: {
  assignment: OperationalKnowledgeReviewerAssignment;
  trackCode: InspectionTrack;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { assignment, trackCode, policyId, policyDigest, purpose } = input;
  if (
    !assignment.review_requested ||
    !assignment.reviewer_assigned ||
    assignment.knowledge_lifecycle !== "reviewer_assigned" ||
    assignment.content_inspection_opened ||
    assignment.domain_review_completed ||
    assignment.security_review_completed
  )
    throw new Error("An exact assigned operational knowledge review track is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact signed protected inspection policy is required");
  const response = await apiFetch("/api/v1/knowledge/protected-inspections/leases", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-protected-inspection.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-protected-inspection-input.v1",
      source_assignment_set_id: assignment.assignment_set_id,
      source_assignment_set_digest: assignment.canonical_digest,
      track_code: trackCode,
      inspection_policy_id: policyId,
      inspection_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_lease_returns_no_content_and_records_no_decision: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Operational knowledge protected inspection failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeProtectedInspectionLease(payload))
    throw new Error("Protected inspection lease returned unsafe metadata");
  if (
    payload.data.source_assignment_set_id !== assignment.assignment_set_id ||
    payload.data.source_assignment_set_digest !== assignment.canonical_digest ||
    payload.data.review_request_id !== assignment.source_review_request_id ||
    payload.data.source_draft_id !== assignment.source_draft_id ||
    payload.data.knowledge_item_id !== assignment.knowledge_item_id ||
    payload.data.manifest_id !== assignment.manifest_id ||
    payload.data.connector_id !== assignment.connector_id ||
    payload.data.instance_id !== assignment.instance_id ||
    payload.data.capability_id !== assignment.capability_id ||
    payload.data.track_code !== trackCode ||
    payload.data.inspection_policy_id !== policyId ||
    payload.data.inspection_policy_digest !== policyDigest
  )
    throw new Error("Protected inspection lease does not match the exact assigned review track");
  return payload;
}
