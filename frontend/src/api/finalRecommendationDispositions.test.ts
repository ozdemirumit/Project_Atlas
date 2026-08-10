import { afterEach, describe, expect, it, vi } from "vitest";

import { createFinalRecommendationDisposition } from "./finalRecommendationDispositions";

const d = (value: string) => value.repeat(64).slice(0, 64);
const input = {
  reviewRequestId: "recommendation-review-request.source-001",
  reviewRequestDigest: d("a"),
  recommendationId: "recommendation.promoted.source-001",
  recommendationDigest: d("b"),
  decisions: [
    { decisionId: "decision.technical-001", canonicalDigest: d("c") },
    { decisionId: "decision.service-impact-001", canonicalDigest: d("d") },
  ] as [
    { decisionId: string; canonicalDigest: string },
    { decisionId: string; canonicalDigest: string },
  ],
  disposition: "recommendation-disposition.accepted" as const,
  basisCodes: [
    "recommendation-final-basis.review-evidence-sufficient",
    "recommendation-final-basis.service-impact-understood",
  ],
  dispositionPolicyId: "final-recommendation-disposition-policy.development",
  dispositionPolicyDigest: d("e"),
  purpose: "Record the accountable final recommendation disposition for this review generation.",
};

function responseData() {
  return {
    disposition_id: "final-recommendation-disposition.result-001",
    schema_version: "atlas.final-recommendation-disposition.v1",
    version: 1,
    review_request_id: input.reviewRequestId,
    review_request_digest: input.reviewRequestDigest,
    recommendation_id: input.recommendationId,
    recommendation_digest: input.recommendationDigest,
    promotion_id: "recommendation-promotion.source-001",
    readiness_assessment_id: "recommendation-readiness.source-001",
    assignment_set_id: "recommendation-assignment.source-001",
    decision_ids: input.decisions.map((item) => item.decisionId),
    decision_digests: input.decisions.map((item) => item.canonicalDigest),
    decision_aggregate_digest: d("1"),
    organization_id: "organization.development",
    environment_id: "environment.development",
    classification: "internal",
    disposition_code: input.disposition,
    basis_codes: input.basisCodes,
    basis_digest: d("2"),
    disposition_policy_id: input.dispositionPolicyId,
    disposition_policy_digest: input.dispositionPolicyDigest,
    disposition_policy_version: "policy-version.final-recommendation-disposition-v1",
    attestor_id: "final-recommendation-disposition-attestor.synthetic",
    attestation_digest: d("3"),
    resolved_at: "2026-08-10T12:00:00Z",
    state: "recommendation_final_accepted",
    purpose: input.purpose,
    canonical_digest: d("4"),
    technical_review_completed: true,
    service_impact_review_completed: true,
    technical_review_passed: true,
    service_impact_review_passed: true,
    correction_required: false,
    correction_created: false,
    final_disposition_recorded: true,
    recommendation_approved: true,
    workflow_handoff_eligible: true,
    workflow_created: false,
    itsm_record_created: false,
    change_approved: false,
    execution_authorized: false,
    deployment_authorized: false,
    infrastructure_mutated: false,
    reused: false,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("final recommendation disposition client", () => {
  it("sends exact metadata and accepts only recommendation-level handoff eligibility", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: responseData() }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "final-disposition-ui-001" });

    const result = await createFinalRecommendationDisposition(input);

    expect(result.data.workflow_handoff_eligible).toBe(true);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(typeof init.body).toBe("string");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body).toMatchObject({
      recommendation_id: input.recommendationId,
      disposition_code: input.disposition,
      acknowledged_handoff_eligibility_only: true,
      acknowledged_no_workflow_itsm_change_or_operational_authority: true,
    });
    expect(body).not.toHaveProperty("recommendation_content");
    expect(body).not.toHaveProperty("findings");
    expect(body).not.toHaveProperty("approved_by");
    expect(body).not.toHaveProperty("workflow_payload");
  });

  it("rejects sensitive identity or later operational authority", async () => {
    for (const unsafe of [
      { approved_by_subject_digest: d("9") },
      { workflow_created: true },
      { change_approved: true },
      { execution_authorized: true },
    ]) {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(JSON.stringify({ data: { ...responseData(), ...unsafe } }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      );
      vi.stubGlobal("crypto", { randomUUID: () => "final-disposition-ui-unsafe" });
      await expect(createFinalRecommendationDisposition(input)).rejects.toThrow(
        "unsafe content or authority",
      );
    }
  });

  it("accepts the same exact decision bindings when the backend orders tracks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ data: responseData() }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    vi.stubGlobal("crypto", { randomUUID: () => "final-disposition-ui-ordered" });

    await expect(
      createFinalRecommendationDisposition({
        ...input,
        decisions: [input.decisions[1], input.decisions[0]],
      }),
    ).resolves.toMatchObject({ data: { disposition_id: responseData().disposition_id } });
  });

  it("rejects a disposition whose basis no longer matches the submitted decision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: {
              ...responseData(),
              basis_codes: ["recommendation-final-basis.governance-scope-accepted"],
            },
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("crypto", { randomUUID: () => "final-disposition-ui-basis-drift" });

    await expect(createFinalRecommendationDisposition(input)).rejects.toThrow(
      "does not match the exact review generation",
    );
  });
});
