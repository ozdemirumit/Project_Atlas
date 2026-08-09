import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationPromotionResult } from "../../api/recommendationPromotions";
import { RecommendationReadinessPanel } from "./RecommendationReadinessPanel";

const promotionResult = {
  recommendation: {
    promotion_id: "recommendation-promotion.test",
    recommendation_id: "recommendation.promoted.test",
    schema_version: "atlas.promoted-recommendation-artifact.v1",
    version: 1,
    presentation_id: "protected-recommendation-presentation.test",
    adjudication_id: "protected-recommendation-adjudication.test",
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    promotion_policy_id: "recommendation-promotion-policy.development",
    promotion_policy_version: "policy-version.recommendation-promotion-development-v1",
    promoter_id: "recommendation-promoter.synthetic",
    outcome: "preferred",
    headline: "A preferred decision-support option is available.",
    safety_notice: "Decision support draft only. No review or operational authority.",
    options: [],
    evidence_needs: [],
    state: "draft",
    promoted_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    purpose: "Assess the exact promoted recommendation for human review readiness.",
    byte_count: 1200,
    canonical_digest: "c".repeat(64),
    recommendation_promoted: true,
    recommendation_ready_for_review: false,
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
    promotion_id: "recommendation-promotion.test",
    recommendation_id: "recommendation.promoted.test",
    presentation_id: "protected-recommendation-presentation.test",
    adjudication_id: "protected-recommendation-adjudication.test",
    outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    state: "draft",
    promoted_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    safety_notice: "Decision support draft only. No review or operational authority.",
  },
} as unknown as RecommendationPromotionResult;

const readinessResult = {
  assessment: {
    assessment_id: "recommendation-readiness.test",
    recommendation_id: "recommendation.promoted.test",
    schema_version: "atlas.recommendation-readiness-assessment.v1",
    version: 1,
    promotion_id: "recommendation-promotion.test",
    presentation_id: "protected-recommendation-presentation.test",
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    readiness_policy_id: "recommendation-readiness-policy.development",
    readiness_policy_version: "policy-version.recommendation-readiness-development-v1",
    evaluator_id: "recommendation-readiness-evaluator.synthetic",
    source_outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    evaluation_outcome: "ready",
    reason_codes: [],
    check_count: 7,
    passed_check_count: 7,
    state: "ready_for_review",
    assessed_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    purpose: promotionResult.recommendation.purpose,
    canonical_digest: "d".repeat(64),
    recommendation_ready_for_review: true,
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
    assessment_id: "recommendation-readiness.test",
    recommendation_id: "recommendation.promoted.test",
    promotion_id: "recommendation-promotion.test",
    source_outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    evaluation_outcome: "ready",
    reason_codes: [],
    check_count: 7,
    passed_check_count: 7,
    state: "ready_for_review",
    assessed_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    recommendation_ready_for_review: true,
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RecommendationReadinessPanel", () => {
  it("assesses readiness without creating review or operational authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: readinessResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RecommendationReadinessPanel promotionResult={promotionResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Assess readiness" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Readiness is not human review or approval."));
    fireEvent.click(
      screen.getByLabelText("A blocked assessment requires a new recommendation version."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No workflow, ITSM, execution, deployment, or mutation authority is created.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Ready for human review")).toBeVisible();
    const summary = screen.getByLabelText("Readiness summary");
    expect(within(summary).getByText("7/7 checks")).toBeVisible();
    expect(within(summary).getByText("no operational authority")).toBeVisible();
    expect(screen.queryByRole("button", { name: /execute|approve|create review/i })).toBeNull();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-readiness-input.v1",
      recommendation_digest: promotionResult.recommendation.canonical_digest,
      acknowledged_readiness_is_not_review: true,
      acknowledged_blocked_requires_new_version: true,
      acknowledged_no_operational_authority: true,
    });
    for (const forbidden of ["evaluation_outcome", "reviewer_id", "approve", "command"])
      expect(body).not.toHaveProperty(forbidden);
  });

  it("requests policy-routed human review without reviewer or action authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const reviewRequestResult = {
      request: {
        schema_version: "atlas.recommendation-review-request.v1",
        state: "review_requested",
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
      },
      manifest: {
        track_statuses: [
          ["review-track.technical", "awaiting_reviewer"],
          ["review-track.service-impact", "awaiting_reviewer"],
        ],
      },
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: readinessResult }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: reviewRequestResult }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RecommendationReadinessPanel promotionResult={promotionResult} />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByLabelText("Readiness is not human review or approval."));
    fireEvent.click(
      screen.getByLabelText("A blocked assessment requires a new recommendation version."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No workflow, ITSM, execution, deployment, or mutation authority is created.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Assess readiness" }));

    const requestReview = await screen.findByRole("button", { name: "Request human review" });
    expect(requestReview).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("Request creation is not reviewer assignment or human review."),
    );
    fireEvent.click(
      screen.getByLabelText("Review tracks and queues are selected only by signed policy."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No approval, workflow, ITSM, execution, deployment, or mutation authority is created.",
      ),
    );
    expect(requestReview).toBeEnabled();
    fireEvent.click(requestReview);

    expect(await screen.findByText("Awaiting accountable reviewers")).toBeVisible();
    const summary = screen.getByLabelText("Review request summary");
    expect(within(summary).getByText("technical: awaiting reviewer")).toBeVisible();
    expect(within(summary).getByText("service impact: awaiting reviewer")).toBeVisible();
    expect(within(summary).getByText("no reviewer assigned")).toBeVisible();
    expect(screen.queryByRole("button", { name: /assign|approve|execute/i })).toBeNull();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const request = fetchMock.mock.calls[1]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-review-request-input.v1",
      recommendation_digest: promotionResult.recommendation.canonical_digest,
      readiness_assessment_id: readinessResult.assessment.assessment_id,
      readiness_assessment_digest: readinessResult.assessment.canonical_digest,
      acknowledged_request_is_not_assignment_or_review: true,
      acknowledged_routing_is_policy_owned: true,
      acknowledged_no_approval_or_operational_authority: true,
    });
    for (const forbidden of ["track_codes", "queue_id", "reviewer_id", "decision", "command"])
      expect(body).not.toHaveProperty(forbidden);
  });
});
