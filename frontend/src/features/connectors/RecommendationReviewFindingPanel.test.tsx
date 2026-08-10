import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";
import { RecommendationReviewFindingPanel } from "./RecommendationReviewFindingPanel";

const policyDigest = "39c89750405471d28f1161dc85f0d8b12685d43aaf06e61fd2ccaebb63e3875a";
const lease = {
  lease_id: "recommendation-protected-inspection-lease.test",
  source_assignment_set_id: "recommendation-reviewer-assignment.test",
  recommendation_id: "recommendation.test",
  review_request_id: "recommendation-review-request.test",
  readiness_assessment_id: "recommendation-review-readiness.test",
  promotion_id: "recommendation-promotion.test",
  organization_id: "organization.atlas-dev",
  environment_id: "environment.development",
  track_code: "review-track.technical",
} as unknown as RecommendationProtectedInspection;
const presentation = {
  presentation_id: "recommendation-protected-content-presentation.test",
  canonical_digest: "a".repeat(64),
  source_lease_id: lease.lease_id,
  source_assignment_set_id: lease.source_assignment_set_id,
  recommendation_id: lease.recommendation_id,
  review_request_id: lease.review_request_id,
  readiness_assessment_id: lease.readiness_assessment_id,
  promotion_id: lease.promotion_id,
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  track_code: lease.track_code,
} as unknown as RecommendationProtectedContent;

const responseRecord = {
  finding_packet_id: "recommendation-human-review-finding.test",
  schema_version: "atlas.recommendation-human-review-finding.v1",
  version: 1,
  source_lease_id: lease.lease_id,
  source_presentation_id: presentation.presentation_id,
  source_presentation_digest: presentation.canonical_digest,
  source_assignment_set_id: lease.source_assignment_set_id,
  recommendation_id: lease.recommendation_id,
  readiness_assessment_id: lease.readiness_assessment_id,
  promotion_id: lease.promotion_id,
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  review_request_id: lease.review_request_id,
  classification: "classification.internal",
  source_outcome: "preferred",
  option_count: 2,
  preferred_count: 1,
  track_code: presentation.track_code,
  finding_count: 1,
  finding_bytes: 248,
  finding_content_digest: "b".repeat(64),
  finding_metadata_digest: "c".repeat(64),
  lineage_digest: "d".repeat(64),
  category_catalog_digest: "e".repeat(64),
  severity_catalog_digest: "f".repeat(64),
  finding_policy_id: "recommendation-human-review-finding-policy.development",
  finding_policy_digest: policyDigest,
  finding_policy_version: "policy-v1",
  recorder_id: "recommendation-human-review-finding-recorder.synthetic",
  created_at: "2026-08-10T00:00:00Z",
  expires_at: "2026-08-11T00:00:00Z",
  state: "recommendation_human_review_finding_recorded",
  purpose: "Record bounded recommendation observations without creating a review decision.",
  canonical_digest: "1".repeat(64),
  human_findings_recorded: true,
  technical_finding_recorded: true,
  service_impact_finding_recorded: false,
  exact_assignee_verified: true,
  browser_session_bound: true,
  source_integrity_verified: true,
  immutable_finding_confirmed: true,
  encrypted_at_rest: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
  human_review_completed: false,
  recommendation_approved: false,
  correction_created: false,
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
      <RecommendationReviewFindingPanel lease={lease} presentation={presentation} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecommendationReviewFindingPanel", () => {
  it("seals exact-track findings and exposes only minimized metadata", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: responseRecord }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    expect(screen.getByRole("option", { name: "Technical accuracy" })).toBeVisible();
    expect(screen.queryByRole("option", { name: "Business impact" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Summary"), {
      target: { value: "Controller evidence conflicts with the recommendation." },
    });
    fireEvent.change(screen.getByLabelText("Evidence and detail"), {
      target: { value: "The protected snapshot and current inventory show different controller counts." },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Record recommendation findings" }));

    expect(await screen.findByText("Recommendation finding packet sealed")).toBeVisible();
    expect(screen.getByText("not recorded")).toBeVisible();
    expect(screen.queryByText("Controller evidence conflicts with the recommendation.")).toBeNull();
    expect(screen.queryByRole("button", { name: /decide|approve|execute|dispatch/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/v1/recommendations/${lease.recommendation_id}/protected-inspections/leases/${lease.lease_id}/presentations/${presentation.presentation_id}/findings`,
    );
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-human-review-finding-input.v1",
      source_presentation_digest: presentation.canonical_digest,
      finding_policy_id: responseRecord.finding_policy_id,
      finding_policy_digest: policyDigest,
      acknowledged_evidence_was_reviewed: true,
      acknowledged_finding_is_not_a_review_decision: true,
    });
    expect(body.findings).toEqual([
      {
        category_code: "finding-category.technical-accuracy",
        severity_code: "finding-severity.observation",
        summary: "Controller evidence conflicts with the recommendation.",
        detail: "The protected snapshot and current inventory show different controller counts.",
      },
    ]);
    expect(new Headers(request?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    for (const forbidden of ["identity", "review_decision", "approval", "command"])
      expect(body).not.toHaveProperty(forbidden);
  });

  it("rejects a response that leaks finding plaintext", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { ...responseRecord, findings: [{ summary: "leaked", detail: "leaked" }] },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    fireEvent.change(screen.getByLabelText("Summary"), {
      target: { value: "Controller evidence conflicts with the recommendation." },
    });
    fireEvent.change(screen.getByLabelText("Evidence and detail"), {
      target: { value: "The protected snapshot and inventory show different controller counts." },
    });
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Record recommendation findings" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Recommendation findings unavailable",
    );
    expect(screen.queryByText("Recommendation finding packet sealed")).toBeNull();
  });
});
