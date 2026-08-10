import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationHumanReviewFinding } from "../../api/recommendationReviewFindings";
import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";
import { RecommendationFindingPresentationPanel } from "./RecommendationFindingPresentationPanel";

const policyDigest = "9fc389887f614977d27f12829da145fabd5d7412173994b0b807ed7fdeb0aabf";
const lease = {
  lease_id: "recommendation-protected-inspection-lease.test",
  recommendation_id: "recommendation.test",
  organization_id: "organization.atlas-dev",
  environment_id: "environment.development",
  track_code: "review-track.technical",
} as unknown as RecommendationProtectedInspection;
const presentation = {
  presentation_id: "recommendation-protected-content-presentation.test",
  source_lease_id: lease.lease_id,
  recommendation_id: lease.recommendation_id,
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
} as unknown as RecommendationProtectedContent;
const finding = {
  finding_packet_id: "recommendation-human-review-finding.test",
  canonical_digest: "1".repeat(64),
  source_lease_id: lease.lease_id,
  source_presentation_id: presentation.presentation_id,
  recommendation_id: lease.recommendation_id,
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
  finding_count: 1,
  finding_content_digest: "2".repeat(64),
} as unknown as RecommendationHumanReviewFinding;

const responseRecord = {
  finding_presentation_id: "recommendation-finding-presentation.test",
  schema_version: "atlas.recommendation-finding-presentation.v1",
  version: 1,
  source_finding_packet_id: finding.finding_packet_id,
  source_finding_digest: finding.canonical_digest,
  source_lease_id: lease.lease_id,
  source_presentation_id: presentation.presentation_id,
  source_assignment_set_id: "recommendation-reviewer-assignment.test",
  recommendation_id: lease.recommendation_id,
  readiness_assessment_id: "recommendation-review-readiness.test",
  promotion_id: "recommendation-promotion.test",
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  review_request_id: "recommendation-review-request.test",
  classification: "classification.internal",
  source_outcome: "preferred",
  option_count: 2,
  preferred_count: 1,
  track_code: lease.track_code,
  findings: [
    {
      category_code: "finding-category.technical-accuracy",
      severity_code: "finding-severity.material",
      summary: "Controller evidence conflicts with the recommendation",
      detail: "The protected snapshot and current inventory show different controller counts.",
    },
  ],
  finding_count: 1,
  finding_bytes: 248,
  finding_content_digest: finding.finding_content_digest,
  finding_metadata_digest: "3".repeat(64),
  lineage_digest: "4".repeat(64),
  category_catalog_digest: "5".repeat(64),
  severity_catalog_digest: "6".repeat(64),
  presentation_policy_id: "recommendation-finding-presentation-policy.development",
  presentation_policy_digest: policyDigest,
  presentation_policy_version: "policy-v1",
  presenter_id: "recommendation-finding-presenter.synthetic",
  presented_at: "2026-08-10T00:00:00Z",
  expires_at: "2026-08-11T00:00:00Z",
  state: "recommendation_human_review_finding_presented",
  purpose: "Present sealed recommendation observations without recording a review decision.",
  canonical_digest: "7".repeat(64),
  human_findings_recorded: true,
  human_findings_presented: true,
  technical_finding_recorded: true,
  service_impact_finding_recorded: false,
  technical_findings_presented: true,
  service_impact_findings_presented: false,
  exact_assignee_verified: true,
  browser_session_bound: true,
  source_integrity_verified: true,
  encrypted_source_verified: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
  human_review_completed: false,
  correction_created: false,
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
      <RecommendationFindingPresentationPanel
        lease={lease}
        presentation={presentation}
        finding={finding}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecommendationFindingPresentationPanel", () => {
  it("presents exact sealed findings without sending plaintext or granting authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: responseRecord }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    const submit = screen.getByRole("button", { name: "Present sealed findings" });
    expect(submit).toBeDisabled();
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Sealed findings presented")).toBeVisible();
    expect(screen.getByText(responseRecord.findings[0]!.summary)).toBeVisible();
    expect(screen.getByText(responseRecord.findings[0]!.detail)).toBeVisible();
    expect(screen.getByText("read only")).toBeVisible();
    expect(screen.queryByRole("button", { name: /decide|approve|execute|dispatch/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/v1/recommendations/${lease.recommendation_id}/protected-inspections/leases/${lease.lease_id}/presentations/${presentation.presentation_id}/findings/${finding.finding_packet_id}/presentations`,
    );
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-finding-presentation-input.v1",
      source_finding_digest: finding.canonical_digest,
      presentation_policy_id: responseRecord.presentation_policy_id,
      presentation_policy_digest: policyDigest,
      acknowledged_findings_are_sensitive: true,
      acknowledged_finding_presentation_is_not_a_review_decision: true,
    });
    for (const forbidden of [
      "findings",
      "summary",
      "detail",
      "finding_artifact_id",
      "decision",
      "approval",
      "command",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(request?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("rejects a response carrying private artifact coordinates", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { ...responseRecord, finding_artifact_id: "private-artifact.test" },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Present sealed findings" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Finding presentation unavailable");
    expect(screen.queryByText("Sealed findings presented")).toBeNull();
  });
});
