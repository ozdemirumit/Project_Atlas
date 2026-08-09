import { apiFetch } from "./client";
import type { ProtectedRecommendationAdjudicationResult } from "./protectedRecommendationAdjudications";

export type PresentedRecommendationOption = {
  role: "preferred" | "alternative" | "tied" | "unsupported";
  category: string;
  title: string;
  intended_outcome: string;
  rationale: string;
  confidence: string;
  confidence_rationale: string;
  steps: Array<{
    order: number;
    phase: string;
    conceptual_action: string;
    capability_class: "C0" | "C1";
  }>;
  overall_risk: "low" | "moderate" | "high" | "critical" | "unknown";
  work_minimum_minutes: number;
  work_maximum_minutes: number;
  interruption_expected_mode: string;
  interruption_minimum_minutes: number;
  interruption_maximum_minutes: number;
  recovery_feasibility: "feasible" | "not_required" | "unknown" | "blocked";
  recovery_minimum_minutes: number;
  recovery_maximum_minutes: number;
  technical_service_count: number;
  business_service_count: number;
  evidence_references: string[];
  assumptions: string[];
  unknowns: string[];
  evidence_gaps: string[];
  applicability_limits: string[];
  support_reasons: string[];
};

export type ProtectedRecommendationPresentationResult = {
  presentation: {
    presentation_id: string;
    schema_version: "atlas.protected-recommendation-presentation.v1";
    version: 1;
    adjudication_id: string;
    adjudication_digest: string;
    completion_id: string;
    candidate_set_id: string;
    impact_analysis_id: string;
    organization_id: string;
    environment_id: string;
    classification: string;
    presentation_policy_id: string;
    presentation_policy_digest: string;
    presentation_policy_version: string;
    presenter_id: string;
    presentation_receipt_digest: string;
    outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    evidence_reference_count: number;
    unknown_count: number;
    byte_count: number;
    media_type: "text/plain";
    presented_at: string;
    expires_at: string;
    instance_state: "protected_recommendation_presented";
    purpose: string;
    safety_notice: string;
    canonical_digest: string;
    recommendation_presented: true;
    recommendation_ready_for_review: false;
    recommendation_approved: false;
    workflow_created: false;
    execution_authorized: false;
    deployment_authorized: false;
    infrastructure_mutated: false;
    reused: boolean;
  };
  manifest: {
    outcome: "preferred" | "tie" | "no_support";
    option_count: number;
    preferred_count: number;
    evidence_reference_count: number;
    unknown_count: number;
    byte_count: number;
    media_type: "text/plain";
    recommendation_digest: string;
    presented_at: string;
    expires_at: string;
    safety_notice: string;
  };
  recommendation: {
    presentation_id: string;
    outcome: "preferred" | "tie" | "no_support";
    headline: string;
    safety_notice: string;
    options: PresentedRecommendationOption[];
    evidence_needs: string[];
    media_type: "text/plain";
    byte_count: number;
    presented_at: string;
    expires_at: string;
    canonical_digest: string;
  };
};

const forbiddenFields = new Set([
  "claim_id",
  "consumer_subject_digest",
  "browser_session_binding_digest",
  "presentation_authorization_digest",
  "source_binding_digest",
  "rendering_digest",
  "cleanup_digest",
  "candidate_id",
  "capability_id",
  "entity_id",
  "entity_ids",
  "relationship_id",
  "relationship_ids",
  "command",
  "endpoint",
  "tool_call",
]);

function hasForbiddenField(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenField);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, child]) => forbiddenFields.has(key) || hasForbiddenField(child),
  );
}

function isSafePresentationResult(
  value: unknown,
): value is { data: ProtectedRecommendationPresentationResult } {
  if (!value || typeof value !== "object" || !("data" in value) || hasForbiddenField(value))
    return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const result = data as Record<string, unknown>;
  const presentation = result.presentation as Record<string, unknown> | undefined;
  const recommendation = result.recommendation as Record<string, unknown> | undefined;
  const options = recommendation?.options;
  return (
    presentation?.schema_version === "atlas.protected-recommendation-presentation.v1" &&
    presentation.recommendation_presented === true &&
    presentation.recommendation_ready_for_review === false &&
    presentation.recommendation_approved === false &&
    presentation.workflow_created === false &&
    presentation.execution_authorized === false &&
    presentation.deployment_authorized === false &&
    presentation.infrastructure_mutated === false &&
    presentation.media_type === "text/plain" &&
    recommendation?.media_type === "text/plain" &&
    Array.isArray(options) &&
    options.length > 0 &&
    options.every((option) => {
      if (!option || typeof option !== "object") return false;
      const item = option as Record<string, unknown>;
      return (
        typeof item.title === "string" &&
        typeof item.overall_risk === "string" &&
        Array.isArray(item.steps) &&
        item.steps.length > 0
      );
    })
  );
}

export async function createProtectedRecommendationPresentation(input: {
  adjudicationResult: ProtectedRecommendationAdjudicationResult;
  policyId: string;
  policyDigest: string;
}) {
  const { adjudicationResult, policyId, policyDigest } = input;
  const adjudication = adjudicationResult.adjudication;
  if (
    !adjudication.recommendation_complete ||
    adjudication.recommendation_presented ||
    !/^[a-f0-9]{64}$/.test(policyDigest)
  )
    throw new Error("An exact protected recommendation adjudication is required");
  const response = await apiFetch(
    `/api/v1/ai/recommendation-adjudications/${encodeURIComponent(adjudication.adjudication_id)}/presentations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `protected-recommendation-presentation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.protected-recommendation-presentation-input.v1",
        adjudication_digest: adjudication.canonical_digest,
        presentation_policy_id: policyId,
        presentation_policy_digest: policyDigest,
        purpose: adjudication.purpose,
        acknowledged_decision_support_only: true,
        acknowledged_tie_or_no_support_is_valid: true,
        acknowledged_no_operational_authority: true,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Protected recommendation presentation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafePresentationResult(payload))
    throw new Error("Recommendation presentation returned protected content or authority");
  return payload;
}
