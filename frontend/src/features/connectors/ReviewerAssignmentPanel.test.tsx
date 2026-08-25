import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  OperationalKnowledgeReviewerAssignmentSource,
} from "../../api/reviewerAssignments";
import { ReviewerAssignmentPanel } from "./ReviewerAssignmentPanel";

const policyDigest = "caa0be534d5b205f4f5184da47a75e961aa9871e986e7392aa75d9bfb289cc58";
const reviewRequest = {
  review_request_id: "operational-knowledge-review-request.test",
  schema_version: "atlas.operational-knowledge-review-request.v1",
  version: 1,
  source_draft_id: "operational-evidence-knowledge-draft.test",
  source_draft_digest: "3".repeat(64),
  organization_id: "organization.local",
  environment_id: "environment.development",
  knowledge_item_id: "knowledge-item.operational-evidence.test",
  draft_version_id: "knowledge-draft-version.test",
  source_ingestion_id: "connector-invocation-evidence-ingestion.test",
  source_invocation_id: "connector-bounded-invocation.test",
  connector_id: "connector.test",
  instance_id: "connector-instance.test",
  capability_id: "capability.storage.health.read",
  title: "Test connector storage health operational evidence",
  manifest_id: "operational-knowledge-review-manifest.test",
  knowledge_lifecycle: "review_requested",
  canonical_digest: "4".repeat(64),
  review_requested: true,
  reviewer_assigned: false,
  content_inspection_opened: false,
  domain_review_completed: false,
  security_review_completed: false,
} as OperationalKnowledgeReviewerAssignmentSource;

const assignment = {
  assignment_set_id: "operational-knowledge-reviewer-assignment.test",
  schema_version: "atlas.operational-knowledge-reviewer-assignment.v1",
  version: 1,
  source_review_request_id: reviewRequest.review_request_id,
  source_review_request_digest: reviewRequest.canonical_digest,
  source_draft_id: reviewRequest.source_draft_id,
  source_draft_digest: reviewRequest.source_draft_digest,
  organization_id: reviewRequest.organization_id,
  environment_id: reviewRequest.environment_id,
  knowledge_item_id: reviewRequest.knowledge_item_id,
  draft_version_id: reviewRequest.draft_version_id,
  source_ingestion_id: reviewRequest.source_ingestion_id,
  source_invocation_id: reviewRequest.source_invocation_id,
  connector_id: reviewRequest.connector_id,
  instance_id: reviewRequest.instance_id,
  capability_id: reviewRequest.capability_id,
  title: reviewRequest.title,
  knowledge_lifecycle: "reviewer_assigned",
  classification: "classification.internal",
  access_policy_id: "access-policy.knowledge.internal",
  retention_policy_id: "retention-policy.knowledge.standard",
  encryption_profile_id: "encryption-profile.knowledge",
  manifest_id: reviewRequest.manifest_id,
  manifest_digest: "5".repeat(64),
  domain_assignment_id: "knowledge-review-assignment.domain.test",
  security_assignment_id: "knowledge-review-assignment.security.test",
  domain_reviewer_subject_digest: "6".repeat(64),
  security_reviewer_subject_digest: "7".repeat(64),
  domain_track_code: "review-track.domain",
  security_track_code: "review-track.security",
  domain_queue_id: "review-queue.operational-domain",
  security_queue_id: "review-queue.knowledge-security",
  domain_status: "assigned",
  security_status: "assigned",
  assignment_policy_id: "operational-knowledge-reviewer-assignment-policy.development",
  assignment_policy_digest: policyDigest,
  created_at: "2026-08-06T12:00:00+00:00",
  expires_at: "2026-08-07T12:00:00+00:00",
  instance_state: "operational_knowledge_reviewers_assigned",
  canonical_digest: "8".repeat(64),
  review_requested: true,
  reviewer_assigned: true,
  immutable_assignments_confirmed: true,
  encrypted_identity_references: true,
  transient_identity_buffers_erased: true,
  directory_channel_closed: true,
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

describe("ReviewerAssignmentPanel", () => {
  it("assigns distinct reviewers without caller-selected identity or review authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: assignment }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ReviewerAssignmentPanel reviewRequest={reviewRequest} />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("textbox", { name: /reviewer|group|queue/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /approve|reject|publish|inspect/i })).toBeNull();
    fireEvent.click(screen.getByLabelText(/assigns distinct eligible reviewers/i));
    fireEvent.click(screen.getByRole("button", { name: "Assign reviewers" }));

    expect(await screen.findByText("reviewers assigned")).toBeVisible();
    expect(screen.getAllByText("assigned")).toHaveLength(2);
    expect(screen.getByText("protected")).toBeVisible();
    expect(screen.getByText("locked")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-knowledge-reviewer-assignment-input.v1",
      source_review_request_id: reviewRequest.review_request_id,
      source_review_request_digest: reviewRequest.canonical_digest,
      assignment_policy_id: assignment.assignment_policy_id,
      assignment_policy_digest: policyDigest,
      purpose: "Assign distinct eligible domain and security reviewers without exposing identity.",
      acknowledged_assignment_opens_no_content_and_records_no_decision: true,
    });
    for (const forbidden of [
      "domain_reviewer_id",
      "security_reviewer_id",
      "reviewer_group",
      "domain_queue_id",
      "security_queue_id",
      "review_decision",
      "approval",
      "publication",
      "content_inspection_opened",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
