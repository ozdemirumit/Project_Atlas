export type RecommendationPlanStep = {
  step_id: string;
  order: number;
  phase: string;
  conceptual_action: string;
  capability_id: string | null;
  capability_class: string;
  expected_output: string;
  stop_condition: string;
  executable_by_atlas: boolean;
};

export type RecommendationOption = {
  option_id: string;
  version: number;
  category: string;
  state: "viable" | "blocked";
  preference: "preferred" | "alternative" | "ineligible";
  title: string;
  intended_outcome: string;
  plan_steps: RecommendationPlanStep[];
  supporting_evidence: string[];
  contradicting_evidence: string[];
  assumptions: string[];
  unknowns: string[];
  confidence: string;
  confidence_rationale: string;
  risk_dimensions: Array<{ dimension: string; level: string; rationale: string }>;
  overall_risk: string;
  impact: {
    affected_components: string[];
    possibly_affected_services: string[];
    explicitly_unaffected_entities: string[];
    blast_radius: string;
    redundancy_effect: string;
    data_protection_effect: string;
    impact_confirmed: boolean;
    graph_maturity: string;
    gaps: string[];
  };
  duration: {
    minimum_minutes: number;
    maximum_minutes: number;
    basis: string;
    confidence: string;
  };
  interruption: {
    expected_mode: string;
    worst_credible_mode: string;
    expected_minutes: [number, number];
    worst_credible_minutes: [number, number];
    assumptions: string[];
    unknowns: string[];
  };
  preconditions: string[];
  success_criteria: string[];
  verification_criteria: string[];
  stop_conditions: string[];
  recovery: {
    strategy: string;
    rollback_feasible: boolean;
    point_of_no_return: string;
    trigger_conditions: string[];
    data_implications: string;
    gaps: string[];
  };
  governance: {
    required_roles: string[];
    policy_references: string[];
    approval_required: boolean;
    itsm_record_required: boolean;
    vendor_support_required: boolean;
    human_handoff: string;
  };
  residual_risk: string[];
  policy_outcome: string;
  exclusion_reasons: string[];
};

export type RecommendationArtifact = {
  recommendation_id: string;
  version: number;
  prior_version_id: string | null;
  owner: string;
  state: string;
  created_at: string;
  expires_at: string;
  target_id: string;
  decision_question: string;
  accountable_audience: string;
  horizon: string;
  constraints: string[];
  source_case_id: string;
  source_case_version: number;
  source_case_state: string;
  options: RecommendationOption[];
  comparisons: Array<{
    dimension: string;
    precedence: number;
    option_values: Array<[string, string]>;
    rationale: string;
  }>;
  preferred_option_id: string | null;
  preference_rationale: string;
  policy_constraints: string[];
  excluded_option_ids: string[];
  human_review: {
    status: string;
    reviewer_id: string | null;
    reviewed_at: string | null;
    rationale: string | null;
  };
  execution_authorized: boolean;
  safety_notice: string;
};

type RecommendationResponse = {
  data: RecommendationArtifact;
  meta: { correlation_id: string; generated_at: string };
};

export async function createStorageRecommendation(
  targetId: string,
  sourceCaseId: string,
  sourceCaseVersion: number,
): Promise<RecommendationResponse> {
  const response = await fetch(
    `/api/v1/recommendations/storage/${encodeURIComponent(targetId)}`,
    {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        source_case_id: sourceCaseId,
        source_case_version: sourceCaseVersion,
        decision_question: "What is the safest next operational choice?",
        accountable_audience: "Storage Operations",
        horizon: "immediate_response",
        constraints: ["No infrastructure change", "C1 read-only maximum"],
        maximum_capability_class: "C1",
        max_options: 5,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Recommendation request failed with ${response.status}`);
  }
  return (await response.json()) as RecommendationResponse;
}
