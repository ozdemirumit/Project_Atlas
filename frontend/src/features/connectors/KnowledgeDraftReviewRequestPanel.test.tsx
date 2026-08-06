import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalEvidenceKnowledgeDraft } from "../../api/evidenceDrafts";
import { KnowledgeDraftReviewRequestPanel } from "./KnowledgeDraftReviewRequestPanel";

const policyDigest = "370a20b5f82bfdc82efdf3ae1036663761094475b66cd562e0aa75bc112d0dd1";
const draft = {
  draft_id: "operational-evidence-knowledge-draft.test",
  schema_version: "atlas.operational-evidence-knowledge-draft.v1",
  version: 1,
  source_ingestion_id: "connector-invocation-evidence-ingestion.test",
  source_invocation_id: "connector-bounded-invocation.test",
  organization_id: "organization.development",
  environment_id: "environment.development",
  connector_id: "connector.test",
  instance_id: "connector-instance.test",
  capability_id: "capability.storage.health.read",
  knowledge_item_id: "knowledge-item.operational-evidence.test",
  draft_version_id: "knowledge-draft-version.test",
  title: "Test connector storage health operational evidence",
  draft_domain: "domain.operational",
  knowledge_lifecycle: "draft",
  classification: "classification.internal",
  access_policy_id: "connector-evidence-access.development-tenant",
  retention_policy_id: "connector-evidence-retention.development-30-days",
  encryption_profile_id: "connector-evidence-encryption.development",
  canonical_digest: "3".repeat(64),
  instance_state: "draft_operational_knowledge_created",
  knowledge_item_created: true,
  immutable_draft_confirmed: true,
  domain_review_completed: false,
  security_review_completed: false,
  knowledge_approved: false,
  retrieval_published: false,
} as unknown as OperationalEvidenceKnowledgeDraft;

const reviewRequest = {
  review_request_id: "operational-knowledge-review-request.test",
  schema_version: "atlas.operational-knowledge-review-request.v1",
  version: 1,
  source_draft_id: draft.draft_id,
  source_draft_digest: draft.canonical_digest,
  organization_id: draft.organization_id,
  environment_id: draft.environment_id,
  knowledge_item_id: draft.knowledge_item_id,
  draft_version_id: draft.draft_version_id,
  source_ingestion_id: draft.source_ingestion_id,
  source_invocation_id: draft.source_invocation_id,
  connector_id: draft.connector_id,
  instance_id: draft.instance_id,
  capability_id: draft.capability_id,
  title: draft.title,
  draft_domain: "domain.operational",
  content_type: "content-type.connector-observations",
  language: "language.en",
  knowledge_lifecycle: "review_requested",
  classification: draft.classification,
  access_policy_id: draft.access_policy_id,
  retention_policy_id: draft.retention_policy_id,
  encryption_profile_id: draft.encryption_profile_id,
  manifest_id: "operational-knowledge-review-manifest.test",
  orchestration_policy_id: "operational-knowledge-review-request-policy.development",
  orchestration_policy_digest: policyDigest,
  domain_track_code: "review-track.domain",
  security_track_code: "review-track.security",
  domain_queue_id: "review-queue.operational-domain",
  security_queue_id: "review-queue.knowledge-security",
  assignment_strategy: "assignment-strategy.policy-controlled",
  sla_class: "sla.knowledge-review-standard",
  domain_status: "awaiting_reviewer",
  security_status: "awaiting_reviewer",
  created_at: "2026-08-06T12:00:00+00:00",
  instance_state: "operational_knowledge_review_requested",
  canonical_digest: "4".repeat(64),
  review_requested: true,
  immutable_manifest_confirmed: true,
  encrypted_at_rest: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
  reviewer_assigned: false,
  content_inspection_opened: false,
  domain_review_completed: false,
  security_review_completed: false,
  correction_created: false,
  knowledge_approved: false,
  knowledge_published: false,
  chunks_created: false,
  embeddings_created: false,
  retrieval_published: false,
  model_context_available: false,
  graph_updated: false,
  scheduled: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("KnowledgeDraftReviewRequestPanel", () => {
  it("creates policy-routed review work without content, assignment, or decisions", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: reviewRequest }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <KnowledgeDraftReviewRequestPanel draft={draft} />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("textbox", { name: /reviewer|queue|draft content/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /approve|reject|publish|inspect/i })).toBeNull();
    fireEvent.click(screen.getByLabelText(/creates unassigned domain and security review/i));
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));

    expect(await screen.findByText("awaiting reviewers")).toBeVisible();
    expect(screen.getAllByText("awaiting reviewer")).toHaveLength(2);
    expect(screen.getByText("policy controlled")).toBeVisible();
    expect(screen.getByText("locked")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-knowledge-review-request-input.v1",
      source_draft_id: draft.draft_id,
      source_draft_digest: draft.canonical_digest,
      orchestration_policy_id: reviewRequest.orchestration_policy_id,
      orchestration_policy_digest: policyDigest,
      purpose: "Request independent domain and security review for this exact immutable draft.",
      acknowledged_result_is_only_an_unassigned_review_request: true,
    });
    for (const forbidden of [
      "draft_content",
      "evidence_content",
      "reviewer_id",
      "reviewer_group",
      "domain_queue_id",
      "security_queue_id",
      "review_decision",
      "approval",
      "publication",
      "retrieval_published",
      "model_context_available",
      "workflow_continued",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
