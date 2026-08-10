import { afterEach, describe, expect, it, vi } from "vitest";

import { createRecommendationCorrection } from "./recommendationCorrectionResubmissions";

const d = (value: string) => value.repeat(64).slice(0, 64);
const input = {
  sourceReviewRequestId: "recommendation-review-request.source-001",
  sourceReviewRequestDigest: d("a"),
  sourceRecommendationId: "recommendation.promoted.source-001",
  sourceRecommendationDigest: d("b"),
  sourceDecisions: [
    { decisionId: "decision.technical-001", canonicalDigest: d("c") },
    { decisionId: "decision.service-impact-001", canonicalDigest: d("d") },
  ] as [{ decisionId: string; canonicalDigest: string }, { decisionId: string; canonicalDigest: string }],
  correctionSubmissionId: "recommendation-correction-submission.source-001",
  correctionSubmissionDigest: d("e"),
  correctionPolicyId: "recommendation-correction-policy.development",
  correctionPolicyDigest: d("f"),
  purpose: "Create one corrected immutable recommendation version for fresh readiness review.",
};

function responseData() {
  return {
    correction_id: "recommendation-correction.result-001",
    schema_version: "atlas.recommendation-correction-resubmission.v1",
    version: 1,
    source_review_request_id: input.sourceReviewRequestId,
    source_review_request_digest: input.sourceReviewRequestDigest,
    source_recommendation_id: input.sourceRecommendationId,
    source_recommendation_digest: input.sourceRecommendationDigest,
    source_promotion_id: "recommendation-promotion.source-001",
    source_readiness_assessment_id: "recommendation-readiness.source-001",
    source_assignment_set_id: "recommendation-assignment.source-001",
    source_decision_ids: input.sourceDecisions.map((item) => item.decisionId),
    source_decision_digests: input.sourceDecisions.map((item) => item.canonicalDigest),
    decision_aggregate_digest: d("1"),
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    correction_submission_id: input.correctionSubmissionId,
    correction_submission_digest: input.correctionSubmissionDigest,
    correction_policy_id: input.correctionPolicyId,
    correction_policy_digest: input.correctionPolicyDigest,
    correction_policy_version: "policy-version.recommendation-correction-development-v1",
    adapter_id: "recommendation-correction-adapter.synthetic",
    attestation_digest: d("2"),
    new_recommendation_id: "recommendation.corrected-result-001",
    new_promotion_id: "recommendation-promotion.correction-result-001",
    new_artifact_digest: d("3"),
    source_binding_digest: d("4"),
    created_at: "2026-08-10T12:00:00Z",
    expires_at: "2026-08-10T12:10:00Z",
    state: "recommendation_correction_resubmitted",
    purpose: input.purpose,
    canonical_digest: d("5"),
    recommendation_promoted: true,
    correction_created: true,
    readiness_assessed: false,
    review_requested: false,
    reviewer_assigned: false,
    protected_inspection_opened: false,
    human_findings_recorded: false,
    technical_review_completed: false,
    service_impact_review_completed: false,
    final_disposition_recorded: false,
    recommendation_approved: false,
    workflow_created: false,
    itsm_record_created: false,
    execution_authorized: false,
    deployment_authorized: false,
    infrastructure_mutated: false,
    reused: false,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("recommendation correction client", () => {
  it("sends only opaque exact lineage and accepts reset lifecycle metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: responseData() }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "correction-ui-001" });

    const result = await createRecommendationCorrection(input);
    expect(result.data.new_recommendation_id).toBe("recommendation.corrected-result-001");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(typeof init.body).toBe("string");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body).toMatchObject({
      source_recommendation_id: input.sourceRecommendationId,
      correction_submission_id: input.correctionSubmissionId,
      acknowledged_fresh_readiness_required: true,
      acknowledged_no_review_approval_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("corrected_content");
    expect(body).not.toHaveProperty("findings");
    expect(body).not.toHaveProperty("options");
    expect(body).not.toHaveProperty("reviewer_id");
  });

  it("rejects content-bearing or authority-bearing responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ data: { ...responseData(), corrected_content: "unsafe" } }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("crypto", { randomUUID: () => "correction-ui-002" });
    await expect(createRecommendationCorrection(input)).rejects.toThrow("unsafe content");
  });
});
