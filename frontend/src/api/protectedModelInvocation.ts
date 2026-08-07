import { apiFetch } from "./client";
import type { ProtectedModelContextResult } from "./modelContextAssembly";

export type ProtectedModelInvocationResult = {
  invocation: {
    invocation_id: string;
    schema_version: "atlas.protected-model-invocation.v1";
    version: 1;
    context_id: string;
    context_digest: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    invocation_policy_id: string;
    invocation_policy_digest: string;
    invocation_policy_version: string;
    gateway_id: string;
    invocation_receipt_digest: string;
    endpoint_profile_id: string;
    endpoint_profile_digest: string;
    model_id: string;
    task_class: string;
    response_schema_version: string;
    draft_digest: string;
    citation_set_digest: string;
    output_safety_digest: string;
    input_tokens: number;
    output_tokens: number;
    maximum_output_tokens: number;
    finish_reason: string;
    outcome: string;
    invoked_at: string;
    expires_at: string;
    instance_state: "protected_model_invoked";
    purpose: string;
    canonical_digest: string;
    knowledge_retrieved: true;
    model_context_available: true;
    model_invoked: true;
    protected_draft_available: true;
    answer_generated: false;
    graph_updated: false;
    scheduled: false;
    workflow_continued: false;
    execution_authorized: false;
    deployment_approved: false;
    infrastructure_mutation_performed: false;
    reused: boolean;
  };
  manifest: {
    invocation_id: string;
    context_id: string;
    endpoint_profile_id: string;
    model_id: string;
    task_class: string;
    response_schema_version: string;
    citation_count: number;
    unknown_count: number;
    input_tokens: number;
    output_tokens: number;
    maximum_output_tokens: number;
    finish_reason: string;
    outcome: string;
    draft_digest: string;
    citation_set_digest: string;
    output_safety_digest: string;
    invoked_at: string;
    expires_at: string;
  };
};

const forbiddenFields = [
  "summary",
  "unknowns",
  "objective",
  "query",
  "evidence",
  "prompt",
  "protected_draft_reference",
  "protected_draft_digest",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "invocation_authorization_digest",
  "secret_reference",
  "endpoint_url",
  "tool_call",
];

function isSafeInvocation(value: unknown): value is { data: ProtectedModelInvocationResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const invocation = result.invocation;
  const manifest = result.manifest;
  if (!invocation || typeof invocation !== "object" || !manifest || typeof manifest !== "object")
    return false;
  const record = invocation as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-model-invocation.v1" &&
    record.model_invoked === true &&
    record.protected_draft_available === true &&
    record.answer_generated === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    typeof safeManifest.citation_count === "number" &&
    typeof safeManifest.unknown_count === "number" &&
    forbiddenFields.every((field) => !(field in record) && !(field in safeManifest))
  );
}

export async function createProtectedModelInvocation(input: {
  contextResult: ProtectedModelContextResult;
  policyId: string;
  policyDigest: string;
}) {
  const { contextResult, policyId, policyDigest } = input;
  const context = contextResult.context;
  if (!context.model_context_available || context.model_invoked || !/^[a-f0-9]{64}$/.test(policyDigest))
    throw new Error("An exact protected model context is required");
  const response = await apiFetch(
    `/api/v1/ai/model-contexts/${encodeURIComponent(context.context_id)}/invocations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-model-invocation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-model-invocation-input.v1",
        context_digest: context.canonical_digest,
        invocation_policy_id: policyId,
        invocation_policy_digest: policyDigest,
        purpose: context.purpose,
        acknowledged_draft_is_untrusted: true,
        acknowledged_citations_and_unknowns_require_validation: true,
        acknowledged_no_answer_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Protected model invocation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeInvocation(payload))
    throw new Error("Model invocation returned protected content or operational authority");
  return payload;
}
