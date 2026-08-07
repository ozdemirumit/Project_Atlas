import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeFindingPresentation } from "../../api/findingPresentations";
import type { OperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import type { OperationalKnowledgeReviewFinding } from "../../api/reviewFindings";
import { ReviewDecisionPanel } from "./ReviewDecisionPanel";

const policyDigest = "881c16aedab87adda50e0abc0879a8f6a568f9e40e442673aad7f63dcc0c33ab";
const lease = {
  lease_id: "operational-knowledge-protected-inspection-lease.test",
  environment_id: "environment.development",
  track_code: "review-track.domain",
} as unknown as OperationalKnowledgeProtectedInspectionLease;
const contentPresentation = {
  presentation_id: "operational-knowledge-protected-content-presentation.test",
  source_lease_id: lease.lease_id,
  track_code: lease.track_code,
} as unknown as OperationalKnowledgeProtectedContent;
const finding = {
  finding_packet_id: "operational-knowledge-review-finding.test",
  source_presentation_id: contentPresentation.presentation_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
} as unknown as OperationalKnowledgeReviewFinding;
const findingPresentation = {
  finding_presentation_id: "operational-knowledge-finding-presentation.test",
  canonical_digest: "a".repeat(64),
  source_finding_packet_id: finding.finding_packet_id,
  track_code: lease.track_code,
} as unknown as OperationalKnowledgeFindingPresentation;
const responseRecord = {
  decision_id: "operational-knowledge-track-review-decision.test",
  schema_version: "atlas.operational-knowledge-track-review-decision.v1",
  version: 1,
  source_finding_presentation_id: findingPresentation.finding_presentation_id,
  source_finding_presentation_digest: findingPresentation.canonical_digest,
  source_finding_packet_id: finding.finding_packet_id,
  source_lease_id: lease.lease_id,
  source_content_presentation_id: contentPresentation.presentation_id,
  track_code: lease.track_code,
  disposition_code: "review-disposition.passed",
  basis_codes: ["review-basis.technical-accuracy"],
  decision_policy_id: "operational-knowledge-track-review-decision-policy.development",
  decision_policy_digest: policyDigest,
  attestation_digest: "b".repeat(64),
  canonical_digest: "c".repeat(64),
  instance_state: "operational_knowledge_track_review_decided",
  domain_review_completed: true,
  security_review_completed: false,
  domain_review_passed: true,
  security_review_passed: false,
  correction_required: false,
  correction_created: false,
  all_tracks_decided: false,
  all_tracks_passed: false,
  any_correction_required: false,
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

describe("ReviewDecisionPanel", () => {
  it("records one explicit track decision without approval or finding content", async () => {
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
        <ReviewDecisionPanel
          lease={lease}
          contentPresentation={contentPresentation}
          finding={finding}
          findingPresentation={findingPresentation}
        />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Passed" }));
    const submit = screen.getByRole("button", { name: "Record track decision" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("I reviewed the exact sealed findings shown for this track."),
    );
    fireEvent.click(screen.getByLabelText("This is my accountable human track decision."));
    fireEvent.click(
      screen.getByLabelText("This decision is not knowledge approval or operational authority."),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Track decision attested")).toBeVisible();
    expect(screen.getByText("not granted")).toBeVisible();
    expect(screen.queryByRole("button", { name: /approve|publish|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-track-review-decision-input.v1",
      source_finding_presentation_digest: findingPresentation.canonical_digest,
      decision_policy_id: responseRecord.decision_policy_id,
      decision_policy_digest: policyDigest,
      disposition_code: "review-disposition.passed",
      basis_codes: ["review-basis.technical-accuracy"],
      acknowledged_exact_findings_reviewed: true,
      acknowledged_human_track_decision: true,
      acknowledged_no_approval_or_operational_authority: true,
    });
    expect(new Headers(request?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    for (const forbidden of [
      "findings",
      "finding_summary",
      "finding_detail",
      "reviewer_identity",
      "approval",
      "publication",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
