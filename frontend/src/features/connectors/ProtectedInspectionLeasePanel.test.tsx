import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeReviewerAssignment } from "../../api/reviewerAssignments";
import { ProtectedInspectionLeasePanel } from "./ProtectedInspectionLeasePanel";

const policyDigest = "94ab5739197fe27b5714035c7fba489ccc618a7c7808c7866fdbc799a080a8ed";
const assignment = {
  assignment_set_id: "operational-knowledge-reviewer-assignment.test",
  canonical_digest: "8".repeat(64),
  source_review_request_id: "operational-knowledge-review-request.test",
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
  knowledge_lifecycle: "reviewer_assigned",
  review_requested: true,
  reviewer_assigned: true,
  content_inspection_opened: false,
  domain_review_completed: false,
  security_review_completed: false,
} as unknown as OperationalKnowledgeReviewerAssignment;

const lease = {
  lease_id: "operational-knowledge-protected-inspection-lease.test",
  schema_version: "atlas.operational-knowledge-protected-inspection-lease.v1",
  version: 1,
  source_assignment_set_id: assignment.assignment_set_id,
  source_assignment_set_digest: assignment.canonical_digest,
  organization_id: assignment.organization_id,
  environment_id: assignment.environment_id,
  review_request_id: assignment.source_review_request_id,
  source_draft_id: assignment.source_draft_id,
  source_draft_digest: assignment.source_draft_digest,
  knowledge_item_id: assignment.knowledge_item_id,
  draft_version_id: assignment.draft_version_id,
  source_ingestion_id: assignment.source_ingestion_id,
  source_invocation_id: assignment.source_invocation_id,
  connector_id: assignment.connector_id,
  instance_id: assignment.instance_id,
  capability_id: assignment.capability_id,
  title: assignment.title,
  classification: "classification.internal",
  access_policy_id: "access-policy.knowledge.internal",
  retention_policy_id: "retention-policy.knowledge.standard",
  encryption_profile_id: "encryption-profile.knowledge",
  manifest_id: assignment.manifest_id,
  manifest_digest: "5".repeat(64),
  track_code: "review-track.security",
  opaque_assignment_id: "knowledge-review-assignment.security.test",
  lease_holder_subject_digest: "7".repeat(64),
  lease_digest: "a".repeat(64),
  assignment_binding_digest: "b".repeat(64),
  policy_binding_digest: "c".repeat(64),
  cleanup_digest: "d".repeat(64),
  inspection_policy_id: "operational-knowledge-protected-inspection-policy.development",
  inspection_policy_digest: policyDigest,
  inspection_policy_version: "policy-v1",
  lease_broker_id: "operational-knowledge-protected-inspection-broker.synthetic",
  issued_at: "2026-08-06T12:00:00+00:00",
  expires_at: "2026-08-06T12:10:00+00:00",
  instance_state: "operational_knowledge_protected_inspection_leased",
  purpose: "Open one short-lived assigned-track inspection boundary without returning content.",
  canonical_digest: "e".repeat(64),
  review_requested: true,
  reviewer_assigned: true,
  content_inspection_opened: true,
  content_disclosed: false,
  content_bytes_read: 0,
  exact_assignee_verified: true,
  browser_session_bound: true,
  non_transferable: true,
  refresh_disabled: true,
  plaintext_secret_buffer_erased: true,
  broker_channel_closed: true,
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

describe("ProtectedInspectionLeasePanel", () => {
  it("opens only an assigned track lease without content or bearer material", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: lease }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedInspectionLeasePanel assignment={assignment} />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("textbox", { name: /reviewer|secret|duration|content range/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /approve|reject|publish/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Security" }));
    fireEvent.click(screen.getByLabelText(/opens a short-lived browser-bound channel/i));
    fireEvent.click(screen.getByRole("button", { name: "Open inspection lease" }));

    expect(await screen.findByText("lease active")).toBeVisible();
    expect(screen.getByText("security")).toBeVisible();
    expect(screen.getByText("verified")).toBeVisible();
    expect(screen.getByText("none")).toBeVisible();
    expect(screen.getByText("not recorded")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-knowledge-protected-inspection-input.v1",
      source_assignment_set_id: assignment.assignment_set_id,
      source_assignment_set_digest: assignment.canonical_digest,
      track_code: "review-track.security",
      inspection_policy_id: lease.inspection_policy_id,
      inspection_policy_digest: policyDigest,
      purpose: "Open one short-lived assigned-track inspection boundary without returning content.",
      acknowledged_lease_returns_no_content_and_records_no_decision: true,
    });
    for (const forbidden of [
      "reviewer_id",
      "lease_secret",
      "lease_secret_digest",
      "browser_session_id",
      "duration",
      "draft_content",
      "content_range",
      "review_decision",
      "approval",
      "publication",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
