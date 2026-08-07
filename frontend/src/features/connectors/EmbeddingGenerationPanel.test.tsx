import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeChunkSet } from "../../api/deterministicChunking";
import { EmbeddingGenerationPanel } from "./EmbeddingGenerationPanel";

const chunkSet = {
  chunk_set_id: "operational-knowledge-chunk-set.test",
  schema_version: "atlas.operational-knowledge-chunk-set.v1",
  version: 1,
  environment_id: "environment.development",
  canonical_digest: "4".repeat(64),
  chunks_created: true,
  embeddings_created: false,
} as OperationalKnowledgeChunkSet;

const embeddingSet = {
  embedding_set_id: "operational-knowledge-embedding-set.test",
  schema_version: "atlas.operational-knowledge-embedding-set.v1",
  version: 1,
  vector_manifest_digest: "5".repeat(64),
  coverage_validation_digest: "6".repeat(64),
  embedding_count: 3,
  vector_dimension: 384,
  instance_state: "operational_knowledge_embeddings_created",
  knowledge_approved: true,
  publication_ready: true,
  publication_prepared: true,
  source_materialized: true,
  chunks_created: true,
  embeddings_created: true,
  index_staged: false,
  index_validated: false,
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

describe("EmbeddingGenerationPanel", () => {
  it("creates only a minimized protected embedding-set receipt", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: embeddingSet }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <EmbeddingGenerationPanel chunkSet={chunkSet} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Generate protected embeddings" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "Protected chunks remain inside the trusted local embedding boundary.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText("The approved model and tokenizer profile is immutable."),
    );
    fireEvent.click(
      screen.getByLabelText("No indexing, retrieval, workflow, or operation is authorized."),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected embedding set created")).toBeVisible();
    expect(screen.getByText(/3 embeddings use a verified 384-dimension/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-embedding-input.v1",
      chunk_set_digest: chunkSet.canonical_digest,
      acknowledged_protected_chunk_boundary: true,
      acknowledged_immutable_model_profile: true,
      acknowledged_no_index_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("chunk_ids");
    expect(body).not.toHaveProperty("vector_values");
    expect(body).not.toHaveProperty("model_endpoint");
    expect(body).not.toHaveProperty("index_id");
  });
});
