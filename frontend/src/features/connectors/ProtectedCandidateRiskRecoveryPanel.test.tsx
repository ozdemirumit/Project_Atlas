import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedCandidateImpactResult } from "../../api/protectedCandidateImpacts";
import { ProtectedCandidateRiskRecoveryPanel } from "./ProtectedCandidateRiskRecoveryPanel";

const impactResult = {
  impact_analysis: {
    impact_analysis_id: "protected-candidate-impact.test",
    schema_version: "atlas.protected-candidate-impact-analysis.v1",
    environment_id: "environment.development",
    canonical_digest: "a".repeat(64),
    purpose: "Complete bounded risk and recovery analysis.",
    service_impact_analyzed: true,
    impact_complete: false,
  },
  manifest: { candidate_count: 3 },
} as unknown as ProtectedCandidateImpactResult;

const completionResult = {
  completion: {
    completion_id: "protected-candidate-risk-recovery.test",
    schema_version: "atlas.protected-candidate-risk-recovery-completion.v1",
    service_impact_analyzed: true,
    impact_complete: true,
    outage_confirmed: false,
    interruption_established: true,
    duration_established: true,
    risk_completed: true,
    recovery_completed: true,
    recommendation_complete: false,
    recommendation_presented: false,
    recommendation_ready_for_review: false,
    recommendation_approved: false,
    workflow_created: false,
    execution_authorized: false,
    deployment_authorized: false,
    infrastructure_mutated: false,
  },
  manifest: {
    maximum_risk: "moderate",
    evidence_freshness: "current",
    evidence_completeness: "partial",
    low_risk_count: 0,
    moderate_risk_count: 3,
    high_risk_count: 0,
    critical_risk_count: 0,
    unknown_risk_count: 0,
    work_minimum_minutes: 0,
    work_maximum_minutes: 240,
    interruption_minimum_minutes: 0,
    interruption_maximum_minutes: 0,
    interruption_possible_count: 0,
    recovery_feasible_count: 3,
    recovery_unknown_count: 0,
    recovery_blocked_count: 0,
    recovery_minimum_minutes: 0,
    recovery_maximum_minutes: 5,
    gap_count: 1,
    unknown_count: 2,
    safety_notice:
      "Assessment completion does not select a candidate or grant operational authority.",
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedCandidateRiskRecoveryPanel", () => {
  it("submits only acknowledgements and presents a minimized aggregate", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: completionResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedCandidateRiskRecoveryPanel impactResult={impactResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Complete assessment" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "Risk, duration, and recovery estimates are evidence-bounded, not guarantees.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText("Missing or unknown evidence cannot reduce the assessed risk."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Completion creates no preference, workflow, approval, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Risk and recovery assessment completed")).toBeVisible();
    expect(screen.getByText(/Maximum risk: moderate/)).toBeVisible();
    const summary = screen.getByLabelText("Risk assessment summary");
    expect(within(summary).getByText("3 moderate")).toBeVisible();
    expect(screen.getByText(/Work estimate: 0-240 minutes/)).toBeVisible();
    expect(screen.getByText(/Recovery: 3 feasible/)).toBeVisible();
    expect(screen.queryByText("candidate.storage-controller-restart")).not.toBeInTheDocument();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-candidate-risk-recovery-input.v1",
      impact_digest: impactResult.impact_analysis.canonical_digest,
      acknowledged_estimates_are_not_guarantees: true,
      acknowledged_unknowns_cannot_lower_risk: true,
      acknowledged_no_preference_or_operational_authority: true,
    });
    for (const forbidden of [
      "candidate_id",
      "risk_dimensions",
      "work_duration",
      "interruption_duration",
      "recovery_strategy",
      "preference",
      "workflow",
      "command",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
