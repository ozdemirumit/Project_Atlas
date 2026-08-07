import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeIndexStage } from "../../api/indexStagingValidation";
import { RetrievalIndexPublicationPanel } from "./RetrievalIndexPublicationPanel";

const indexStage = {
  index_staging_id: "operational-knowledge-index-staging.test",
  schema_version: "atlas.operational-knowledge-index-staging.v1",
  version: 1,
  environment_id: "environment.development",
  canonical_digest: "4".repeat(64),
  index_validated: true,
  retrieval_published: false,
} as OperationalKnowledgeIndexStage;

const publication = {
  publication_id: "operational-knowledge-retrieval-publication.test",
  schema_version: "atlas.operational-knowledge-retrieval-publication.v1",
  version: 1,
  route_generation_digest: "5".repeat(64),
  route_verification_digest: "6".repeat(64),
  instance_state: "operational_knowledge_retrieval_published",
  knowledge_approved: true,
  publication_ready: true,
  publication_prepared: true,
  source_materialized: true,
  chunks_created: true,
  embeddings_created: true,
  index_staged: true,
  index_validated: true,
  knowledge_published: true,
  retrieval_published: true,
  model_context_available: false,
  graph_updated: false,
  scheduled: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("RetrievalIndexPublicationPanel", () => {
  it("creates only a minimized atomic retrieval-publication receipt", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: publication }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RetrievalIndexPublicationPanel indexStage={indexStage} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Publish retrieval index" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("Publication creates only policy-filtered retrieval visibility."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No vector-store route, alias, point, payload, filter, or vector is exposed.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No model context, workflow, deployment, or operation is authorized.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected retrieval index published")).toBeVisible();
    expect(screen.getByText(/Atomic policy-filtered visibility is active/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-retrieval-publication-input.v1",
      index_staging_digest: indexStage.canonical_digest,
      acknowledged_policy_filtered_visibility: true,
      acknowledged_no_vector_store_disclosure: true,
      acknowledged_no_context_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("vector_values");
    expect(body).not.toHaveProperty("collection_name");
    expect(body).not.toHaveProperty("alias_name");
    expect(body).not.toHaveProperty("filters");
    expect(body).not.toHaveProperty("query");
    expect(body).not.toHaveProperty("model_context_enabled");
  });
});
