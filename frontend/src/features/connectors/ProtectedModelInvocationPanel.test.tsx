import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedModelContextResult } from "../../api/modelContextAssembly";
import { ProtectedModelInvocationPanel } from "./ProtectedModelInvocationPanel";

const contextResult = {
  context: {
    context_id: "protected-model-context.test",
    schema_version: "atlas.protected-model-context.v1",
    version: 1,
    environment_id: "environment.development",
    canonical_digest: "4".repeat(64),
    purpose: "Analyze approved evidence for a read-only controller warning investigation.",
    knowledge_retrieved: true,
    model_context_available: true,
    model_invoked: false,
  },
  manifest: {},
} as unknown as ProtectedModelContextResult;

const result = {
  invocation: {
    invocation_id: "protected-model-invocation.test",
    schema_version: "atlas.protected-model-invocation.v1",
    model_invoked: true,
    protected_draft_available: true,
    answer_generated: false,
    graph_updated: false,
    scheduled: false,
    workflow_continued: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  },
  manifest: {
    model_id: "atlas-local-synthetic",
    endpoint_profile_id: "endpoint.model.synthetic-local",
    citation_count: 1,
    unknown_count: 2,
    input_tokens: 215,
    output_tokens: 48,
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedModelInvocationPanel", () => {
  it("invokes only by policy and renders a minimized manifest", async () => {
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
        <ProtectedModelInvocationPanel contextResult={contextResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Invoke model" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Model output remains an untrusted protected draft."));
    fireEvent.click(
      screen.getByLabelText("Citations and unknowns require independent validation."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Invocation grants no answer, tool, workflow, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected model invocation completed")).toBeVisible();
    expect(screen.getByText(/Draft content remains protected/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-model-invocation-input.v1",
      context_digest: contextResult.context.canonical_digest,
      acknowledged_draft_is_untrusted: true,
      acknowledged_citations_and_unknowns_require_validation: true,
      acknowledged_no_answer_or_operational_authority: true,
    });
    for (const forbidden of ["model_id", "endpoint_url", "prompt", "evidence", "tool"]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });
});
