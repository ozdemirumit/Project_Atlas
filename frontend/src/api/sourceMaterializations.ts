import { apiFetch } from "./client";
import type { OperationalKnowledgePublicationPreparation } from "./publicationPreparations";

export type OperationalKnowledgeSourceMaterialization = {
  materialization_id: string;
  schema_version: "atlas.operational-knowledge-source-materialization.v1";
  version: 1;
  preparation_id: string;
  preparation_digest: string;
  resolution_id: string;
  source_draft_id: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  materialization_policy_id: string;
  materialization_policy_digest: string;
  canonicalization_profile_id: string;
  source_security_profile_id: string;
  materializer_id: string;
  materialization_receipt_digest: string;
  source_artifact_digest: string;
  protected_material_digest: string;
  chunking_profile_digest: string;
  media_type: string;
  source_bytes: number;
  canonical_bytes: number;
  canonical_characters: number;
  security_scan_evidence_digest: string;
  governance_binding_digest: string;
  instance_state: "operational_knowledge_source_materialized";
  canonical_digest: string;
  knowledge_approved: true;
  publication_ready: true;
  publication_prepared: true;
  source_materialized: true;
  chunks_created: false;
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
  "source_coordinate",
  "destination_coordinate",
  "encryption_key",
  "materialized_by_subject_digest",
  "publication_steward_subject_digest",
  "browser_session_binding_digest",
  "request_binding_digest",
  "idempotency_digest",
];

function isSafeMaterialization(
  value: unknown,
): value is { data: OperationalKnowledgeSourceMaterialization } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-source-materialization.v1" &&
    record.version === 1 &&
    typeof record.materialization_id === "string" &&
    /^[a-f0-9]{64}$/.test(String(record.protected_material_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.chunking_profile_digest)) &&
    /^[a-f0-9]{64}$/.test(String(record.materialization_receipt_digest)) &&
    record.instance_state === "operational_knowledge_source_materialized" &&
    record.knowledge_approved === true &&
    record.publication_ready === true &&
    record.publication_prepared === true &&
    record.source_materialized === true &&
    record.chunks_created === false &&
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

export async function createOperationalKnowledgeSourceMaterialization(input: {
  preparation: OperationalKnowledgePublicationPreparation;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { preparation, policyId, policyDigest, purpose } = input;
  if (
    !preparation.publication_prepared ||
    preparation.chunks_created ||
    preparation.index_staged ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  )
    throw new Error("An exact completed publication preparation is required");
  const response = await apiFetch(
    `/api/v1/knowledge/publication-preparations/${encodeURIComponent(preparation.preparation_id)}/source-materializations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-source-materialization.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-source-materialization-input.v1",
        publication_preparation_digest: preparation.canonical_digest,
        materialization_policy_id: policyId,
        materialization_policy_digest: policyDigest,
        purpose: purpose.trim(),
        acknowledged_immutable_approved_source: true,
        acknowledged_protected_content_boundary: true,
        acknowledged_no_chunking_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge source materialization failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeMaterialization(payload))
    throw new Error("Source materialization returned unsafe content or authority-bearing data");
  return payload;
}
