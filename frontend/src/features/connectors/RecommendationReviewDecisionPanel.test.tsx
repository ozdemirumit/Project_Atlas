import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationFindingPresentation } from "../../api/recommendationFindingPresentations";
import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";
import type { RecommendationHumanReviewFinding } from "../../api/recommendationReviewFindings";
import { RecommendationReviewDecisionPanel } from "./RecommendationReviewDecisionPanel";

const policyDigest = "d3c8affc6491b472c26a156210f69209cd9c75d85ab08274925645ca525aa165";
const lease = {
  lease_id: "recommendation-protected-inspection-lease.test",
  recommendation_id: "recommendation.test",
  organization_id: "organization.atlas-dev",
  environment_id: "environment.development",
  track_code: "review-track.technical",
} as unknown as RecommendationProtectedInspection;
const contentPresentation = {
  presentation_id: "recommendation-protected-content-presentation.test",
  source_lease_id: lease.lease_id,
  recommendation_id: lease.recommendation_id,
  track_code: lease.track_code,
} as unknown as RecommendationProtectedContent;
const finding = {
  finding_packet_id: "recommendation-human-review-finding.test",
  source_presentation_id: contentPresentation.presentation_id,
  environment_id: lease.environment_id,
  recommendation_id: lease.recommendation_id,
  track_code: lease.track_code,
} as unknown as RecommendationHumanReviewFinding;
const findingPresentation = {
  finding_presentation_id: "recommendation-finding-presentation.test",
  canonical_digest: "a".repeat(64),
  source_finding_packet_id: finding.finding_packet_id,
  recommendation_id: lease.recommendation_id,
  track_code: lease.track_code,
} as unknown as RecommendationFindingPresentation;
const responseRecord = {
  decision_id: "recommendation-track-review-decision.test",
  schema_version: "atlas.recommendation-track-review-decision.v1",
  version: 1,
  source_finding_presentation_id: findingPresentation.finding_presentation_id,
  source_finding_presentation_digest: findingPresentation.canonical_digest,
  source_finding_packet_id: finding.finding_packet_id,
  source_lease_id: lease.lease_id,
  source_content_presentation_id: contentPresentation.presentation_id,
  source_assignment_set_id: "recommendation-reviewer-assignment.test",
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  review_request_id: "recommendation-review-request.test",
  source_review_request_digest: "d".repeat(64),
  recommendation_id: lease.recommendation_id,
  readiness_assessment_id: "recommendation-review-readiness.test",
  promotion_id: "recommendation-promotion.test",
  classification: "classification.internal",
  source_outcome: "preferred",
  option_count: 2,
  preferred_count: 1,
  track_code: lease.track_code,
  disposition_code: "review-disposition.passed",
  basis_codes: ["review-basis.recommendation-technical-correctness"],
  decision_policy_id: "recommendation-track-review-decision-policy.development",
  decision_policy_digest: policyDigest,
  decision_policy_version: "policy-v1",
  attestor_id: "recommendation-track-review-decision-attestor.synthetic",
  attestation_digest: "b".repeat(64),
  decided_at: "2026-08-10T00:00:00Z",
  expires_at: "2026-08-11T00:00:00Z",
  state: "recommendation_track_review_decided",
  purpose: "Record the accountable recommendation review decision for this exact finding packet.",
  canonical_digest: "c".repeat(64),
  technical_review_completed: true,
  service_impact_review_completed: false,
  technical_review_passed: true,
  service_impact_review_passed: false,
  correction_required: false,
  correction_created: false,
  all_tracks_decided: false,
  all_tracks_passed: false,
  any_correction_required: false,
  track_decisions: [
    {
      track_code: lease.track_code,
      decision_id: "recommendation-track-review-decision.test",
      canonical_digest: "c".repeat(64),
      disposition_code: "review-disposition.passed",
    },
  ],
  recommendation_approved: false,
  workflow_created: false,
  itsm_record_created: false,
  execution_authorized: false,
  deployment_authorized: false,
  infrastructure_mutated: false,
  reused: false,
};

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RecommendationReviewDecisionPanel
        lease={lease}
        contentPresentation={contentPresentation}
        finding={finding}
        findingPresentation={findingPresentation}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecommendationReviewDecisionPanel", () => {
  it("records an accountable recommendation track decision without downstream authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: responseRecord }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Passed" }));
    const submit = screen.getByRole("button", { name: "Record track decision" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "I reviewed the exact sealed findings shown for this recommendation track.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText("This is my accountable human recommendation track decision."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "This decision is not recommendation approval or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Track decision attested")).toBeVisible();
    expect(screen.getByText("not granted")).toBeVisible();
    expect(screen.getByText(/other accountable review track remains/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /approve|dispatch|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/v1/recommendations/${lease.recommendation_id}/protected-inspections/leases/${lease.lease_id}/presentations/${contentPresentation.presentation_id}/findings/${finding.finding_packet_id}/presentations/${findingPresentation.finding_presentation_id}/decisions`,
    );
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-track-review-decision-input.v1",
      source_finding_presentation_digest: findingPresentation.canonical_digest,
      decision_policy_id: responseRecord.decision_policy_id,
      decision_policy_digest: policyDigest,
      disposition_code: "review-disposition.passed",
      basis_codes: ["review-basis.recommendation-technical-correctness"],
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
      "workflow",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });

  it("rejects a decision response that grants recommendation approval", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({ data: { ...responseRecord, recommendation_approved: true } }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "Passed" }));
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Record track decision" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Review decision unavailable");
    expect(screen.queryByText("Track decision attested")).toBeNull();
  });
});
