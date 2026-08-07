import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import { ProtectedContentPanel } from "./ProtectedContentPanel";

const policyDigest = "c00b22d070bd43ce544ba714bd67beabfc4b6f1c6e9b582a1ded0c019e0023c4";
const lease = {
  lease_id: "operational-knowledge-protected-inspection-lease.test",
  canonical_digest: "e".repeat(64),
  source_assignment_set_id: "operational-knowledge-reviewer-assignment.test",
  source_draft_id: "operational-evidence-knowledge-draft.test",
  knowledge_item_id: "knowledge-item.operational-evidence.test",
  organization_id: "organization.local",
  environment_id: "environment.development",
  track_code: "review-track.domain",
  title: "Test connector storage health operational evidence",
  content_inspection_opened: true,
  content_disclosed: false,
  content_bytes_read: 0,
} as unknown as OperationalKnowledgeProtectedInspectionLease;

const content = "Read-only evidence\n<script>alert('unsafe')</script>";
const presentation = {
  presentation_id: "operational-knowledge-protected-content-presentation.test",
  schema_version: "atlas.operational-knowledge-protected-content-presentation.v1",
  version: 1,
  source_lease_id: lease.lease_id,
  source_lease_digest: lease.canonical_digest,
  source_assignment_set_id: lease.source_assignment_set_id,
  source_draft_id: lease.source_draft_id,
  knowledge_item_id: lease.knowledge_item_id,
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
  title: lease.title,
  content,
  content_bytes: new TextEncoder().encode(content).length,
  output_media_type: "media-type.text-plain",
  presented_content_digest: "a".repeat(64),
  presentation_policy_id: "operational-knowledge-protected-content-policy.development",
  presentation_policy_digest: policyDigest,
  instance_state: "operational_knowledge_protected_content_presented",
  content_inspection_opened: true,
  content_disclosed: true,
  exact_assignee_verified: true,
  browser_session_bound: true,
  source_integrity_verified: true,
  redaction_applied: true,
  active_content_rejected: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
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
};

afterEach(() => vi.unstubAllGlobals());

describe("ProtectedContentPanel", () => {
  it("presents exact-lease content as inert read-only text without review authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: presentation }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <ProtectedContentPanel lease={lease} />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole("button", { name: /approve|reject|publish|execute/i })).toBeNull();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Present protected content" }));

    expect(await screen.findByText("read-only")).toBeVisible();
    expect(container.querySelector("pre")?.textContent).toBe(content);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("not recorded")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-knowledge-protected-content-input.v1",
      source_lease_digest: lease.canonical_digest,
      presentation_policy_id: presentation.presentation_policy_id,
      presentation_policy_digest: policyDigest,
      purpose: "Inspect the exact assigned-track operational knowledge snapshot in a read-only boundary.",
      acknowledged_sensitive_read_only_content_grants_no_review_authority: true,
    });
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    for (const forbidden of [
      "lease_secret",
      "browser_session_id",
      "content_range",
      "review_decision",
      "approval",
      "publication",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
