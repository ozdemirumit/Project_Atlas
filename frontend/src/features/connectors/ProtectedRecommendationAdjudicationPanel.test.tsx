import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedCandidateRiskRecoveryResult } from "../../api/protectedCandidateRiskRecovery";
import { ProtectedRecommendationAdjudicationPanel } from "./ProtectedRecommendationAdjudicationPanel";

const completionResult = {
  completion: {
    completion_id: "protected-candidate-risk-recovery.test",
    schema_version: "atlas.protected-candidate-risk-recovery-completion.v1",
    environment_id: "environment.development",
    canonical_digest: "a".repeat(64),
    purpose: "Adjudicate exact protected candidates with deterministic policy controls.",
    risk_completed: true,
    recovery_completed: true,
    recommendation_complete: false,
  },
  manifest: { candidate_count: 3 },
} as unknown as ProtectedCandidateRiskRecoveryResult;

const adjudicationResult = {
  adjudication: {
    adjudication_id: "protected-recommendation-adjudication.test",
    schema_version: "atlas.protected-recommendation-adjudication.v1",
    service_impact_analyzed: true,
    impact_complete: true,
    interruption_established: true,
    duration_established: true,
    risk_completed: true,
    recovery_completed: true,
    recommendation_complete: true,
    recommendation_presented: false,
    recommendation_ready_for_review: false,
    recommendation_approved: false,
    workflow_created: false,
    execution_authorized: false,
    deployment_authorized: false,
    infrastructure_mutated: false,
  },
  manifest: {
    candidate_count: 3,
    dimension_count: 9,
    eligible_count: 3,
    excluded_count: 0,
    preferred_count: 1,
    alternative_count: 2,
    tie: false,
    no_supportable_candidate: false,
    maximum_risk: "moderate",
    gap_count: 3,
    unknown_count: 2,
    safety_notice:
      "Deterministic protected preference is decision support only; no operational authority is established.",
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedRecommendationAdjudicationPanel", () => {
  it("submits only acknowledgements and presents a minimized aggregate", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: adjudicationResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedRecommendationAdjudicationPanel completionResult={completionResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Adjudicate candidates" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("A protected preference is decision support, not approval."),
    );
    fireEvent.click(
      screen.getByLabelText("A tie or no supportable candidate is a valid governed outcome."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Adjudication creates no presentation, workflow, approval, or authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected preference established")).toBeVisible();
    const summary = screen.getByLabelText("Adjudication summary");
    expect(within(summary).getByText("3 eligible")).toBeVisible();
    expect(within(summary).getByText("1 preferred")).toBeVisible();
    expect(screen.getByText(/3 candidates were evaluated across 9/)).toBeVisible();
    expect(screen.queryByText("candidate.storage-controller-restart")).not.toBeInTheDocument();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-recommendation-adjudication-input.v1",
      completion_digest: completionResult.completion.canonical_digest,
      acknowledged_preference_is_not_approval: true,
      acknowledged_tie_or_no_support_is_valid: true,
      acknowledged_no_presentation_or_operational_authority: true,
    });
    for (const forbidden of [
      "candidate_id",
      "preferred_candidate_id",
      "category",
      "dimensions",
      "score",
      "ranking",
      "preference",
      "workflow",
      "command",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
