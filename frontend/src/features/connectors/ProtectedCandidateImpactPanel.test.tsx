import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedRecommendationCandidateResult } from "../../api/protectedRecommendationCandidates";
import { ProtectedCandidateImpactPanel } from "./ProtectedCandidateImpactPanel";

const candidateResult = {
  candidate_set: {
    candidate_set_id: "protected-recommendation-candidates.test",
    schema_version: "atlas.protected-recommendation-candidate-set.v1",
    environment_id: "environment.development",
    candidate_content_digest: "a".repeat(64),
    purpose: "Analyze approved evidence for a read-only controller warning investigation.",
    recommendation_candidates_generated: true,
    service_impact_analyzed: false,
  },
  manifest: { candidate_count: 3 },
} as unknown as ProtectedRecommendationCandidateResult;

const impactResult = {
  impact_analysis: {
    impact_analysis_id: "protected-candidate-impact.test",
    schema_version: "atlas.protected-candidate-impact-analysis.v1",
    service_impact_analyzed: true,
    impact_complete: false,
    outage_confirmed: false,
    interruption_established: false,
    duration_established: false,
    risk_completed: false,
    recovery_completed: false,
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
    path_count: 5,
    modeled_entity_count: 6,
    technical_service_count: 1,
    business_service_count: 1,
    gap_count: 3,
    graph_freshness: "aging",
    graph_completeness: "partial",
    safety_notice:
      "Dependencies show modeled reachability only; no outage or operational authority is established.",
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedCandidateImpactPanel", () => {
  it("returns only a minimized graph-impact manifest", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: impactResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedCandidateImpactPanel candidateResult={candidateResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Analyze reachability" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("Graph reachability is dependency evidence, not proof of an outage."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Impact, interruption, duration, risk, and recovery remain provisional.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Enrichment grants no recommendation, workflow, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Service reachability analyzed")).toBeVisible();
    const status = screen.getByLabelText("Graph analysis status");
    expect(within(status).getByText("aging")).toBeVisible();
    expect(within(status).getByText("partial")).toBeVisible();
    expect(within(status).getByText("3 graph gaps")).toBeVisible();
    expect(screen.queryByText("ERP-PROD-VOL-01")).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-candidate-impact-input.v1",
      candidate_set_digest: candidateResult.candidate_set.candidate_content_digest,
      acknowledged_reachability_is_not_outage_evidence: true,
      acknowledged_impact_remains_provisional: true,
      acknowledged_no_recommendation_or_operational_authority: true,
    });
    for (const forbidden of [
      "candidate_content",
      "target",
      "graph_snapshot",
      "max_depth",
      "paths",
      "impact",
      "risk",
      "recovery",
      "command",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
