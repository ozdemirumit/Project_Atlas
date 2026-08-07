import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgePublicationPreparation } from "../../api/publicationPreparations";
import { SourceMaterializationPanel } from "./SourceMaterializationPanel";

const preparation = {
  preparation_id: "operational-knowledge-publication-preparation.test",
  schema_version: "atlas.operational-knowledge-publication-preparation.v1",
  version: 1,
  resolution_id: "operational-knowledge-final-resolution.test",
  resolution_digest: "a".repeat(64),
  review_request_id: "operational-knowledge-review-request.test",
  review_request_digest: "b".repeat(64),
  source_draft_id: "operational-knowledge-draft.test",
  source_draft_digest: "c".repeat(64),
  knowledge_item_id: "knowledge-item.test",
  organization_id: "organization.development",
  environment_id: "environment.development",
  preparation_receipt_digest: "d".repeat(64),
  canonical_digest: "e".repeat(64),
  instance_state: "operational_knowledge_publication_prepared",
  knowledge_approved: true,
  publication_ready: true,
  publication_prepared: true,
  knowledge_published: false,
  chunks_created: false,
  embeddings_created: false,
  index_staged: false,
  index_validated: false,
  retrieval_published: false,
  model_context_available: false,
  graph_updated: false,
  scheduled: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} as OperationalKnowledgePublicationPreparation;

const materialization = {
  materialization_id: "operational-knowledge-source-materialization.test",
  schema_version: "atlas.operational-knowledge-source-materialization.v1",
  version: 1,
  protected_material_digest: "1".repeat(64),
  materialization_receipt_digest: "2".repeat(64),
  canonical_digest: "3".repeat(64),
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
};

afterEach(() => vi.unstubAllGlobals());

describe("SourceMaterializationPanel", () => {
  it("materializes inside the protected boundary without later authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: materialization }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <SourceMaterializationPanel preparation={preparation} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Materialize protected source" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("The exact approved source and governance bindings are immutable."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Protected content remains inside the trusted materialization boundary.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No chunking, indexing, retrieval, workflow, or operation is authorized.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected source materialized")).toBeVisible();
    expect(screen.getByText(/No content, coordinate, chunk, vector, or index/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-source-materialization-input.v1",
      publication_preparation_digest: preparation.canonical_digest,
      acknowledged_immutable_approved_source: true,
      acknowledged_protected_content_boundary: true,
      acknowledged_no_chunking_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("source_coordinate");
    expect(body).not.toHaveProperty("canonicalization_profile_id");
  });
});
