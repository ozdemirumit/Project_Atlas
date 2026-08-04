import { apiFetch, ApiRequestError } from "./client";

export type ApprovalPlanStep = {
  order: number;
  step_id: string;
  conceptual_action: string;
  capability_id: string | null;
  capability_class: string;
  expected_output: string;
  stop_condition: string;
};

export type ApprovalRecord = {
  request_id: string;
  version: number;
  state: "pending" | "approved" | "rejected" | "needs_evidence" | "deferred" | "expired";
  packet: {
    canonicalization_version: string;
    canonical_digest: string;
    requested_by: string;
    purpose: string;
    created_at: string;
    expires_at: string;
    target_id: string;
    recommendation_id: string;
    recommendation_version: number;
    option_id: string;
    option_version: number;
    option_title: string;
    option_category: string;
    option_confidence: string;
    confidence_rationale: string;
    overall_risk: string;
    risk_rationales: string[];
    evidence_references: string[];
    evidence_summaries: string[];
    alternatives: string[];
    assumptions: string[];
    unknowns: string[];
    affected_components: string[];
    possibly_affected_services: string[];
    blast_radius: string;
    impact_confirmed: boolean;
    graph_maturity: string;
    impact_gaps: string[];
    duration_minimum_minutes: number;
    duration_maximum_minutes: number;
    interruption_expected_mode: string;
    interruption_worst_credible_mode: string;
    interruption_expected_minutes: [number, number];
    interruption_worst_credible_minutes: [number, number];
    interruption_unknowns: string[];
    plan_steps: ApprovalPlanStep[];
    preconditions: string[];
    verification_criteria: string[];
    stop_conditions: string[];
    recovery_strategy: string;
    rollback_feasible: boolean;
    recovery_duration_minimum_minutes: number;
    recovery_duration_maximum_minutes: number;
    recovery_gaps: string[];
    policy_constraints: string[];
    execution_authorized: boolean;
  };
  decisions: Array<{
    decision_id: string;
    request_version: number;
    outcome: string;
    reviewer_id: string;
    decided_at: string;
    rationale: string;
  }>;
  execution_authorized: boolean;
};

type ApprovalResponse = {
  data: ApprovalRecord;
  meta: { correlation_id: string; generated_at: string };
};

export async function createApprovalRequest(
  targetId: string,
  recommendationId: string,
  recommendationVersion: number,
  optionId: string,
): Promise<ApprovalResponse> {
  const response = await apiFetch(`/api/v1/approvals/storage/${encodeURIComponent(targetId)}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      recommendation_id: recommendationId,
      recommendation_version: recommendationVersion,
      option_id: optionId,
      purpose: "Review the bounded evidence-supported operational recommendation.",
      expires_in_minutes: 60,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Approval request failed", response.status);
  return (await response.json()) as ApprovalResponse;
}

export async function getApprovalRequest(requestId: string): Promise<ApprovalResponse> {
  const response = await apiFetch(`/api/v1/approvals/${encodeURIComponent(requestId)}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Approval request unavailable", response.status);
  return (await response.json()) as ApprovalResponse;
}

export async function decideApprovalRequest(
  requestId: string,
  version: number,
  outcome: "approve" | "reject" | "needs_evidence" | "defer",
  rationale: string,
): Promise<ApprovalResponse> {
  const response = await apiFetch(
    `/api/v1/approvals/${encodeURIComponent(requestId)}/decisions`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `approval-ui-${crypto.randomUUID()}`,
      },
      body: JSON.stringify({ outcome, rationale, expected_version: version }),
    },
  );
  if (!response.ok) throw new ApiRequestError("Approval decision failed", response.status);
  return (await response.json()) as ApprovalResponse;
}
