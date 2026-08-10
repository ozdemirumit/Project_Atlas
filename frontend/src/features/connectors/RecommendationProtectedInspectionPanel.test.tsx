import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationReviewerAssignmentResult } from "../../api/recommendationReviewerAssignments";
import { RecommendationProtectedInspectionPanel } from "./RecommendationProtectedInspectionPanel";

const technical = [
  "review-track.technical",
  "review-queue.technical",
  "recommendation-review-assignment.technical",
  "c".repeat(64),
  "assigned",
] as const;
const serviceImpact = [
  "review-track.service-impact",
  "review-queue.service-impact",
  "recommendation-review-assignment.service-impact",
  "d".repeat(64),
  "assigned",
] as const;
const assignmentResult = {
  assignment: {
    assignment_set_id: "recommendation-reviewer-assignment.test",
    review_request_id: "recommendation-review-request.test",
    recommendation_id: "recommendation.promoted.test",
    schema_version: "atlas.recommendation-reviewer-assignment.v1",
    version: 1,
    readiness_assessment_id: "recommendation-readiness.test",
    promotion_id: "recommendation-promotion.test",
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    assignment_policy_id: "recommendation-reviewer-assignment-policy.development",
    assignment_policy_version: "policy-v1",
    assignment_adapter_id: "recommendation-reviewer-assignment-adapter.synthetic",
    source_outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    track_assignments: [technical, serviceImpact],
    manifest_digest: "a".repeat(64),
    state: "reviewers_assigned",
    assigned_at: "2026-08-10T10:00:00Z",
    expires_at: "2026-08-10T10:10:00Z",
    purpose: "Open the exact assigned recommendation track without returning protected content.",
    canonical_digest: "e".repeat(64),
    review_requested: true,
    reviewer_assigned: true,
    immutable_assignments_confirmed: true,
    encrypted_identity_references: true,
    transient_identity_buffers_erased: true,
    directory_channel_closed: true,
    content_inspection_opened: false,
    human_review_completed: false,
    recommendation_approved: false,
    workflow_created: false,
    itsm_record_created: false,
    execution_authorized: false,
    deployment_authorized: false,
    infrastructure_mutated: false,
    reused: false,
  },
  manifest: {
    assignment_set_id: "recommendation-reviewer-assignment.test",
    review_request_id: "recommendation-review-request.test",
    recommendation_id: "recommendation.promoted.test",
    track_assignments: [technical, serviceImpact],
    state: "reviewers_assigned",
    assigned_at: "2026-08-10T10:00:00Z",
    expires_at: "2026-08-10T10:10:00Z",
    reviewer_assigned: true,
  },
} as RecommendationReviewerAssignmentResult;

const lease = {
  lease_id: "recommendation-protected-inspection-lease.test",
  schema_version: "atlas.recommendation-protected-inspection-lease.v1",
  version: 1,
  source_assignment_set_id: assignmentResult.assignment.assignment_set_id,
  recommendation_id: assignmentResult.assignment.recommendation_id,
  review_request_id: assignmentResult.assignment.review_request_id,
  readiness_assessment_id: assignmentResult.assignment.readiness_assessment_id,
  promotion_id: assignmentResult.assignment.promotion_id,
  organization_id: "organization.development",
  environment_id: "environment.development",
  classification: "internal",
  source_outcome: "preferred",
  option_count: 2,
  preferred_count: 1,
  track_code: "review-track.technical",
  opaque_assignment_id: technical[2],
  lease_holder_subject_digest: technical[3],
  lease_digest: "1".repeat(64),
  assignment_binding_digest: "2".repeat(64),
  policy_binding_digest: "3".repeat(64),
  cleanup_digest: "4".repeat(64),
  inspection_policy_id: "recommendation-protected-inspection-policy.development",
  inspection_policy_digest: "6245171bd90d87d0faa11cd7972959bb32ca06201d23d882813aeb9e1dd28c9f",
  inspection_policy_version: "policy-v1",
  lease_broker_id: "recommendation-protected-inspection-broker.synthetic",
  issued_at: "2026-08-10T10:00:00Z",
  expires_at: "2026-08-10T10:10:00Z",
  state: "recommendation_protected_inspection_leased",
  purpose: assignmentResult.assignment.purpose,
  canonical_digest: "5".repeat(64),
  review_requested: true,
  reviewer_assigned: true,
  content_inspection_opened: true,
  content_disclosed: false,
  protected_content_bytes_returned: 0,
  exact_assignee_verified: true,
  browser_session_bound: true,
  non_transferable: true,
  refresh_disabled: true,
  plaintext_secret_buffer_erased: true,
  broker_channel_closed: true,
  human_review_completed: false,
  recommendation_approved: false,
  workflow_created: false,
  itsm_record_created: false,
  execution_authorized: false,
  deployment_authorized: false,
  infrastructure_mutated: false,
  reused: false,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecommendationProtectedInspectionPanel", () => {
  it("opens only the selected assigned track without sending content or authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: lease }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RecommendationProtectedInspectionPanel assignmentResult={assignmentResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Open assigned inspection lease" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Only the exact assigned reviewer may open the selected review track."));
    fireEvent.click(screen.getByLabelText("The short-lived lease returns no content or secret in JSON."));
    fireEvent.click(screen.getByLabelText("The lease records no finding, decision, approval, workflow, or operation."));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Protected review channel is active")).toBeVisible();
    const summary = screen.getByLabelText("Recommendation inspection summary");
    expect(summary).toHaveTextContent("Tracktechnical");
    expect(summary).toHaveTextContent("Content disclosednone");
    expect(summary).toHaveTextContent("Operational authoritynone");
    expect(screen.queryByRole("button", { name: /retrieve|finding|decide|approve|execute/i })).toBeNull();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_assignment_set_id: assignmentResult.assignment.assignment_set_id,
      track_code: "review-track.technical",
      opaque_assignment_id: technical[2],
      acknowledged_exact_assignee_and_track_required: true,
      acknowledged_lease_returns_no_content_or_secret_in_json: true,
      acknowledged_no_decision_approval_or_operational_authority: true,
    });
    for (const forbidden of ["reviewer_identity", "lease_ttl_minutes", "lease_secret", "content", "decision", "command"])
      expect(body).not.toHaveProperty(forbidden);
  });
});
