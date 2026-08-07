import { apiFetch } from "./client";
import type { OperationalKnowledgeSourceMaterialization } from "./sourceMaterializations";

export type OperationalKnowledgeChunkSet = {
  chunk_set_id: string;
  schema_version: "atlas.operational-knowledge-chunk-set.v1";
  version: 1;
  materialization_id: string;
  materialization_digest: string;
  preparation_id: string;
  resolution_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  chunking_policy_id: string;
  chunking_policy_digest: string;
  algorithm_profile_id: string;
  algorithm_profile_digest: string;
  chunker_id: string;
  chunking_receipt_digest: string;
  protected_material_digest: string;
  chunking_profile_digest: string;
  ordered_chunk_manifest_digest: string;
  structure_manifest_digest: string;
  governance_binding_digest: string;
  determinism_evidence_digest: string;
  media_type: string;
  chunk_count: number;
  total_chunk_characters: number;
  total_chunk_tokens: number;
  minimum_chunk_characters: number;
  maximum_chunk_characters: number;
  overlap_characters: number;
  instance_state: "operational_knowledge_chunks_created";
  canonical_digest: string;
  knowledge_approved: true;
  publication_ready: true;
  publication_prepared: true;
  source_materialized: true;
  chunks_created: true;
  embeddings_created: false;
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
  "section_path",
  "page",
  "anchor",
  "ordinal_map",
  "chunk_coordinate",
  "token_stream",
  "chunked_by_subject_digest",
  "materialization_steward_subject_digest",
  "publication_steward_subject_digest",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafeChunkSet(value: unknown): value is { data: OperationalKnowledgeChunkSet } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-chunk-set.v1" &&
    record.version === 1 &&
    typeof record.chunk_set_id === "string" &&
    /^[a-f0-9]{64}$/.test(String(record.ordered_chunk_manifest_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.determinism_evidence_digest)) &&
    Number.isInteger(record.chunk_count) &&
    Number(record.chunk_count) > 0 &&
    record.instance_state === "operational_knowledge_chunks_created" &&
    record.knowledge_approved === true &&
    record.publication_ready === true &&
    record.publication_prepared === true &&
    record.source_materialized === true &&
    record.chunks_created === true &&
    record.embeddings_created === false &&
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

export async function createOperationalKnowledgeChunkSet(input: {
  materialization: OperationalKnowledgeSourceMaterialization;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { materialization, policyId, policyDigest, purpose } = input;
  if (
    !materialization.source_materialized ||
    materialization.chunks_created ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact completed source materialization is required");
  const response = await apiFetch(
    `/api/v1/knowledge/source-materializations/${encodeURIComponent(materialization.materialization_id)}/chunk-sets`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-deterministic-chunking.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-chunking-input.v1",
        source_materialization_digest: materialization.canonical_digest,
        chunking_policy_id: policyId,
        chunking_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_protected_content_boundary: true,
        acknowledged_immutable_chunking_profile: true,
        acknowledged_no_embedding_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge deterministic chunking failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeChunkSet(payload))
    throw new Error("Deterministic chunking returned unsafe content or authority-bearing data");
  return payload;
}
