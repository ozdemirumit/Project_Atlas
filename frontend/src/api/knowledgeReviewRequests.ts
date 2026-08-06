import { apiFetch } from "./client";
import type { OperationalEvidenceKnowledgeDraft } from "./evidenceDrafts";

export type OperationalKnowledgeReviewRequest = {
  review_request_id: string;
  schema_version: "atlas.operational-knowledge-review-request.v1";
  version: 1;
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
  draft_domain: "domain.operational";
  content_type: string;
  language: string;
  knowledge_lifecycle: "review_requested";
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  encryption_profile_id: string;
  manifest_id: string;
  orchestration_policy_id: string;
  orchestration_policy_digest: string;
  domain_track_code: "review-track.domain";
  security_track_code: "review-track.security";
  domain_queue_id: string;
  security_queue_id: string;
  assignment_strategy: "assignment-strategy.policy-controlled";
  sla_class: string;
  domain_status: "awaiting_reviewer";
  security_status: "awaiting_reviewer";
  created_at: string;
  instance_state: "operational_knowledge_review_requested";
  canonical_digest: string;
  review_requested: true;
  immutable_manifest_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  reviewer_assigned: false;
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

function isSafeReviewRequest(
  value: unknown,
): value is { data: OperationalKnowledgeReviewRequest } {
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
    "reviewer_id",
    "reviewer_group",
    "review_decision",
    "target_address",
    "storage_location",
    "storage_coordinates",
    "acl_principals",
    "encryption_key",
    "secret_reference_id",
    "session_handle",
    "request_binding_digest",
    "idempotency_digest",
    "idempotency_key",
  ];
  return (
    record.schema_version === "atlas.operational-knowledge-review-request.v1" &&
    record.version === 1 &&
    typeof record.review_request_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "operational_knowledge_review_requested" &&
    record.knowledge_lifecycle === "review_requested" &&
    record.review_requested === true &&
    record.immutable_manifest_confirmed === true &&
    record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
    record.domain_status === "awaiting_reviewer" &&
    record.security_status === "awaiting_reviewer" &&
    record.reviewer_assigned === false &&
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

export async function createOperationalKnowledgeReviewRequest(input: {
  draft: OperationalEvidenceKnowledgeDraft;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { draft, policyId, policyDigest, purpose } = input;
  if (
    !draft.knowledge_item_created ||
    !draft.immutable_draft_confirmed ||
    draft.knowledge_lifecycle !== "draft" ||
    draft.domain_review_completed ||
    draft.security_review_completed ||
    draft.knowledge_approved ||
    draft.retrieval_published
  )
    throw new Error("An exact unreviewed immutable knowledge draft is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact signed review orchestration policy is required");
  const response = await apiFetch("/api/v1/knowledge/operational-review-requests", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-knowledge-review-request.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-knowledge-review-request-input.v1",
      source_draft_id: draft.draft_id,
      source_draft_digest: draft.canonical_digest,
      orchestration_policy_id: policyId,
      orchestration_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_result_is_only_an_unassigned_review_request: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Operational knowledge review request failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeReviewRequest(payload)) throw new Error("Review request returned unsafe metadata");
  if (
    payload.data.source_draft_id !== draft.draft_id ||
    payload.data.source_draft_digest !== draft.canonical_digest ||
    payload.data.knowledge_item_id !== draft.knowledge_item_id ||
    payload.data.draft_version_id !== draft.draft_version_id ||
    payload.data.connector_id !== draft.connector_id ||
    payload.data.instance_id !== draft.instance_id ||
    payload.data.capability_id !== draft.capability_id ||
    payload.data.classification !== draft.classification ||
    payload.data.access_policy_id !== draft.access_policy_id ||
    payload.data.retention_policy_id !== draft.retention_policy_id ||
    payload.data.encryption_profile_id !== draft.encryption_profile_id ||
    payload.data.orchestration_policy_id !== policyId ||
    payload.data.orchestration_policy_digest !== policyDigest
  )
    throw new Error("Review request does not match the exact governed draft");
  return payload;
}
