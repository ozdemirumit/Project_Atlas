import { apiFetch } from "./client";
import type { OperationalKnowledgeRetrievalResult } from "./protectedRetrieval";

export type ProtectedModelContext = {
  context_id: string;
  schema_version: "atlas.protected-model-context.v1";
  version: 1;
  retrieval_id: string;
  retrieval_digest: string;
  publication_id: string;
  organization_id: string;
  environment_id: string;
  classification: string;
  access_policy_id: string;
  context_policy_id: string;
  context_policy_digest: string;
  context_policy_version: string;
  assembler_id: string;
  assembly_receipt_digest: string;
  objective_digest: string;
  context_package_digest: string;
  evidence_set_digest: string;
  citation_set_digest: string;
  safety_validation_digest: string;
  budget_allocation_digest: string;
  destination_profile_digest: string;
  task_class: string;
  output_schema_version: string;
  included_evidence_count: number;
  character_count: number;
  estimated_token_count: number;
  maximum_context_characters: number;
  maximum_estimated_tokens: number;
  outcome: string;
  assembled_at: string;
  expires_at: string;
  instance_state: "protected_model_context_assembled" | "protected_model_context_insufficient";
  purpose: string;
  canonical_digest: string;
  knowledge_retrieved: true;
  model_context_available: boolean;
  model_invoked: false;
  answer_generated: false;
  graph_updated: false;
  scheduled: false;
  workflow_continued: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ProtectedModelContextResult = {
  context: ProtectedModelContext;
  manifest: {
    context_id: string;
    retrieval_id: string;
    task_class: string;
    output_schema_version: string;
    classification: string;
    included_evidence_count: number;
    character_count: number;
    estimated_token_count: number;
    maximum_context_characters: number;
    maximum_estimated_tokens: number;
    outcome: string;
    evidence_set_digest: string;
    citation_set_digest: string;
    safety_validation_digest: string;
    context_package_digest: string;
    assembled_at: string;
    expires_at: string;
  };
};

const forbiddenFields = [
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "authorization_context_digest",
  "protected_artifact_reference",
  "protected_artifact_digest",
  "claim_id",
  "objective",
  "query",
  "evidence",
  "excerpt",
  "source_title",
  "citation_location",
  "platform_safety_layer",
  "task_contract_layer",
  "output_contract_layer",
  "prompt",
  "model_id",
  "endpoint_url",
  "tool_call",
  "workflow_id",
];

function isSafeContext(value: unknown): value is { data: ProtectedModelContextResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const context = result.context;
  const manifest = result.manifest;
  if (!context || typeof context !== "object" || !manifest || typeof manifest !== "object")
    return false;
  const record = context as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-model-context.v1" &&
    record.version === 1 &&
    record.knowledge_retrieved === true &&
    record.model_invoked === false &&
    record.answer_generated === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    typeof safeManifest.context_id === "string" &&
    typeof safeManifest.included_evidence_count === "number" &&
    forbiddenFields.every((field) => !(field in record) && !(field in safeManifest))
  );
}

export async function createProtectedModelContext(input: {
  retrievalResult: OperationalKnowledgeRetrievalResult;
  policyId: string;
  policyDigest: string;
  objective: string;
}) {
  const { retrievalResult, policyId, policyDigest, objective } = input;
  const retrieval = retrievalResult.retrieval;
  if (
    !retrieval.knowledge_retrieved ||
    retrieval.model_context_available ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    objective.trim().length < 3
  )
    throw new Error("An exact authorized protected retrieval is required");
  const response = await apiFetch(
    `/api/v1/ai/retrievals/${encodeURIComponent(retrieval.retrieval_id)}/model-contexts`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-model-context.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-model-context-input.v1",
        retrieval_digest: retrieval.canonical_digest,
        context_policy_id: policyId,
        context_policy_digest: policyDigest,
        objective: objective.trim(),
        purpose: retrieval.purpose,
        acknowledged_untrusted_intent: true,
        acknowledged_citation_boundaries: true,
        acknowledged_no_model_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Protected model-context assembly failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeContext(payload))
    throw new Error("Model-context assembly returned protected or authority-bearing data");
  return payload;
}
