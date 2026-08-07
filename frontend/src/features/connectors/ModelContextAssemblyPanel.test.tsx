import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeRetrievalResult } from "../../api/protectedRetrieval";
import { ModelContextAssemblyPanel } from "./ModelContextAssemblyPanel";

const retrievalResult = {
  retrieval: {
    retrieval_id: "operational-knowledge-retrieval.test",
    schema_version: "atlas.operational-knowledge-retrieval.v1",
    version: 1,
    publication_id: "operational-knowledge-retrieval-publication.test",
    environment_id: "environment.development",
    canonical_digest: "4".repeat(64),
    purpose: "Retrieve approved evidence for a read-only controller warning investigation.",
    knowledge_retrieved: true,
    model_context_available: false,
  },
  evidence: { query: "Why is the controller warning active?", results: [] },
} as unknown as OperationalKnowledgeRetrievalResult;

const result = {
  context: {
    context_id: "protected-model-context.test",
    schema_version: "atlas.protected-model-context.v1",
    version: 1,
    knowledge_retrieved: true,
    model_context_available: true,
    model_invoked: false,
    answer_generated: false,
    graph_updated: false,
    scheduled: false,
    workflow_continued: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  },
  manifest: {
    context_id: "protected-model-context.test",
    included_evidence_count: 1,
    estimated_token_count: 215,
    maximum_estimated_tokens: 2000,
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ModelContextAssemblyPanel", () => {
  it("shows only a minimized context manifest without invoking a model", async () => {
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
        <ModelContextAssemblyPanel retrievalResult={retrievalResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Assemble context" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("User intent and retrieved text remain untrusted data."));
    fireEvent.click(
      screen.getByLabelText("Evidence units keep immutable citation and safety boundaries."),
    );
    fireEvent.click(
      screen.getByLabelText("Assembly does not invoke a model, tool, workflow, or operation."),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected model context assembled")).toBeVisible();
    expect(screen.getByText(/context body remains protected/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-model-context-input.v1",
      retrieval_digest: retrievalResult.retrieval.canonical_digest,
      acknowledged_untrusted_intent: true,
      acknowledged_citation_boundaries: true,
      acknowledged_no_model_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("model_id");
    expect(body).not.toHaveProperty("endpoint_url");
    expect(body).not.toHaveProperty("prompt");
    expect(body).not.toHaveProperty("evidence_selection");
    expect(body).not.toHaveProperty("tool");
  });
});
