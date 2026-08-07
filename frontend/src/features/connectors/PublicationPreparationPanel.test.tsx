import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeFinalResolution } from "../../api/finalResolutions";
import { PublicationPreparationPanel } from "./PublicationPreparationPanel";

const resolution = {
  resolution_id: "operational-knowledge-final-resolution.test",
  schema_version: "atlas.operational-knowledge-final-resolution.v1",
  version: 1,
  review_request_id: "operational-knowledge-review-request.test",
  review_request_digest: "a".repeat(64),
  decision_ids: ["decision.domain.test", "decision.security.test"],
  decision_digests: ["b".repeat(64), "c".repeat(64)],
  organization_id: "organization.development",
  environment_id: "environment.development",
  knowledge_item_id: "knowledge-item.test",
  disposition_code: "final-resolution.approved",
  resolution_policy_id: "operational-knowledge-final-resolution-policy.development",
  resolution_policy_digest: "d".repeat(64),
  attestation_digest: "e".repeat(64),
  instance_state: "operational_knowledge_final_approved",
  canonical_digest: "f".repeat(64),
  domain_review_passed: true,
  security_review_passed: true,
  correction_required: false,
  correction_created: false,
  knowledge_approved: true,
  publication_ready: true,
  knowledge_published: false,
  retrieval_published: false,
  model_context_available: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} as OperationalKnowledgeFinalResolution;

const preparation = {
  preparation_id: "operational-knowledge-publication-preparation.test",
  schema_version: "atlas.operational-knowledge-publication-preparation.v1",
  version: 1,
  preparation_receipt_digest: "1".repeat(64),
  canonical_digest: "2".repeat(64),
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
};

afterEach(() => vi.unstubAllGlobals());

describe("PublicationPreparationPanel", () => {
  it("creates metadata-only preparation without processing authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: preparation }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PublicationPreparationPanel resolution={resolution} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Prepare publication metadata" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("The exact approved generation is immutable."));
    fireEvent.click(screen.getByLabelText("This step creates signed metadata only."));
    fireEvent.click(
      screen.getByLabelText(
        "No chunking, embedding, indexing, retrieval, workflow, or operation is authorized.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Publication metadata prepared")).toBeVisible();
    expect(screen.getByText(/No content was chunked, embedded, indexed, or published/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-publication-preparation-input.v1",
      final_resolution_digest: resolution.canonical_digest,
      acknowledged_immutable_approved_generation: true,
      acknowledged_metadata_only_preparation: true,
      acknowledged_no_processing_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("chunking_profile_id");
    expect(body).not.toHaveProperty("steward_id");
  });
});
