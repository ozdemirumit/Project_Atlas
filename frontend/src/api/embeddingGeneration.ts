import { apiFetch } from "./client";
import type { OperationalKnowledgeChunkSet } from "./deterministicChunking";

export type OperationalKnowledgeEmbeddingSet = {
  embedding_set_id: string;
  schema_version: "atlas.operational-knowledge-embedding-set.v1";
  version: 1;
  chunk_set_id: string;
  chunk_set_digest: string;
  materialization_id: string;
  preparation_id: string;
  resolution_id: string;
  review_request_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  embedding_policy_id: string;
  embedding_policy_digest: string;
  embedding_policy_version: string;
  model_profile_id: string;
  model_profile_digest: string;
  model_artifact_digest: string;
  tokenizer_profile_digest: string;
  vector_dimension: number;
  normalization_profile_id: string;
  distance_metric_id: string;
  data_boundary_id: string;
  data_boundary_digest: string;
  embedder_id: string;
  embedding_receipt_digest: string;
  protected_material_digest: string;
  ordered_chunk_manifest_digest: string;
  chunking_profile_digest: string;
  governance_binding_digest: string;
  embedding_count: number;
  vector_manifest_digest: string;
  chunk_vector_binding_digest: string;
  numeric_validation_digest: string;
  coverage_validation_digest: string;
  resource_evidence_digest: string;
  instance_state: "operational_knowledge_embeddings_created";
  canonical_digest: string;
  knowledge_approved: true;
  publication_ready: true;
  publication_prepared: true;
  source_materialized: true;
  chunks_created: true;
  embeddings_created: true;
  index_staged: false;
  index_validated: false;
  knowledge_published: false;
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
  "excerpt",
  "title",
  "chunk_coordinates",
  "chunk_id_map",
  "vector_values",
  "model_endpoint",
  "token_stream",
  "encryption_key",
  "embedded_by_subject_digest",
  "chunking_steward_subject_digest",
  "materialization_steward_subject_digest",
  "publication_steward_subject_digest",
  "browser_session_binding_digest",
  "upstream_accountable_subject_digests",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafeEmbeddingSet(
  value: unknown,
): value is { data: OperationalKnowledgeEmbeddingSet } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-embedding-set.v1" &&
    record.version === 1 &&
    typeof record.embedding_set_id === "string" &&
    /^[a-f0-9]{64}$/.test(String(record.vector_manifest_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.coverage_validation_digest)) &&
    Number.isInteger(record.embedding_count) &&
    Number(record.embedding_count) > 0 &&
    Number.isInteger(record.vector_dimension) &&
    Number(record.vector_dimension) > 0 &&
    record.instance_state === "operational_knowledge_embeddings_created" &&
    record.knowledge_approved === true &&
    record.publication_ready === true &&
    record.publication_prepared === true &&
    record.source_materialized === true &&
    record.chunks_created === true &&
    record.embeddings_created === true &&
    record.index_staged === false &&
    record.index_validated === false &&
    record.knowledge_published === false &&
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

export async function createOperationalKnowledgeEmbeddingSet(input: {
  chunkSet: OperationalKnowledgeChunkSet;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { chunkSet, policyId, policyDigest, purpose } = input;
  if (
    !chunkSet.chunks_created ||
    chunkSet.embeddings_created ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact completed protected chunk set is required");
  const response = await apiFetch(
    `/api/v1/knowledge/chunk-sets/${encodeURIComponent(chunkSet.chunk_set_id)}/embedding-sets`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-embedding-generation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-embedding-input.v1",
        chunk_set_digest: chunkSet.canonical_digest,
        embedding_policy_id: policyId,
        embedding_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_protected_chunk_boundary: true,
        acknowledged_immutable_model_profile: true,
        acknowledged_no_index_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge embedding generation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeEmbeddingSet(payload))
    throw new Error("Embedding generation returned unsafe content or authority-bearing data");
  return payload;
}
