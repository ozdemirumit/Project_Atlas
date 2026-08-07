import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeSourceMaterialization } from "../../api/sourceMaterializations";
import { DeterministicChunkingPanel } from "./DeterministicChunkingPanel";

const materialization = {
  materialization_id: "operational-knowledge-source-materialization.test",
  schema_version: "atlas.operational-knowledge-source-materialization.v1",
  version: 1,
  preparation_id: "operational-knowledge-publication-preparation.test",
  resolution_id: "operational-knowledge-final-resolution.test",
  source_draft_id: "operational-knowledge-draft.test",
  knowledge_item_id: "knowledge-item.test",
  organization_id: "organization.development",
  environment_id: "environment.development",
  classification: "classification.internal",
  protected_material_digest: "1".repeat(64),
  chunking_profile_digest: "2".repeat(64),
  materialization_receipt_digest: "3".repeat(64),
  canonical_digest: "4".repeat(64),
  instance_state: "operational_knowledge_source_materialized",
  knowledge_approved: true,
  publication_ready: true,
  publication_prepared: true,
  source_materialized: true,
  chunks_created: false,
  embeddings_created: false,
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
} as OperationalKnowledgeSourceMaterialization;

const chunkSet = {
  chunk_set_id: "operational-knowledge-chunk-set.test",
  schema_version: "atlas.operational-knowledge-chunk-set.v1",
  version: 1,
  ordered_chunk_manifest_digest: "5".repeat(64),
  determinism_evidence_digest: "6".repeat(64),
  chunk_count: 3,
  instance_state: "operational_knowledge_chunks_created",
  knowledge_approved: true,
  publication_ready: true,
  publication_prepared: true,
  source_materialized: true,
  chunks_created: true,
  embeddings_created: false,
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

describe("DeterministicChunkingPanel", () => {
  it("creates only a minimized deterministic chunk-set receipt", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: chunkSet }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <DeterministicChunkingPanel materialization={materialization} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Create protected chunk set" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("Protected content remains inside the trusted chunking boundary."),
    );
    fireEvent.click(
      screen.getByLabelText("The preparation-bound chunking profile is immutable."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No embedding, indexing, retrieval, workflow, or operation is authorized.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Deterministic chunk set created")).toBeVisible();
    expect(screen.getByText(/3 immutable chunks are bound/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-chunking-input.v1",
      source_materialization_digest: materialization.canonical_digest,
      acknowledged_protected_content_boundary: true,
      acknowledged_immutable_chunking_profile: true,
      acknowledged_no_embedding_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("chunk_size");
    expect(body).not.toHaveProperty("overlap");
    expect(body).not.toHaveProperty("section_path");
  });
});
