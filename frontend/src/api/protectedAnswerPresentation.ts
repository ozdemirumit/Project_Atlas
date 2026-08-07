import { apiFetch } from "./client";
import type { ProtectedDraftAdjudicationResult } from "./protectedDraftAdjudication";

export type ProtectedAnswerPresentationResult = {
  presentation: {
    presentation_id: string;
    schema_version: "atlas.protected-answer-presentation.v1";
    version: 1;
    adjudication_id: string;
    adjudication_digest: string;
    invocation_id: string;
    context_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    presentation_policy_id: string;
    presenter_id: string;
    answer_digest: string;
    citation_count: number;
    unknown_count: number;
    byte_count: number;
    media_type: "text/plain";
    presented_at: string;
    expires_at: string;
    instance_state: "protected_answer_presented";
    purpose: string;
    canonical_digest: string;
    answer_presented: true;
    recommendation_generated: false;
    graph_updated: false;
    scheduled: false;
    workflow_continued: false;
    execution_authorized: false;
    deployment_approved: false;
    infrastructure_mutation_performed: false;
  };
  manifest: {
    presentation_id: string;
    adjudication_id: string;
    summary_character_count: number;
    citation_count: number;
    unknown_count: number;
    byte_count: number;
    media_type: "text/plain";
    answer_digest: string;
    presented_at: string;
    expires_at: string;
  };
  answer: {
    presentation_id: string;
    summary: string;
    citation_references: string[];
    unknowns: string[];
    media_type: "text/plain";
    byte_count: number;
    generated_at: string;
    expires_at: string;
    canonical_digest: string;
  };
};

const forbiddenFields = [
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "presentation_authorization_digest",
  "context_package_digest",
  "protected_report_reference",
  "protected_draft_reference",
  "secret_reference",
  "endpoint_url",
  "tool_call",
  "command",
];

function isSafePresentation(
  value: unknown,
): value is { data: ProtectedAnswerPresentationResult } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const presentation = result.presentation;
  const manifest = result.manifest;
  const answer = result.answer;
  if (
    !presentation ||
    typeof presentation !== "object" ||
    !manifest ||
    typeof manifest !== "object" ||
    !answer ||
    typeof answer !== "object"
  )
    return false;
  const record = presentation as Record<string, unknown>;
  const content = answer as Record<string, unknown>;
  return (
    record.schema_version === "atlas.protected-answer-presentation.v1" &&
    record.answer_presented === true &&
    record.recommendation_generated === false &&
    record.graph_updated === false &&
    record.scheduled === false &&
    record.workflow_continued === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    content.media_type === "text/plain" &&
    typeof content.summary === "string" &&
    Array.isArray(content.citation_references) &&
    Array.isArray(content.unknowns) &&
    forbiddenFields.every(
      (field) => !(field in record) && !(field in content) && !(field in manifest),
    )
  );
}

export async function createProtectedAnswerPresentation(input: {
  adjudicationResult: ProtectedDraftAdjudicationResult;
  policyId: string;
  policyDigest: string;
}) {
  const { adjudicationResult, policyId, policyDigest } = input;
  const adjudication = adjudicationResult.adjudication;
  if (
    !adjudication.model_draft_adjudicated ||
    adjudication.answer_generated ||
    adjudication.outcome !== "adjudication-outcome.eligible" ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact eligible protected draft adjudication is required");
  const response = await apiFetch(
    `/api/v1/ai/draft-adjudications/${encodeURIComponent(adjudication.adjudication_id)}/presentations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-answer-presentation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-answer-presentation-input.v1",
        adjudication_digest: adjudication.canonical_digest,
        presentation_policy_id: policyId,
        presentation_policy_digest: policyDigest,
        purpose: adjudication.purpose,
        acknowledged_bounded_decision_support: true,
        acknowledged_citations_and_unknowns_are_material: true,
        acknowledged_no_recommendation_or_operational_authority: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Protected answer presentation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafePresentation(payload))
    throw new Error("Answer presentation returned unsafe content or operational authority");
  return payload;
}
