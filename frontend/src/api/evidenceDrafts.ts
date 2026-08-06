import { apiFetch } from "./client";
import type { ConnectorInvocationEvidence } from "./invocationEvidence";

export type OperationalEvidenceKnowledgeDraft = {
  draft_id: string;
  schema_version: "atlas.operational-evidence-knowledge-draft.v1";
  version: 1;
  claim_id: string;
  source_ingestion_id: string;
  source_ingestion_digest: string;
  organization_id: string;
  environment_id: string;
  source_invocation_id: string;
  evidence_package_id: string;
  evidence_content_digest: string;
  evidence_metadata_digest: string;
  connector_id: string;
  instance_id: string;
  capability_id: string;
  knowledge_item_id: string;
  draft_version_id: string;
  draft_artifact_id: string;
  draft_schema_version: string;
  title: string;
  draft_domain: "domain.operational";
  content_type: string;
  source_authority: "source-authority.system-generated";
  language: string;
  knowledge_lifecycle: "draft";
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  encryption_profile_id: string;
  curation_policy_id: string;
  curation_policy_digest: string;
  draft_item_count: number;
  draft_bytes: number;
  created_at: string;
  instance_state: "draft_operational_knowledge_created";
  canonical_digest: string;
  evidence_ingested: true;
  knowledge_item_created: true;
  immutable_draft_confirmed: true;
  encrypted_at_rest: true;
  transient_buffers_erased: true;
  artifact_channel_closed: true;
  domain_review_completed: false;
  security_review_completed: false;
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

function isSafeEvidenceDraft(
  value: unknown,
): value is { data: OperationalEvidenceKnowledgeDraft } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const forbidden = [
    "evidence_content",
    "draft_content",
    "excerpt",
    "observation_values",
    "raw_output",
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
    record.schema_version === "atlas.operational-evidence-knowledge-draft.v1" &&
    record.version === 1 &&
    typeof record.draft_id === "string" &&
    typeof record.title === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "draft_operational_knowledge_created" &&
    record.knowledge_lifecycle === "draft" &&
    record.evidence_ingested === true &&
    record.knowledge_item_created === true &&
    record.immutable_draft_confirmed === true &&
    record.encrypted_at_rest === true &&
    record.transient_buffers_erased === true &&
    record.artifact_channel_closed === true &&
    record.domain_review_completed === false &&
    record.security_review_completed === false &&
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

export async function createOperationalEvidenceKnowledgeDraft(input: {
  evidence: ConnectorInvocationEvidence;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { evidence, policyId, policyDigest, purpose } = input;
  if (
    !evidence.evidence_ingested ||
    !evidence.immutable_storage_confirmed ||
    evidence.knowledge_item_created ||
    evidence.retrieval_published ||
    evidence.instance_state !== "enabled_invocation_evidence_ingested"
  )
    throw new Error("Completed uncurated operational evidence is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact signed curation policy is required");
  const response = await apiFetch("/api/v1/knowledge/operational-evidence-drafts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `operational-evidence-knowledge-draft.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.operational-evidence-knowledge-draft-input.v1",
      source_ingestion_id: evidence.ingestion_id,
      source_ingestion_digest: evidence.canonical_digest,
      curation_policy_id: policyId,
      curation_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_result_is_an_unapproved_non_retrievable_draft: true,
    }),
  });
  if (!response.ok)
    throw new Error(`Operational evidence knowledge draft failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeEvidenceDraft(payload)) throw new Error("Knowledge draft returned unsafe metadata");
  if (
    payload.data.source_ingestion_id !== evidence.ingestion_id ||
    payload.data.source_ingestion_digest !== evidence.canonical_digest ||
    payload.data.evidence_package_id !== evidence.evidence_package_id ||
    payload.data.evidence_content_digest !== evidence.evidence_content_digest ||
    payload.data.connector_id !== evidence.connector_id ||
    payload.data.instance_id !== evidence.instance_id ||
    payload.data.capability_id !== evidence.capability_id ||
    payload.data.classification !== evidence.classification ||
    payload.data.access_policy_id !== evidence.access_policy_id ||
    payload.data.retention_policy_id !== evidence.retention_policy_id ||
    payload.data.encryption_profile_id !== evidence.encryption_profile_id ||
    payload.data.curation_policy_id !== policyId ||
    payload.data.curation_policy_digest !== policyDigest
  )
    throw new Error("Knowledge draft does not match the exact governed evidence");
  return payload;
}
