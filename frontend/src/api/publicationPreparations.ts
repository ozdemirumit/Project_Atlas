import { apiFetch } from "./client";
import type { OperationalKnowledgeFinalResolution } from "./finalResolutions";

export type OperationalKnowledgePublicationPreparation = {
  preparation_id: string;
  schema_version: "atlas.operational-knowledge-publication-preparation.v1";
  version: 1;
  resolution_id: string;
  resolution_digest: string;
  review_request_id: string;
  review_request_digest: string;
  source_draft_id: string;
  source_draft_digest: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  preparation_policy_id: string;
  preparation_policy_digest: string;
  preparation_policy_version: string;
  preparation_profile_id: string;
  preparation_profile_digest: string;
  chunking_profile_id: string;
  chunking_profile_digest: string;
  embedding_profile_id: string;
  embedding_profile_digest: string;
  index_profile_id: string;
  index_profile_digest: string;
  validation_profile_id: string;
  validation_profile_digest: string;
  preparer_id: string;
  preparation_receipt_digest: string;
  source_artifact_digest: string;
  metadata_manifest_digest: string;
  access_manifest_digest: string;
  retention_manifest_digest: string;
  instance_state: "operational_knowledge_publication_prepared";
  canonical_digest: string;
  knowledge_approved: true;
  publication_ready: true;
  publication_prepared: true;
  knowledge_published: false;
  chunks_created: false;
  embeddings_created: false;
  index_staged: false;
  index_validated: false;
  retrieval_published: false;
  model_context_available: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

const forbiddenResponseFields = [
  "content",
  "title",
  "artifact_location",
  "final_approver_subject_digest",
  "prepared_by_subject_digest",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafePreparation(
  value: unknown,
): value is { data: OperationalKnowledgePublicationPreparation } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-publication-preparation.v1" &&
    record.version === 1 &&
    typeof record.preparation_id === "string" &&
    /^[a-f0-9]{64}$/.test(String(record.preparation_receipt_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.canonical_digest)) &&
    record.instance_state === "operational_knowledge_publication_prepared" &&
    record.knowledge_approved === true &&
    record.publication_ready === true &&
    record.publication_prepared === true &&
    record.knowledge_published === false &&
    record.chunks_created === false &&
    record.embeddings_created === false &&
    record.index_staged === false &&
    record.index_validated === false &&
    record.retrieval_published === false &&
    record.model_context_available === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    forbiddenResponseFields.every((field) => !(field in record))
  );
}

export async function createOperationalKnowledgePublicationPreparation(input: {
  resolution: OperationalKnowledgeFinalResolution;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { resolution, policyId, policyDigest, purpose } = input;
  if (
    !resolution.knowledge_approved ||
    !resolution.publication_ready ||
    resolution.knowledge_published ||
    resolution.retrieval_published ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An approved publication-ready generation is required");
  const response = await apiFetch(
    `/api/v1/knowledge/final-resolutions/${encodeURIComponent(resolution.resolution_id)}/publication-preparations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-publication-preparation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-publication-preparation-input.v1",
        final_resolution_digest: resolution.canonical_digest,
        preparation_policy_id: policyId,
        preparation_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_immutable_approved_generation: true,
        acknowledged_metadata_only_preparation: true,
        acknowledged_no_processing_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge publication preparation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafePreparation(payload))
    throw new Error("Publication preparation returned unsafe content or authority-bearing data");
  return payload;
}
