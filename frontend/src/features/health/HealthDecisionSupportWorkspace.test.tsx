import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { InvestigationArtifact } from "../../api/investigations";
import type { RcaCase } from "../../api/rca";
import type { RecommendationArtifact } from "../../api/recommendations";
import HealthDecisionSupportWorkspace from "./HealthDecisionSupportWorkspace";

afterEach(cleanup);

const baseProps = {
  canBuildRca: false,
  canCompareOptions: false,
  investigationError: false,
  investigationPending: false,
  onBuildRca: vi.fn(),
  onCompareOptions: vi.fn(),
  rcaError: false,
  rcaPending: false,
  recommendationError: false,
  recommendationPending: false,
};

const reasoningArtifact = {
  artifact_id: "investigation.test",
  version: 2,
  summary: {
    confidence: "moderate",
    confidence_rationale: "The evidence is current but incomplete.",
    known: ["A path warning was observed."],
    inferred: ["Redundancy may be reduced."],
    unknowns: ["The physical path state is unknown."],
    safest_next_check: "Collect another read-only observation.",
    supported_decision: "Continue bounded diagnostics.",
    unsupported_decision: "Do not restart infrastructure.",
  },
  claims: [
    {
      claim_id: "claim.test",
      epistemic_type: "observation",
      confidence: "moderate",
      text: "A path warning was observed.",
      supporting_evidence: ["evidence.test"],
      contradicting_evidence: [],
    },
  ],
  hypotheses: [
    {
      hypothesis_id: "hypothesis.test",
      state: "provisional",
      confidence: "moderate",
      statement: "One path may be unavailable.",
      confidence_rationale: "A single current signal supports the hypothesis.",
      discriminating_checks: [
        { title: "Refresh path state", capability_class: "C1" },
      ],
    },
  ],
  timeline: [
    {
      event_id: "event.test",
      occurred_at: "2026-08-10T00:00:00Z",
      summary: "The warning entered the authorized evidence window.",
      evidence_references: ["evidence.test"],
    },
  ],
  stop_reason: "Further evidence is required.",
  safety_notice: "Decision support only.",
} as unknown as InvestigationArtifact;

const rcaCase = {
  case_id: "rca.test",
  version: 1,
  state: "provisional",
  severity: "warning",
  owner: "Storage Operations",
  target_id: "storage.test",
  incident_references: [{ reference_id: "INC-TEST" }],
  human_review: { status: "pending" },
  symptoms: [
    { statement: "One path reports a warning.", current_state: "Observed" },
  ],
  impact_scope: {
    affected_entities: ["storage.test"],
    possibly_affected_services: ["Service A"],
    explicitly_unaffected_entities: ["Service B"],
    limitations: ["The service graph is incomplete."],
  },
  hypotheses: [
    {
      hypothesis_id: "rca-hypothesis.test",
      rank: 1,
      cause_type: "path_state",
      confirmation_level: "provisional",
      statement: "A path may be unavailable.",
      mechanism: "The current observation reports reduced path health.",
      supporting_evidence: ["evidence.test"],
      contradicting_evidence: [],
      missing_expected_observations: ["Switch port state"],
      expected_sequence: ["Observe", "Correlate"],
      diagnostic_steps: [
        {
          step_id: "diagnostic.test",
          capability_class: "C1",
          question: "Is the path still unavailable?",
          capability_id: "storage.paths.read",
          timeout_seconds: 30,
          max_output_records: 20,
          approval_required: false,
        },
      ],
    },
  ],
  evidence_gaps: ["Current switch port state"],
  blocker: "No current switch evidence.",
  safest_next_step: "Collect bounded read-only evidence.",
  provisional_statement: {
    statement: "The available evidence supports a provisional path issue.",
    prevention_or_verification_implication: "Verify the path before planning a change.",
  },
  safety_notice: "No root cause is confirmed.",
} as unknown as RcaCase;

const recommendation = {
  recommendation_id: "recommendation.test",
  version: 1,
  state: "provisional",
  source_case_version: 1,
  source_case_state: "provisional",
  human_review: { status: "pending" },
  accountable_audience: "Storage Operations",
  expires_at: "2026-08-11T00:00:00Z",
  horizon: "immediate_response",
  preferred_option_id: "option.observe",
  preference_rationale: "Read-only evidence reduces uncertainty without operational risk.",
  options: [
    {
      option_id: "option.observe",
      category: "diagnostic",
      state: "viable",
      preference: "preferred",
      overall_risk: "low",
      title: "Collect read-only path evidence",
      intended_outcome: "Reduce uncertainty.",
      confidence: "moderate",
      duration: { minimum_minutes: 1, maximum_minutes: 5 },
      interruption: { expected_mode: "none" },
      plan_steps: [
        {
          step_id: "step.observe",
          order: 1,
          conceptual_action: "Collect the authorized path state.",
          capability_class: "C1",
          capability_id: "storage.paths.read",
        },
      ],
      recovery: { rollback_feasible: true },
      policy_outcome: "allowed_read_only",
      exclusion_reasons: [],
    },
    {
      option_id: "option.restart",
      category: "change",
      state: "blocked",
      preference: "ineligible",
      overall_risk: "critical",
      title: "Restart the controller",
      intended_outcome: "Attempt to restore path state.",
      confidence: "insufficient",
      duration: { minimum_minutes: 10, maximum_minutes: 30 },
      interruption: { expected_mode: "possible_outage" },
      plan_steps: [],
      recovery: { rollback_feasible: false },
      policy_outcome: "blocked",
      exclusion_reasons: ["No approval or execution authority exists."],
    },
  ],
  comparisons: [
    {
      dimension: "risk",
      option_values: [
        ["option.observe", "low"],
        ["option.restart", "critical"],
      ],
    },
  ],
  policy_constraints: ["No autonomous infrastructure change"],
  execution_authorized: false,
  safety_notice: "A recommendation is not an approval.",
} as unknown as RecommendationArtifact;

describe("HealthDecisionSupportWorkspace", () => {
  it("presents fail-closed investigation, RCA, and recommendation states", () => {
    render(<HealthDecisionSupportWorkspace {...baseProps} />);

    expect(screen.getByRole("heading", { name: "Reasoning artifact" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Governed RCA case" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Operational choices" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Build RCA case" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Compare options" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /execute|deploy|restart|apply/i })).toBeNull();
  });

  it("delegates governed actions only when the parent grants readiness", () => {
    const onBuildRca = vi.fn();
    const onCompareOptions = vi.fn();
    render(
      <HealthDecisionSupportWorkspace
        {...baseProps}
        canBuildRca
        canCompareOptions
        onBuildRca={onBuildRca}
        onCompareOptions={onCompareOptions}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Build RCA case" }));
    fireEvent.click(screen.getByRole("button", { name: "Compare options" }));

    expect(onBuildRca).toHaveBeenCalledOnce();
    expect(onCompareOptions).toHaveBeenCalledOnce();
  });

  it("keeps pending and failed states explicit", () => {
    const { rerender } = render(
      <HealthDecisionSupportWorkspace
        {...baseProps}
        investigationPending
        rcaPending
        recommendationPending
      />,
    );

    expect(screen.getByText("Assembling governed evidence")).toBeVisible();
    expect(screen.getByText("Building immutable RCA case")).toBeVisible();
    expect(screen.getByText("Comparing operational choices")).toBeVisible();

    rerender(
      <HealthDecisionSupportWorkspace
        {...baseProps}
        investigationError
        rcaError
        recommendationError
      />,
    );
    expect(screen.getAllByRole("alert")).toHaveLength(3);
  });

  it("presents epistemic, provisional, preferred, and blocked decision evidence", () => {
    render(
      <HealthDecisionSupportWorkspace
        {...baseProps}
        canBuildRca
        canCompareOptions
        rcaCase={rcaCase}
        reasoningArtifact={reasoningArtifact}
        recommendation={recommendation}
      />,
    );

    expect(screen.getByText("observation")).toBeVisible();
    expect(screen.getByText("Provisional cause statement")).toBeVisible();
    expect(screen.getAllByText("Collect read-only path evidence")).toHaveLength(2);
    expect(screen.getByText("Restart the controller")).toBeVisible();
    expect(screen.getByText("Blocked by policy and readiness")).toBeVisible();
    expect(screen.getByText("No execution authority")).toBeVisible();
  });
});
