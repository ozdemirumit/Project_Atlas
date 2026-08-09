import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationReviewRequestResult } from "../../api/recommendationReviewRequests";
import { RecommendationReviewerAssignmentPanel } from "./RecommendationReviewerAssignmentPanel";

const reviewRequestResult = {
  request: {
    review_request_id: "recommendation-review-request.test",
    recommendation_id: "recommendation.promoted.test",
    schema_version: "atlas.recommendation-review-request.v1",
    version: 1,
    readiness_assessment_id: "recommendation-readiness.test",
    promotion_id: "recommendation-promotion.test",
    presentation_id: "recommendation-presentation.test",
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    review_request_policy_id: "recommendation-review-request-policy.development",
    review_request_policy_version: "policy-version.review-request-development-v1",
    orchestrator_id: "recommendation-review-request-orchestrator.synthetic",
    source_outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    track_codes: ["review-track.technical", "review-track.service-impact"],
    queue_ids: ["review-queue.technical", "review-queue.service-impact"],
    track_statuses: [
      ["review-track.technical", "awaiting_reviewer"],
      ["review-track.service-impact", "awaiting_reviewer"],
    ],
    routing_profile: "routing-profile.recommendation-review",
    sla_class: "standard",
    manifest_digest: "a".repeat(64),
    state: "review_requested",
    requested_at: "2026-08-10T10:00:00Z",
    expires_at: "2026-08-10T10:10:00Z",
    purpose: "Assign accountable reviewers to the exact recommendation review request.",
    canonical_digest: "b".repeat(64),
    review_requested: true,
    reviewer_assigned: false,
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
  manifest: {},
} as unknown as RecommendationReviewRequestResult;

const assignmentResult = {
  assignment: {
    assignment_set_id: "recommendation-reviewer-assignment.test",
    review_request_id: reviewRequestResult.request.review_request_id,
    recommendation_id: reviewRequestResult.request.recommendation_id,
    schema_version: "atlas.recommendation-reviewer-assignment.v1",
    version: 1,
    readiness_assessment_id: reviewRequestResult.request.readiness_assessment_id,
    promotion_id: reviewRequestResult.request.promotion_id,
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    assignment_policy_id: "recommendation-reviewer-assignment-policy.development",
    assignment_policy_version: "policy-version.assignment-development-v1",
    assignment_adapter_id: "recommendation-reviewer-assignment-adapter.synthetic",
    source_outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    track_assignments: [
      [
        "review-track.technical",
        "review-queue.technical",
        "recommendation-review-assignment.technical",
        "c".repeat(64),
        "assigned",
      ],
      [
        "review-track.service-impact",
        "review-queue.service-impact",
        "recommendation-review-assignment.service-impact",
        "d".repeat(64),
        "assigned",
      ],
    ],
    manifest_digest: "a".repeat(64),
    state: "reviewers_assigned",
    assigned_at: "2026-08-10T10:00:00Z",
    expires_at: "2026-08-10T10:10:00Z",
    purpose: reviewRequestResult.request.purpose,
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
    review_request_id: reviewRequestResult.request.review_request_id,
    recommendation_id: reviewRequestResult.request.recommendation_id,
    track_assignments: [
      [
        "review-track.technical",
        "review-queue.technical",
        "recommendation-review-assignment.technical",
        "c".repeat(64),
        "assigned",
      ],
      [
        "review-track.service-impact",
        "review-queue.service-impact",
        "recommendation-review-assignment.service-impact",
        "d".repeat(64),
        "assigned",
      ],
    ],
    state: "reviewers_assigned",
    assigned_at: "2026-08-10T10:00:00Z",
    expires_at: "2026-08-10T10:10:00Z",
    reviewer_assigned: true,
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecommendationReviewerAssignmentPanel", () => {
  it("assigns two policy-owned reviewers without opening review or operational authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: assignmentResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RecommendationReviewerAssignmentPanel reviewRequestResult={reviewRequestResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Assign accountable reviewers" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "Reviewer identities, tracks, queues, and directory queries are policy-owned.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Technical and service-impact review require two distinct eligible humans.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText(
        "Assignment opens no content and grants no decision, approval, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Independent review tracks are ready")).toBeVisible();
    const summary = screen.getByLabelText("Reviewer assignment summary");
    expect(within(summary).getByText("technical")).toBeVisible();
    expect(within(summary).getByText("service impact")).toBeVisible();
    expect(within(summary).getAllByText("assigned")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /inspect|review|approve|execute/i })).toBeNull();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-reviewer-assignment-input.v1",
      review_request_id: reviewRequestResult.request.review_request_id,
      review_request_digest: reviewRequestResult.request.canonical_digest,
      acknowledged_caller_cannot_select_reviewers: true,
      acknowledged_distinct_reviewers_required: true,
      acknowledged_no_inspection_decision_or_operational_authority: true,
    });
    for (const forbidden of [
      "reviewer_id",
      "track_code",
      "queue_id",
      "directory_query",
      "decision",
      "command",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
