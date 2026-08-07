import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import type { OperationalKnowledgeReviewFinding } from "../../api/reviewFindings";
import { FindingPresentationPanel } from "./FindingPresentationPanel";

const policyDigest = "84b3f45594737cfb3218e4f51bb3e873174cdc2c34d84ce070073113d44fd168";
const lease = {
  lease_id: "operational-knowledge-protected-inspection-lease.test",
  environment_id: "environment.development",
  track_code: "review-track.domain",
} as unknown as OperationalKnowledgeProtectedInspectionLease;
const contentPresentation = {
  presentation_id: "operational-knowledge-protected-content-presentation.test",
  source_lease_id: lease.lease_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
} as unknown as OperationalKnowledgeProtectedContent;
const finding = {
  finding_packet_id: "operational-knowledge-review-finding.test",
  canonical_digest: "a".repeat(64),
  source_lease_id: lease.lease_id,
  source_presentation_id: contentPresentation.presentation_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
  finding_count: 1,
  finding_content_digest: "b".repeat(64),
} as unknown as OperationalKnowledgeReviewFinding;
const presentedFinding = {
  category_code: "finding-category.accuracy",
  severity_code: "finding-severity.material",
  summary: "The controller count conflicts with inventory evidence.",
  detail: "The protected snapshot reports one controller while inventory reports two.",
};
const responseRecord = {
  finding_presentation_id: "operational-knowledge-finding-presentation.test",
  schema_version: "atlas.operational-knowledge-finding-presentation.v1",
  version: 1,
  source_finding_packet_id: finding.finding_packet_id,
  source_finding_digest: finding.canonical_digest,
  source_lease_id: lease.lease_id,
  source_content_presentation_id: contentPresentation.presentation_id,
  track_code: finding.track_code,
  findings: [presentedFinding],
  finding_count: 1,
  finding_bytes: 246,
  finding_content_digest: finding.finding_content_digest,
  canonical_digest: "c".repeat(64),
  presentation_policy_id: "operational-knowledge-finding-presentation-policy.development",
  presentation_policy_digest: policyDigest,
  instance_state: "operational_knowledge_review_finding_presented",
  finding_recorded: true,
  finding_presented: true,
  domain_finding_recorded: true,
  security_finding_recorded: false,
  exact_assignee_verified: true,
  browser_session_bound: true,
  source_integrity_verified: true,
  encrypted_source_verified: true,
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

describe("FindingPresentationPanel", () => {
  it("presents exact sealed findings as inert text without decision authority", async () => {
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
        <FindingPresentationPanel
          lease={lease}
          contentPresentation={contentPresentation}
          finding={finding}
        />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Present sealed findings" });
    expect(submit).toBeDisabled();
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Exact finding packet presented")).toBeVisible();
    expect(screen.getByText(presentedFinding.summary)).toBeVisible();
    expect(screen.getByText(presentedFinding.detail)).toBeVisible();
    expect(screen.getByText("not recorded")).toBeVisible();
    expect(screen.queryByRole("button", { name: /approve|reject|publish|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-finding-presentation-input.v1",
      source_finding_digest: finding.canonical_digest,
      presentation_policy_id: responseRecord.presentation_policy_id,
      presentation_policy_digest: policyDigest,
      acknowledged_findings_are_sensitive: true,
      acknowledged_finding_presentation_is_not_a_review_decision: true,
    });
    expect(new Headers(request?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    for (const forbidden of [
      "findings",
      "finding_artifact_id",
      "review_decision",
      "approval",
      "publication",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
