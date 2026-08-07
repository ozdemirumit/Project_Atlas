import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedDraftAdjudicationResult } from "../../api/protectedDraftAdjudication";
import { ProtectedAnswerPresentationPanel } from "./ProtectedAnswerPresentationPanel";

const adjudicationResult = {
  adjudication: {
    adjudication_id: "protected-draft-adjudication.test",
    schema_version: "atlas.protected-draft-adjudication.v1",
    environment_id: "environment.development",
    canonical_digest: "5".repeat(64),
    purpose: "Analyze approved evidence for a read-only controller warning investigation.",
    outcome: "adjudication-outcome.eligible",
    model_draft_adjudicated: true,
    answer_generated: false,
  },
  manifest: { outcome: "adjudication-outcome.eligible" },
} as unknown as ProtectedDraftAdjudicationResult;

const result = {
  presentation: {
    presentation_id: "protected-answer-presentation.test",
    schema_version: "atlas.protected-answer-presentation.v1",
    answer_presented: true,
    recommendation_generated: false,
    graph_updated: false,
    scheduled: false,
    workflow_continued: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  },
  manifest: {
    citation_count: 1,
    unknown_count: 1,
    byte_count: 128,
  },
  answer: {
    presentation_id: "protected-answer-presentation.test",
    summary: "Controller evidence indicates a bounded warning that requires human review.",
    citation_references: ["evidence-reference.controller-health"],
    unknowns: ["Failover timing remains unknown."],
    media_type: "text/plain",
    byte_count: 128,
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedAnswerPresentationPanel", () => {
  it("presents only an eligible answer and renders inert evidence", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: result }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedAnswerPresentationPanel adjudicationResult={adjudicationResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Present answer" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("The answer is bounded decision support, not established truth."),
    );
    fireEvent.click(
      screen.getByLabelText("Citation references and explicit unknowns remain material."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Presentation grants no recommendation, workflow, tool, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Adjudicated answer")).toBeVisible();
    expect(screen.getByText(result.answer.summary)).toBeVisible();
    expect(screen.getByText("evidence-reference.controller-health")).toBeVisible();
    expect(screen.getByText("Failover timing remains unknown.")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-answer-presentation-input.v1",
      adjudication_digest: adjudicationResult.adjudication.canonical_digest,
      acknowledged_bounded_decision_support: true,
      acknowledged_citations_and_unknowns_are_material: true,
      acknowledged_no_recommendation_or_operational_authority: true,
    });
    for (const forbidden of ["summary", "unknowns", "evidence", "model_id", "tool", "command"])
      expect(body).not.toHaveProperty(forbidden);
  });
});
