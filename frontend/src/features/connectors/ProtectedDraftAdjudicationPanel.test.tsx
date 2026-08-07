import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedModelInvocationResult } from "../../api/protectedModelInvocation";
import { ProtectedDraftAdjudicationPanel } from "./ProtectedDraftAdjudicationPanel";

const invocationResult = {
  invocation: {
    invocation_id: "protected-model-invocation.test",
    schema_version: "atlas.protected-model-invocation.v1",
    environment_id: "environment.development",
    canonical_digest: "4".repeat(64),
    purpose: "Analyze approved evidence for a read-only controller warning investigation.",
    model_invoked: true,
    protected_draft_available: true,
    answer_generated: false,
  },
  manifest: {},
} as unknown as ProtectedModelInvocationResult;

const result = {
  adjudication: {
    adjudication_id: "protected-draft-adjudication.test",
    schema_version: "atlas.protected-draft-adjudication.v1",
    model_draft_adjudicated: true,
    answer_generated: false,
    graph_updated: false,
    scheduled: false,
    workflow_continued: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  },
  manifest: {
    outcome: "adjudication-outcome.eligible",
    check_count: 6,
    citation_count: 1,
    unknown_count: 2,
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedDraftAdjudicationPanel", () => {
  it("adjudicates only by policy and renders a minimized manifest", async () => {
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
        <ProtectedDraftAdjudicationPanel invocationResult={invocationResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Adjudicate draft" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Model output remains untrusted protected content."));
    fireEvent.click(
      screen.getByLabelText("Adjudication does not display or publish draft content."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Eligibility grants no answer, workflow, tool, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(
      await screen.findByText("Draft eligible for later presentation review"),
    ).toBeVisible();
    expect(screen.getByText(/Draft content remains protected/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-draft-adjudication-input.v1",
      invocation_digest: invocationResult.invocation.canonical_digest,
      acknowledged_draft_is_untrusted: true,
      acknowledged_no_content_presentation: true,
      acknowledged_no_answer_or_operational_authority: true,
    });
    for (const forbidden of [
      "draft",
      "summary",
      "evidence",
      "model_id",
      "prompt",
      "tool",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });
});
