import { apiFetch } from "./client";
import type { OperationalKnowledgeRetrievalPublication } from "./retrievalIndexPublication";

export type OperationalKnowledgeEvidence = {
  evidence_reference_id: string;
  source_title: string;
  source_class: string;
  excerpt: string;
  citation_location: string;
  applicability: string;
  lifecycle_state: string;
  freshness_state: string;
  conflict_state: string;
  safety_state: string;
  rank_band: string;
};

export type OperationalKnowledgeRetrieval = {
  retrieval_id: string;
  schema_version: "atlas.operational-knowledge-retrieval.v1";
  version: 1;
  publication_id: string;
  publication_digest: string;
  knowledge_item_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  access_policy_id: string;
  retention_policy_id: string;
  retrieval_policy_id: string;
  retrieval_policy_digest: string;
  retrieval_policy_version: string;
  retriever_id: string;
  retrieval_receipt_digest: string;
  query_digest: string;
  authorization_context_digest: string;
  evidence_package_digest: string;
  result_count: number;
  outcome: string;
  retrieved_at: string;
  expires_at: string;
  instance_state: "operational_knowledge_retrieved";
  purpose: string;
  canonical_digest: string;
  knowledge_retrieved: true;
  model_context_available: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type OperationalKnowledgeRetrievalResult = {
  retrieval: OperationalKnowledgeRetrieval;
  evidence: {
    query: string;
    results: OperationalKnowledgeEvidence[];
    outcome: string;
    generated_at: string;
    expires_at: string;
    canonical_digest: string;
  };
};

const forbiddenFields = [
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "protected_artifact_reference",
  "protected_artifact_digest",
  "claim_id",
  "collection_name",
  "alias_name",
  "point_ids",
  "vector_values",
  "authorization_filters",
  "raw_similarity_score",
  "model_context",
  "tool_call",
  "workflow_id",
];

function isSafeRetrieval(value: unknown): value is { data: OperationalKnowledgeRetrievalResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const retrieval = result.retrieval;
  const evidence = result.evidence;
  if (!retrieval || typeof retrieval !== "object" || !evidence || typeof evidence !== "object")
    return false;
  const record = retrieval as Record<string, unknown>;
  const packageRecord = evidence as Record<string, unknown>;
  return (
    record.schema_version === "atlas.operational-knowledge-retrieval.v1" &&
    record.version === 1 &&
    record.instance_state === "operational_knowledge_retrieved" &&
    record.knowledge_retrieved === true &&
    record.model_context_available === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    typeof packageRecord.query === "string" &&
    Array.isArray(packageRecord.results) &&
    forbiddenFields.every((field) => !(field in record) && !(field in packageRecord))
  );
}

export async function createOperationalKnowledgeRetrieval(input: {
  publication: OperationalKnowledgeRetrievalPublication;
  policyId: string;
  policyDigest: string;
  query: string;
  purpose: string;
}) {
  const { publication, policyId, policyDigest, query, purpose } = input;
  if (
    !publication.retrieval_published ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    query.trim().length < 3 ||
    purpose.trim().length < 20
  )
    throw new Error("An exact active protected retrieval publication is required");
  const response = await apiFetch(
    `/api/v1/knowledge/retrieval-publications/${encodeURIComponent(publication.publication_id)}/retrievals`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `operational-knowledge-retrieval.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.operational-knowledge-retrieval-input.v1",
        publication_digest: publication.canonical_digest,
        retrieval_policy_id: policyId,
        retrieval_policy_digest: policyDigest,
        query: query.trim(),
        purpose: purpose.trim(),
        acknowledged_untrusted_evidence: true,
        acknowledged_unsafe_instructions: true,
        acknowledged_no_model_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Operational knowledge retrieval failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeRetrieval(payload))
    throw new Error("Protected retrieval returned unsafe or authority-bearing data");
  return payload;
}
