import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeTrackReviewDecision } from "../../api/reviewDecisions";
import { FinalResolutionPanel } from "./FinalResolutionPanel";

const decision = {
  review_request_id: "operational-knowledge-review-request.test",
  source_review_request_digest: "a".repeat(64),
  environment_id: "environment.development",
  all_tracks_decided: true,
  all_tracks_passed: true,
  any_correction_required: false,
  track_decisions: [
    {
      track_code: "review-track.domain",
      decision_id: "decision.domain.test",
      canonical_digest: "b".repeat(64),
      disposition_code: "review-disposition.passed",
    },
    {
      track_code: "review-track.security",
      decision_id: "decision.security.test",
      canonical_digest: "c".repeat(64),
      disposition_code: "review-disposition.passed",
    },
  ],
} as unknown as OperationalKnowledgeTrackReviewDecision;

const resolution = {
  resolution_id: "operational-knowledge-final-resolution.test",
  schema_version: "atlas.operational-knowledge-final-resolution.v1",
  version: 1,
  review_request_id: decision.review_request_id,
  review_request_digest: decision.source_review_request_digest,
  decision_ids: ["decision.domain.test", "decision.security.test"],
  decision_digests: ["b".repeat(64), "c".repeat(64)],
  organization_id: "organization.development",
  environment_id: decision.environment_id,
  knowledge_item_id: "knowledge-item.test",
  disposition_code: "final-resolution.approved",
  resolution_policy_id: "operational-knowledge-final-resolution-policy.development",
  resolution_policy_digest: "47a0ab94067d3767933d9f6115c373dfdbfe98049d854d58688724c5135e7590",
  attestation_digest: "d".repeat(64),
  instance_state: "operational_knowledge_final_approved",
  canonical_digest: "e".repeat(64),
  domain_review_passed: true,
  security_review_passed: true,
  correction_required: false,
  correction_created: false,
  knowledge_approved: true,
  publication_ready: true,
  knowledge_published: false,
  retrieval_published: false,
  model_context_available: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("FinalResolutionPanel", () => {
  it("records publication readiness without publishing or operational authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: resolution }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <FinalResolutionPanel decision={decision} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Record final resolution" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("The exact passed review generation is immutable."));
    fireEvent.click(screen.getByLabelText("Approval establishes publication readiness only."));
    fireEvent.click(
      screen.getByLabelText(
        "No publication, retrieval, workflow, or operational authority is granted.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Knowledge approved")).toBeVisible();
    expect(screen.getByText(/Nothing was published or indexed/)).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-final-resolution-input.v1",
      disposition_code: "final-resolution.approved",
      acknowledged_immutable_review_generation: true,
      acknowledged_publication_readiness_only: true,
      acknowledged_no_operational_authority: true,
    });
    expect(body).not.toHaveProperty("content");
    expect(body).not.toHaveProperty("publication_state");
    expect(body).not.toHaveProperty("approver_id");
  });
});
