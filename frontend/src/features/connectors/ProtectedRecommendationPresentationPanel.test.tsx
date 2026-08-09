import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProtectedRecommendationAdjudicationResult } from "../../api/protectedRecommendationAdjudications";
import type { ProtectedRecommendationPresentationResult } from "../../api/protectedRecommendationPresentations";
import { ProtectedRecommendationPresentationPanel } from "./ProtectedRecommendationPresentationPanel";
import { RecommendationPromotionPanel } from "./RecommendationPromotionPanel";

const adjudicationResult = {
  adjudication: {
    adjudication_id: "protected-recommendation-adjudication.test",
    schema_version: "atlas.protected-recommendation-adjudication.v1",
    environment_id: "environment.development",
    canonical_digest: "a".repeat(64),
    purpose: "Present the exact protected recommendation as inert decision support.",
    recommendation_complete: true,
    recommendation_presented: false,
  },
  manifest: { preferred_count: 1 },
} as unknown as ProtectedRecommendationAdjudicationResult;

const presentationResult = {
  presentation: {
    presentation_id: "protected-recommendation-presentation.test",
    schema_version: "atlas.protected-recommendation-presentation.v1",
    adjudication_id: "protected-recommendation-adjudication.test",
    organization_id: "organization.development",
    environment_id: "environment.development",
    purpose: "Present the exact protected recommendation as inert decision support.",
    canonical_digest: "d".repeat(64),
    recommendation_presented: true,
    recommendation_ready_for_review: false,
    recommendation_approved: false,
    workflow_created: false,
    execution_authorized: false,
    deployment_authorized: false,
    infrastructure_mutated: false,
    media_type: "text/plain",
  },
  manifest: {
    outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    evidence_reference_count: 4,
    unknown_count: 2,
    byte_count: 1200,
    media_type: "text/plain",
    recommendation_digest: "b".repeat(64),
    presented_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    safety_notice: "Decision support only.",
  },
  recommendation: {
    presentation_id: "protected-recommendation-presentation.test",
    outcome: "preferred",
    headline: "A preferred decision-support option is available.",
    safety_notice: "Decision support only. No operational authority is granted.",
    options: [
      {
        role: "preferred",
        category: "recommendation-category.investigate",
        title: "Repeat the bounded health observation",
        intended_outcome: "Confirm whether the observed condition remains present.",
        rationale: "The signed deterministic policy established this preference.",
        confidence: "confidence.moderate",
        confidence_rationale: "Recent evidence is applicable.",
        steps: [
          {
            order: 1,
            phase: "observe",
            conceptual_action: "Repeat the approved read-only health observation.",
            capability_class: "C1",
          },
        ],
        overall_risk: "moderate",
        work_minimum_minutes: 5,
        work_maximum_minutes: 15,
        interruption_expected_mode: "interruption-mode.none-expected",
        interruption_minimum_minutes: 0,
        interruption_maximum_minutes: 0,
        recovery_feasibility: "feasible",
        recovery_minimum_minutes: 0,
        recovery_maximum_minutes: 5,
        technical_service_count: 2,
        business_service_count: 1,
        evidence_references: ["evidence-ref.health", "evidence-ref.topology"],
        assumptions: ["Observation access remains available."],
        unknowns: ["The condition may have changed."],
        evidence_gaps: ["Confirm the latest controller state."],
        applicability_limits: ["Read-only observation only."],
        support_reasons: [],
      },
      {
        role: "alternative",
        category: "recommendation-category.escalate",
        title: "Escalate for specialist review",
        intended_outcome: "Obtain independent validation.",
        rationale: "The option remains eligible but is not preferred.",
        confidence: "confidence.low",
        confidence_rationale: "Evidence remains incomplete.",
        steps: [
          {
            order: 1,
            phase: "escalate",
            conceptual_action: "Prepare the bounded evidence package for specialist review.",
            capability_class: "C0",
          },
        ],
        overall_risk: "low",
        work_minimum_minutes: 10,
        work_maximum_minutes: 20,
        interruption_expected_mode: "interruption-mode.none-expected",
        interruption_minimum_minutes: 0,
        interruption_maximum_minutes: 0,
        recovery_feasibility: "not_required",
        recovery_minimum_minutes: 0,
        recovery_maximum_minutes: 0,
        technical_service_count: 2,
        business_service_count: 1,
        evidence_references: ["evidence-ref.health", "evidence-ref.topology"],
        assumptions: ["A specialist is available."],
        unknowns: ["Review timing is unknown."],
        evidence_gaps: ["Confirm specialist ownership."],
        applicability_limits: ["No operational action."],
        support_reasons: [],
      },
    ],
    evidence_needs: ["Confirm the latest controller state."],
    media_type: "text/plain",
    byte_count: 1200,
    presented_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    canonical_digest: "b".repeat(64),
  },
} as unknown as ProtectedRecommendationPresentationResult;

const promotionResult = {
  recommendation: {
    promotion_id: "recommendation-promotion.test",
    recommendation_id: "recommendation.promoted.test",
    schema_version: "atlas.promoted-recommendation-artifact.v1",
    version: 1,
    presentation_id: presentationResult.presentation.presentation_id,
    adjudication_id: presentationResult.presentation.adjudication_id,
    organization_id: presentationResult.presentation.organization_id,
    environment_id: presentationResult.presentation.environment_id,
    classification: "internal",
    promotion_policy_id: "recommendation-promotion-policy.development",
    promotion_policy_version: "policy-version.recommendation-promotion-development-v1",
    promoter_id: "recommendation-promoter.synthetic",
    outcome: "preferred",
    headline: presentationResult.recommendation.headline,
    safety_notice: "Decision support draft only. No review or operational authority.",
    options: presentationResult.recommendation.options,
    evidence_needs: [],
    state: "draft",
    promoted_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    purpose: presentationResult.presentation.purpose,
    byte_count: presentationResult.recommendation.byte_count,
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
    presentation_id: presentationResult.presentation.presentation_id,
    adjudication_id: presentationResult.presentation.adjudication_id,
    outcome: "preferred",
    option_count: 2,
    preferred_count: 1,
    state: "draft",
    promoted_at: "2026-08-09T10:00:00Z",
    expires_at: "2026-08-09T10:10:00Z",
    safety_notice: "Decision support draft only. No review or operational authority.",
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ProtectedRecommendationPresentationPanel", () => {
  it("submits acknowledgements and renders safe recommendation details", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: presentationResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProtectedRecommendationPresentationPanel adjudicationResult={adjudicationResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Present recommendation" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText("The presentation is decision support only, not approval."),
    );
    fireEvent.click(
      screen.getByLabelText("A tie or no supportable option will remain unresolved."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No review, workflow, execution, or infrastructure authority is granted.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(
      await screen.findByText("A preferred decision-support option is available."),
    ).toBeVisible();
    expect(screen.getByText("Repeat the bounded health observation")).toBeVisible();
    expect(screen.getByText("Escalate for specialist review")).toBeVisible();
    const summary = screen.getByLabelText("Presentation summary");
    expect(within(summary).getByText("2 options")).toBeVisible();
    expect(screen.queryByRole("button", { name: /execute|approve/i })).not.toBeInTheDocument();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.protected-recommendation-presentation-input.v1",
      adjudication_digest: adjudicationResult.adjudication.canonical_digest,
      acknowledged_decision_support_only: true,
      acknowledged_tie_or_no_support_is_valid: true,
      acknowledged_no_operational_authority: true,
    });
    for (const forbidden of ["candidate_id", "capability_id", "command", "endpoint", "preferred"])
      expect(body).not.toHaveProperty(forbidden);
  });

  it("promotes only an acknowledged presentation into a non-authoritative draft", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: promotionResult }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RecommendationPromotionPanel presentationResult={presentationResult} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Promote to draft" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Promotion creates an immutable draft only."));
    fireEvent.click(
      screen.getByLabelText("The draft is not ready for review and is not approved."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "No workflow, ITSM, execution, deployment, or mutation authority is created.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByTestId("recommendation-promotion-result")).toBeVisible();
    expect(screen.getByText("draft")).toBeVisible();
    expect(screen.queryByRole("button", { name: /execute|approve|review/i })).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.recommendation-promotion-input.v1",
      presentation_digest: presentationResult.presentation.canonical_digest,
      acknowledged_draft_only: true,
      acknowledged_no_review_or_approval: true,
      acknowledged_no_operational_authority: true,
    });
    for (const forbidden of ["outcome", "candidate_id", "command", "approve", "workflow"])
      expect(body).not.toHaveProperty(forbidden);
  });
});
