import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeEmbeddingSet } from "../../api/embeddingGeneration";
import { IndexStagingValidationPanel } from "./IndexStagingValidationPanel";

const embeddingSet = {
  embedding_set_id: "operational-knowledge-embedding-set.test",
  schema_version: "atlas.operational-knowledge-embedding-set.v1",
  version: 1,
  environment_id: "environment.development",
  canonical_digest: "4".repeat(64),
  embeddings_created: true,
  index_staged: false,
} as OperationalKnowledgeEmbeddingSet;

const indexStage = {
  index_staging_id: "operational-knowledge-index-staging.test",
  schema_version: "atlas.operational-knowledge-index-staging.v1",
  version: 1,
  projection_manifest_digest: "5".repeat(64),
  reconciliation_digest: "6".repeat(64),
  embedding_count: 3,
  staged_point_count: 3,
  instance_state: "operational_knowledge_index_validated",
  knowledge_approved: true,
  publication_ready: true,
  publication_prepared: true,
  source_materialized: true,
  chunks_created: true,
  embeddings_created: true,
  index_staged: true,
  index_validated: true,
  knowledge_published: false,
  retrieval_published: false,
  model_context_available: false,
  graph_updated: false,
  scheduled: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("IndexStagingValidationPanel", () => {
  it("creates only a minimized inactive index-staging receipt", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: indexStage }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <IndexStagingValidationPanel embeddingSet={embeddingSet} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Stage and validate index" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "Protected vectors remain inside the trusted local index boundary.",
      ),
    );
    fireEvent.click(screen.getByLabelText("The validated projection remains sealed and inactive."));
    fireEvent.click(
      screen.getByLabelText("No publication, retrieval, workflow, or operation is authorized."),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Inactive retrieval projection validated")).toBeVisible();
    expect(screen.getByText(/3 protected points were reconciled and sealed/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-index-input.v1",
      embedding_set_digest: embeddingSet.canonical_digest,
      acknowledged_protected_vector_boundary: true,
      acknowledged_inactive_projection: true,
      acknowledged_no_publication_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("vector_values");
    expect(body).not.toHaveProperty("collection_name");
    expect(body).not.toHaveProperty("point_ids");
    expect(body).not.toHaveProperty("retrieval_enabled");
  });
});
