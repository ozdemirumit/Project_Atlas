import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import { ReviewFindingPanel } from "./ReviewFindingPanel";

const policyDigest = "a75b0d4793e099271c6ae1ccdb56bc279babe4489855488c9bc93dcf80947552";
const lease = {
  lease_id: "operational-knowledge-protected-inspection-lease.test",
  source_assignment_set_id: "operational-knowledge-reviewer-assignment.test",
  source_draft_id: "operational-evidence-knowledge-draft.test",
  knowledge_item_id: "knowledge-item.operational-evidence.test",
  environment_id: "environment.development",
  track_code: "review-track.domain",
} as unknown as OperationalKnowledgeProtectedInspectionLease;
const presentation = {
  presentation_id: "operational-knowledge-protected-content-presentation.test",
  canonical_digest: "a".repeat(64),
  source_lease_id: lease.lease_id,
  source_assignment_set_id: lease.source_assignment_set_id,
  source_draft_id: lease.source_draft_id,
  knowledge_item_id: lease.knowledge_item_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
} as unknown as OperationalKnowledgeProtectedContent;

const responseRecord = {
  finding_packet_id: "operational-knowledge-review-finding.test",
  schema_version: "atlas.operational-knowledge-review-finding.v1",
  version: 1,
  source_lease_id: lease.lease_id,
  source_presentation_id: presentation.presentation_id,
  source_presentation_digest: presentation.canonical_digest,
  track_code: presentation.track_code,
  finding_count: 1,
  finding_bytes: 248,
  finding_content_digest: "b".repeat(64),
  canonical_digest: "c".repeat(64),
  finding_policy_id: "operational-knowledge-review-finding-policy.development",
  finding_policy_digest: policyDigest,
  instance_state: "operational_knowledge_review_finding_recorded",
  finding_recorded: true,
  domain_finding_recorded: true,
  security_finding_recorded: false,
  exact_assignee_verified: true,
  browser_session_bound: true,
  source_integrity_verified: true,
  immutable_finding_confirmed: true,
  encrypted_at_rest: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
  domain_review_completed: false,
  security_review_completed: false,
  correction_created: false,
  knowledge_approved: false,
  knowledge_published: false,
  retrieval_published: false,
  model_context_available: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("ReviewFindingPanel", () => {
  it("records track-specific findings and renders only the minimized sealed receipt", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: responseRecord }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ReviewFindingPanel lease={lease} presentation={presentation} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("option", { name: "Accuracy" })).toBeVisible();
    expect(screen.queryByRole("option", { name: "Malware" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Summary"), {
      target: { value: "The controller count conflicts with inventory evidence." },
    });
    fireEvent.change(screen.getByLabelText("Evidence and detail"), {
      target: { value: "The protected snapshot reports one controller; inventory reports two." },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Record findings" }));

    expect(await screen.findByText("Finding packet sealed")).toBeVisible();
    expect(screen.getByText("not recorded")).toBeVisible();
    expect(screen.queryByText("The controller count conflicts with inventory evidence.")).toBeNull();
    expect(screen.queryByRole("button", { name: /approve|reject|publish|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-review-finding-input.v1",
      source_presentation_digest: presentation.canonical_digest,
      finding_policy_id: responseRecord.finding_policy_id,
      finding_policy_digest: policyDigest,
      acknowledged_evidence_was_reviewed: true,
      acknowledged_finding_is_not_a_review_decision: true,
    });
    expect(body.findings).toEqual([
      {
        category_code: "finding-category.accuracy",
        severity_code: "finding-severity.observation",
        summary: "The controller count conflicts with inventory evidence.",
        detail: "The protected snapshot reports one controller; inventory reports two.",
      },
    ]);
    expect(new Headers(request?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    for (const forbidden of ["review_decision", "approval", "publication", "execution_authorized"])
      expect(body).not.toHaveProperty(forbidden);
  });
});
