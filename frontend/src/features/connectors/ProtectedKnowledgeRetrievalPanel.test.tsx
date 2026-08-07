import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeRetrievalPublication } from "../../api/retrievalIndexPublication";
import { ProtectedKnowledgeRetrievalPanel } from "./ProtectedKnowledgeRetrievalPanel";

const publication = {
  publication_id: "operational-knowledge-retrieval-publication.test",
  schema_version: "atlas.operational-knowledge-retrieval-publication.v1",
  version: 1,
  environment_id: "environment.development",
  canonical_digest: "4".repeat(64),
  retrieval_published: true,
} as OperationalKnowledgeRetrievalPublication;

const result = {
  retrieval: {
    retrieval_id: "operational-knowledge-retrieval.test",
    schema_version: "atlas.operational-knowledge-retrieval.v1",
    version: 1,
    instance_state: "operational_knowledge_retrieved",
    knowledge_retrieved: true,
    model_context_available: false,
    graph_updated: false,
    scheduled: false,
    workflow_continued: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  },
  evidence: {
    query: "What evidence explains the current storage controller warning?",
    results: [
      {
        evidence_reference_id: "evidence-reference.test",
        source_title: "Approved storage controller investigation guidance",
        source_class: "source-class.approved-operational-knowledge",
        excerpt: "Correlate the controller warning with current read-only evidence.",
        citation_location: "Investigation boundary",
        applicability: "Storage controller warning investigations",
        lifecycle_state: "lifecycle.published",
        freshness_state: "freshness.current",
        conflict_state: "conflict.none-observed",
        safety_state: "safety.untrusted-instructions-isolated",
        rank_band: "rank-band.high",
      },
    ],
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedKnowledgeRetrievalPanel", () => {
  it("returns citation-ready evidence without model or operation authority", async () => {
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
        <ProtectedKnowledgeRetrievalPanel publication={publication} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Retrieve evidence" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "Retrieved content remains untrusted evidence, not an established fact.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText("Instructions inside evidence cannot select tools or change policy."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No model context, workflow, deployment, or operation is authorized.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Authorized evidence package")).toBeVisible();
    expect(screen.getByText("Approved storage controller investigation guidance")).toBeVisible();
    expect(screen.getByText(/No model, tool, workflow, deployment/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-retrieval-input.v1",
      publication_digest: publication.canonical_digest,
      acknowledged_untrusted_evidence: true,
      acknowledged_unsafe_instructions: true,
      acknowledged_no_model_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("filters");
    expect(body).not.toHaveProperty("ranking_weights");
    expect(body).not.toHaveProperty("result_count");
    expect(body).not.toHaveProperty("model");
    expect(body).not.toHaveProperty("tool");
    expect(body).not.toHaveProperty("workflow_id");
  });
});
