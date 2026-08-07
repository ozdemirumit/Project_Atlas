import { apiFetch } from "./client";
import type { OperationalKnowledgeIndexStage } from "./indexStagingValidation";

export type OperationalKnowledgeRetrievalPublication = {
  publication_id: string;
  schema_version: "atlas.operational-knowledge-retrieval-publication.v1";
  version: 1;
  index_staging_id: string;
  index_staging_digest: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  publication_policy_id: string;
  publication_policy_digest: string;
  publication_profile_id: string;
  publication_profile_digest: string;
  retrieval_route_profile_digest: string;
  publisher_id: string;
  publication_receipt_digest: string;
  projection_manifest_digest: string;
  route_generation_digest: string;
  activation_digest: string;
  route_verification_digest: string;
  authorization_enforcement_digest: string;
  lifecycle_filter_digest: string;
  rollback_metadata_digest: string;
  instance_state: "operational_knowledge_retrieval_published";
  canonical_digest: string;
  knowledge_approved: true;
  publication_ready: true;
  publication_prepared: true;
  source_materialized: true;
  chunks_created: true;
  embeddings_created: true;
  index_staged: true;
  index_validated: true;
  knowledge_published: true;
  retrieval_published: true;
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
  "chunk_coordinates",
  "chunk_id_map",
  "point_ids",
  "collection_name",
  "alias_name",
  "vector_values",
  "payload",
  "filters",
  "query_results",
  "model_endpoint",
  "token_stream",
  "encryption_key",
  "publication_steward_subject_digest",
  "upstream_accountable_subject_digests",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafePublication(
  value: unknown,
): value is { data: OperationalKnowledgeRetrievalPublication } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-retrieval-publication.v1" &&
    record.version === 1 &&
    typeof record.publication_id === "string" &&
    /^[a-f0-9]{64}$/.test(String(record.route_generation_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.route_verification_digest)) &&
    record.instance_state === "operational_knowledge_retrieval_published" &&
    record.knowledge_approved === true &&
    record.publication_ready === true &&
    record.publication_prepared === true &&
    record.source_materialized === true &&
    record.chunks_created === true &&
    record.embeddings_created === true &&
    record.index_staged === true &&
    record.index_validated === true &&
    record.knowledge_published === true &&
    record.retrieval_published === true &&
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

export async function createOperationalKnowledgeRetrievalPublication(input: {
  indexStage: OperationalKnowledgeIndexStage;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { indexStage, policyId, policyDigest, purpose } = input;
  if (
    !indexStage.index_validated ||
    indexStage.retrieval_published ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact validated inactive retrieval index is required");
  const response = await apiFetch(
    `/api/v1/knowledge/index-stages/${encodeURIComponent(indexStage.index_staging_id)}/publications`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-retrieval-publication.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-retrieval-publication-input.v1",
        index_staging_digest: indexStage.canonical_digest,
        publication_policy_id: policyId,
        publication_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_policy_filtered_visibility: true,
        acknowledged_no_vector_store_disclosure: true,
        acknowledged_no_context_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge retrieval publication failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafePublication(payload))
    throw new Error("Retrieval publication returned unsafe content or authority-bearing data");
  return payload;
}
