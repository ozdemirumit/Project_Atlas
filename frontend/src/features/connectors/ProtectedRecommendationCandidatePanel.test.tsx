import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedAnswerPresentationResult } from "../../api/protectedAnswerPresentation";
import { ProtectedRecommendationCandidatePanel } from "./ProtectedRecommendationCandidatePanel";

const presentationResult = {
  presentation: {
    presentation_id: "protected-answer-presentation.test",
    schema_version: "atlas.protected-answer-presentation.v1",
    environment_id: "environment.development",
    canonical_digest: "6".repeat(64),
    purpose: "Analyze approved evidence for a read-only controller warning investigation.",
    answer_presented: true,
    recommendation_generated: false,
  },
} as unknown as ProtectedAnswerPresentationResult;

const candidateResult = {
  candidate_set: {
    candidate_set_id: "protected-recommendation-candidates.test",
    schema_version: "atlas.protected-recommendation-candidate-set.v1",
    recommendation_candidates_generated: true,
    service_impact_analyzed: false,
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
    candidate_count: 3,
    step_count: 4,
    maximum_capability_class: "C1",
    candidate_categories: [
      "recommendation-category.investigate",
      "recommendation-category.escalate",
      "recommendation-category.defer-no-action",
    ],
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedRecommendationCandidatePanel", () => {
  it("generates only a private bounded candidate manifest", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: candidateResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedRecommendationCandidatePanel presentationResult={presentationResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Generate candidates" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("Candidates are incomplete inputs, not final recommendations."),
    );
    fireEvent.click(
      screen.getByLabelText("Service impact, risk, duration, and recovery remain unverified."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Generation grants no recommendation, workflow, tool, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Grounded candidate set generated")).toBeVisible();
    const categories = screen.getByLabelText("Candidate categories");
    expect(within(categories).getByText("Investigate")).toBeVisible();
    expect(within(categories).getByText("Escalate")).toBeVisible();
    expect(within(categories).getByText("Defer or take no action")).toBeVisible();
    expect(screen.queryByText("Restart controller")).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-recommendation-candidate-input.v1",
      presentation_digest: presentationResult.presentation.canonical_digest,
      acknowledged_candidates_are_incomplete: true,
      acknowledged_impact_and_recovery_are_unverified: true,
      acknowledged_no_recommendation_or_operational_authority: true,
    });
    for (const forbidden of ["candidates", "steps", "command", "tool_call", "impact", "recovery"])
      expect(body).not.toHaveProperty(forbidden);
  });
});
