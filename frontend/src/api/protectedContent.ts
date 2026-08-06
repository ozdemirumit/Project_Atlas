import { apiFetch } from "./client";
import type { OperationalKnowledgeProtectedInspectionLease } from "./protectedInspections";

export type OperationalKnowledgeProtectedContent = {
  presentation_id: string;
  schema_version: "atlas.operational-knowledge-protected-content-presentation.v1";
  version: 1;
  source_lease_id: string;
  source_lease_digest: string;
  source_assignment_set_id: string;
  organization_id: string;
  environment_id: string;
  review_request_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  title: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  encryption_profile_id: string;
  track_code: "review-track.domain" | "review-track.security";
  output_media_type: "media-type.text-plain";
  language: string;
  content: string;
  presented_content_digest: string;
  content_bytes: number;
  redaction_digest: string;
  truncation_digest: string;
  cleanup_digest: string;
  presentation_policy_id: string;
  presentation_policy_digest: string;
  presentation_policy_version: string;
  presenter_id: string;
  presented_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_protected_content_presented";
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
  artifact_channel_closed: true;
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

function isSafeProtectedContent(
  value: unknown,
): value is { data: OperationalKnowledgeProtectedContent } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "lease_secret",
    "lease_secret_digest",
    "browser_session_id",
    "browser_session_binding_digest",
    "lease_holder_subject_digest",
    "draft_artifact_id",
    "draft_content_digest",
    "raw_subject_id",
    "reviewer_name",
    "reviewer_email",
    "storage_location",
    "decryption_key",
    "request_binding_digest",
    "idempotency_digest",
  ];
  return (
    record.schema_version === "atlas.operational-knowledge-protected-content-presentation.v1" &&
    record.version === 1 &&
    typeof record.presentation_id === "string" &&
    typeof record.content === "string" &&
    record.content.length > 0 &&
    typeof record.content_bytes === "number" &&
    record.content_bytes > 0 &&
    record.output_media_type === "media-type.text-plain" &&
    /^[a-f0-9]{64}$/.test(String(record.presented_content_digest)) &&
    record.instance_state === "operational_knowledge_protected_content_presented" &&
    record.content_inspection_opened === true &&
    record.content_disclosed === true &&
    record.exact_assignee_verified === true &&
    record.browser_session_bound === true &&
    record.source_integrity_verified === true &&
    record.redaction_applied === true &&
    record.active_content_rejected === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
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

export async function createOperationalKnowledgeProtectedContent(input: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { lease, policyId, policyDigest, purpose } = input;
  if (
    lease.content_disclosed ||
    lease.content_bytes_read !== 0 ||
    !lease.content_inspection_opened ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An active exact-track inspection lease and signed policy are required");
  const response = await apiFetch(
    `/api/v1/knowledge/protected-inspections/leases/${encodeURIComponent(lease.lease_id)}/presentations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-protected-content.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-protected-content-input.v1",
        source_lease_digest: lease.canonical_digest,
        presentation_policy_id: policyId,
        presentation_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_sensitive_read_only_content_grants_no_review_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge protected content failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeProtectedContent(payload))
    throw new Error("Protected content returned an unsafe presentation");
  if (
    payload.data.source_lease_id !== lease.lease_id ||
    payload.data.source_lease_digest !== lease.canonical_digest ||
    payload.data.source_assignment_set_id !== lease.source_assignment_set_id ||
    payload.data.source_draft_id !== lease.source_draft_id ||
    payload.data.knowledge_item_id !== lease.knowledge_item_id ||
    payload.data.track_code !== lease.track_code ||
    payload.data.presentation_policy_id !== policyId ||
    payload.data.presentation_policy_digest !== policyDigest
  )
    throw new Error("Protected content does not match the exact inspection lease");
  return payload;
}
