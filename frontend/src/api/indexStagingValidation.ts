import { apiFetch } from "./client";
import type { OperationalKnowledgeEmbeddingSet } from "./embeddingGeneration";

export type OperationalKnowledgeIndexStage = {
  index_staging_id: string;
  schema_version: "atlas.operational-knowledge-index-staging.v1";
  version: 1;
  embedding_set_id: string;
  embedding_set_digest: string;
  chunk_set_id: string;
  materialization_id: string;
  preparation_id: string;
  resolution_id: string;
  review_request_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  index_policy_id: string;
  index_policy_digest: string;
  index_policy_version: string;
  index_profile_id: string;
  index_profile_digest: string;
  staging_boundary_id: string;
  staging_boundary_digest: string;
  authorization_payload_profile_digest: string;
  indexer_id: string;
  index_receipt_digest: string;
  model_profile_digest: string;
  vector_dimension: number;
  normalization_profile_id: string;
  distance_metric_id: string;
  embedding_count: number;
  vector_manifest_digest: string;
  chunk_vector_binding_digest: string;
  governance_binding_digest: string;
  staged_point_count: number;
  projection_manifest_digest: string;
  point_coverage_digest: string;
  authorization_metadata_validation_digest: string;
  model_compatibility_validation_digest: string;
  isolation_validation_digest: string;
  reconciliation_digest: string;
  instance_state: "operational_knowledge_index_validated";
  canonical_digest: string;
  knowledge_approved: true;
  publication_ready: true;
  publication_prepared: true;
  source_materialized: true;
  chunks_created: true;
  embeddings_created: true;
  index_staged: true;
  index_validated: true;
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
  "point_ids",
  "collection_name",
  "vector_values",
  "payload",
  "query_results",
  "model_endpoint",
  "token_stream",
  "encryption_key",
  "index_steward_subject_digest",
  "upstream_accountable_subject_digests",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafeIndexStage(value: unknown): value is { data: OperationalKnowledgeIndexStage } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-index-staging.v1" &&
    record.version === 1 &&
    typeof record.index_staging_id === "string" &&
    /^[a-f0-9]{64}$/.test(String(record.projection_manifest_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.reconciliation_digest)) &&
    Number.isInteger(record.staged_point_count) &&
    Number(record.staged_point_count) > 0 &&
    record.staged_point_count === record.embedding_count &&
    record.instance_state === "operational_knowledge_index_validated" &&
    record.knowledge_approved === true &&
    record.publication_ready === true &&
    record.publication_prepared === true &&
    record.source_materialized === true &&
    record.chunks_created === true &&
    record.embeddings_created === true &&
    record.index_staged === true &&
    record.index_validated === true &&
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

export async function createOperationalKnowledgeIndexStage(input: {
  embeddingSet: OperationalKnowledgeEmbeddingSet;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { embeddingSet, policyId, policyDigest, purpose } = input;
  if (
    !embeddingSet.embeddings_created ||
    embeddingSet.index_staged ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact completed protected embedding set is required");
  const response = await apiFetch(
    `/api/v1/knowledge/embedding-sets/${encodeURIComponent(embeddingSet.embedding_set_id)}/index-stages`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-index-staging.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-index-input.v1",
        embedding_set_digest: embeddingSet.canonical_digest,
        index_policy_id: policyId,
        index_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_protected_vector_boundary: true,
        acknowledged_inactive_projection: true,
        acknowledged_no_publication_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge index staging failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeIndexStage(payload))
    throw new Error("Index staging returned unsafe content or authority-bearing data");
  return payload;
}
