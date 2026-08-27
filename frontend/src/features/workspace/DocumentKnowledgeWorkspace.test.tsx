import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../../api/client";
import {
  createDocumentKnowledgeDraft,
  indexDocumentKnowledge,
  prepareDocumentKnowledgePublication,
  recordDocumentKnowledgeApproval,
  searchDocumentKnowledge,
  submitDocumentKnowledgeReview,
  type DocumentKnowledgeApproval,
  type DocumentKnowledgeDraft,
  type DocumentKnowledgePublicationPreparation,
  type DocumentKnowledgeReview,
} from "../../api/documentKnowledge";
import DocumentKnowledgeWorkspace from "./DocumentKnowledgeWorkspace";

vi.mock("../../api/documentKnowledge", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/documentKnowledge")>();
  return {
    ...original,
    createDocumentKnowledgeDraft: vi.fn(),
    submitDocumentKnowledgeReview: vi.fn(),
    recordDocumentKnowledgeApproval: vi.fn(),
    prepareDocumentKnowledgePublication: vi.fn(),
    indexDocumentKnowledge: vi.fn(),
    searchDocumentKnowledge: vi.fn(),
    fileToBase64: vi.fn().mockResolvedValue("ZmFrZS1jb250ZW50"),
    chunkingProfileDigest: vi.fn().mockResolvedValue("a".repeat(64)),
  };
});

const draft: DocumentKnowledgeDraft = {
  draft_id: "document-knowledge-draft.test",
  organization_id: "organization.test",
  environment_id: "environment.test",
  knowledge_item_id: "knowledge-item.test",
  title: "Storage capacity runbook",
  draft_domain: "domain.general-document",
  content_type: "application/pdf",
  classification: "classification.internal",
  access_policy_id: "access-policy.default-internal",
  retention_policy_id: "retention-policy.standard-12m",
  protected_material_digest: "b".repeat(64),
  byte_count: 4096,
  created_at: "2026-08-27T10:00:00Z",
  instance_state: "document_knowledge_draft_created",
  canonical_digest: "c".repeat(64),
};

const passedReview: DocumentKnowledgeReview = {
  review_id: "document-knowledge-review.test",
  draft_id: draft.draft_id,
  organization_id: "organization.test",
  environment_id: "environment.test",
  decision: "passed",
  findings: ["Content is accurate."],
  decided_at: "2026-08-27T10:05:00Z",
  instance_state: "document_knowledge_review_decided",
  canonical_digest: "d".repeat(64),
};

const grantedApproval: DocumentKnowledgeApproval = {
  approval_id: "document-knowledge-approval.test",
  review_id: passedReview.review_id,
  draft_id: draft.draft_id,
  organization_id: "organization.test",
  environment_id: "environment.test",
  decision: "approved",
  rationale: "The document is accurate, current, and safe to publish as knowledge.",
  decided_at: "2026-08-27T10:10:00Z",
  instance_state: "document_knowledge_final_approved",
  canonical_digest: "e".repeat(64),
};

const preparation: DocumentKnowledgePublicationPreparation = {
  preparation_id: "document-knowledge-preparation.test",
  approval_id: grantedApproval.approval_id,
  draft_id: draft.draft_id,
  knowledge_item_id: draft.knowledge_item_id,
  organization_id: "organization.test",
  environment_id: "environment.test",
  classification: draft.classification,
  protected_material_digest: draft.protected_material_digest,
  chunking_profile_digest: "f".repeat(64),
  prepared_at: "2026-08-27T10:15:00Z",
  instance_state: "document_knowledge_publication_prepared",
  canonical_digest: "g".repeat(64),
};

function renderWorkspace() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DocumentKnowledgeWorkspace />
    </QueryClientProvider>,
  );
}

async function fillUploadStage() {
  const file = new File(["fake-content"], "runbook.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Document file"), { target: { files: [file] } });
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "Storage capacity runbook" },
  });
  fireEvent.change(screen.getByLabelText(/Curation purpose/), {
    target: { value: "Explain how storage capacity is monitored for this environment." },
  });
  fireEvent.click(screen.getByRole("button", { name: /Curate draft/ }));
}

describe("DocumentKnowledgeWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("curates a draft and advances to the review stage", async () => {
    vi.mocked(createDocumentKnowledgeDraft).mockResolvedValue(draft);
    renderWorkspace();

    await fillUploadStage();

    expect(await screen.findByRole("heading", { name: /Review decision/ })).toBeVisible();
    expect(screen.getByText("Storage capacity runbook")).toBeVisible();
    expect(vi.mocked(createDocumentKnowledgeDraft)).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Storage capacity runbook" }),
    );
  });

  it("surfaces separation-of-duties guidance when the reviewer matches the curator", async () => {
    vi.mocked(createDocumentKnowledgeDraft).mockResolvedValue(draft);
    vi.mocked(submitDocumentKnowledgeReview).mockRejectedValue(
      new ApiRequestError(
        "A reviewer must be a different subject than the draft's curator. " +
          "(document_knowledge_separation_of_duties_required)",
        403,
      ),
    );
    renderWorkspace();
    await fillUploadStage();
    await screen.findByRole("heading", { name: /Review decision/ });

    fireEvent.click(screen.getByRole("button", { name: /Submit review/ }));

    expect(
      await screen.findByText(/cannot also review it/),
    ).toBeVisible();
  });

  it("advances review, approval, preparation, and indexing to a searchable success state", async () => {
    vi.mocked(createDocumentKnowledgeDraft).mockResolvedValue(draft);
    vi.mocked(submitDocumentKnowledgeReview).mockResolvedValue(passedReview);
    vi.mocked(recordDocumentKnowledgeApproval).mockResolvedValue(grantedApproval);
    vi.mocked(prepareDocumentKnowledgePublication).mockResolvedValue(preparation);
    vi.mocked(indexDocumentKnowledge).mockResolvedValue({
      preparation_id: preparation.preparation_id,
      chunk_count: 3,
    });
    renderWorkspace();
    await fillUploadStage();
    await screen.findByRole("heading", { name: /Review decision/ });

    fireEvent.click(screen.getByRole("button", { name: /Submit review/ }));
    await screen.findByRole("heading", { name: /Final approval/ });

    fireEvent.change(screen.getByLabelText(/Rationale/), {
      target: { value: "The document is accurate, current, and safe to publish as knowledge." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Record approval/ }));
    await screen.findByRole("heading", { name: /Publication preparation/ });

    fireEvent.click(screen.getByRole("button", { name: /Prepare publication/ }));
    await screen.findByRole("heading", { name: /Index for retrieval/ });

    fireEvent.click(screen.getByRole("button", { name: /Index document/ }));

    expect(await screen.findByText(/Indexed 3 chunks/)).toBeVisible();
    expect(vi.mocked(indexDocumentKnowledge)).toHaveBeenCalledWith({
      preparationId: preparation.preparation_id,
    });
  });

  it("searches indexed documents independently of the pipeline stage", async () => {
    vi.mocked(searchDocumentKnowledge).mockResolvedValue([
      {
        chunk_id: "document-knowledge-chunk.test",
        knowledge_item_id: "knowledge-item.test",
        content_digest: "h".repeat(64),
        score: 0.82,
        excerpt: "Pool utilization reached 91% in the observed window.",
      },
    ]);
    renderWorkspace();

    fireEvent.change(
      screen.getByPlaceholderText("Ask about anything indexed from an approved document"),
      { target: { value: "What was the pool utilization?" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByText("Pool utilization reached 91% in the observed window."),
    ).toBeVisible();
    expect(vi.mocked(searchDocumentKnowledge)).toHaveBeenCalledWith({
      query: "What was the pool utilization?",
      topK: 5,
    });
    await waitFor(() => expect(screen.getByText("82.0%")).toBeVisible());
  });
});
