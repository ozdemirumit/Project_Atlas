import { apiFetch } from "./client";
import type { ProtectedModelInvocationResult } from "./protectedModelInvocation";

export type ProtectedDraftAdjudicationResult = {
  adjudication: {
    adjudication_id: string;
    schema_version: "atlas.protected-draft-adjudication.v1";
    version: 1;
    invocation_id: string;
    invocation_digest: string;
    context_id: string;
    organization_id: string;
    environment_id: string;
    adjudication_policy_id: string;
    adjudicator_id: string;
    outcome: string;
    canonical_digest: string;
    model_invoked: true;
    protected_draft_available: true;
    model_draft_adjudicated: true;
    answer_generated: false;
    graph_updated: false;
    scheduled: false;
    workflow_continued: false;
    execution_authorized: false;
    deployment_approved: false;
    infrastructure_mutation_performed: false;
  };
  manifest: {
    adjudication_id: string;
    invocation_id: string;
    context_id: string;
    outcome: string;
    check_count: number;
    citation_count: number;
    unknown_count: number;
    report_digest: string;
    check_set_digest: string;
    citation_coverage_digest: string;
    unknown_preservation_digest: string;
    prohibited_output_digest: string;
    adjudicated_at: string;
    expires_at: string;
  };
};

const forbidden = ["summary", "unknowns", "draft", "evidence", "check_codes", "protected_report_reference", "protected_report_digest", "consumer_subject_digest", "browser_session_binding_digest", "adjudication_authorization_digest", "prompt", "endpoint_url", "secret_reference", "tool_call"];

function isSafe(value: unknown): value is { data: ProtectedDraftAdjudicationResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const adjudication = result.adjudication;
  const manifest = result.manifest;
  if (!adjudication || typeof adjudication !== "object" || !manifest || typeof manifest !== "object") return false;
  const record = adjudication as Record<string, unknown>;
  const safeManifest = manifest as Record<string, unknown>;
  return record.schema_version === "atlas.protected-draft-adjudication.v1" && record.model_draft_adjudicated === true && record.answer_generated === false && record.graph_updated === false && record.scheduled === false && record.workflow_continued === false && record.execution_authorized === false && record.deployment_approved === false && record.infrastructure_mutation_performed === false && typeof safeManifest.check_count === "number" && forbidden.every((field) => !(field in record) && !(field in safeManifest));
}

export async function createProtectedDraftAdjudication(input: { invocationResult: ProtectedModelInvocationResult; policyId: string; policyDigest: string }) {
  const { invocationResult, policyId, policyDigest } = input;
  const invocation = invocationResult.invocation;
  if (!invocation.model_invoked || !invocation.protected_draft_available || invocation.answer_generated || !/^[a-f0-9]{64}$/.test(policyDigest)) throw new Error("An exact protected model invocation is required");
  const response = await apiFetch(`/api/v1/ai/model-invocations/${encodeURIComponent(invocation.invocation_id)}/adjudications`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", "Idempotency-Key": `protected-draft-adjudication.${crypto.randomUUID()}` },
    body: JSON.stringify({ schema_version: "atlas.protected-draft-adjudication-input.v1", invocation_digest: invocation.canonical_digest, adjudication_policy_id: policyId, adjudication_policy_digest: policyDigest, purpose: invocation.purpose, acknowledged_draft_is_untrusted: true, acknowledged_no_content_presentation: true, acknowledged_no_answer_or_operational_authority: true }),
  });
  if (!response.ok) throw new Error(`Protected draft adjudication failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafe(payload)) throw new Error("Draft adjudication returned protected content or authority");
  return payload;
}
