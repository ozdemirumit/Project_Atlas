import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalKnowledgeTrackReviewDecision } from "../../api/reviewDecisions";
import { CorrectionResubmissionPanel } from "./CorrectionResubmissionPanel";

const policyDigest = "bf82889bfba836f13350b88151d2c78af6b1807c72aa6c7c85750132637d2f13";
const decision = {
  decision_id: "operational-knowledge-track-review-decision.domain",
  schema_version: "atlas.operational-knowledge-track-review-decision.v1",
  version: 1,
  environment_id: "environment.development",
  review_request_id: "operational-knowledge-review-request.test",
  source_review_request_digest: "a".repeat(64),
  all_tracks_decided: true,
  all_tracks_passed: false,
  any_correction_required: true,
  track_decisions: [
    {
      track_code: "review-track.domain",
      decision_id: "operational-knowledge-track-review-decision.domain",
      canonical_digest: "b".repeat(64),
      disposition_code: "review-disposition.changes-required",
    },
    {
      track_code: "review-track.security",
      decision_id: "operational-knowledge-track-review-decision.security",
      canonical_digest: "c".repeat(64),
      disposition_code: "review-disposition.passed",
    },
  ],
} as OperationalKnowledgeTrackReviewDecision;

const correction = {
  correction_id: "operational-knowledge-correction.test",
  schema_version: "atlas.operational-knowledge-correction-resubmission.v1",
  version: 1,
  source_review_request_id: decision.review_request_id,
  source_review_request_digest: decision.source_review_request_digest,
  source_draft_id: "operational-evidence-knowledge-draft.original",
  source_draft_digest: "d".repeat(64),
  source_decision_ids: decision.track_decisions.map((item) => item.decision_id),
  source_decision_digests: decision.track_decisions.map((item) => item.canonical_digest),
  decision_aggregate_digest: "e".repeat(64),
  organization_id: "organization.atlas-development",
  environment_id: decision.environment_id,
  knowledge_item_id: "knowledge-item.test",
  prior_draft_version_id: "knowledge-draft-version.original",
  title: "Operational knowledge test",
  classification: "classification.internal",
  correction_submission_id: "trusted-correction-submission.test",
  correction_submission_digest: "f".repeat(64),
  correction_policy_id: "operational-knowledge-correction-policy.development",
  correction_policy_digest: policyDigest,
  correction_policy_version: "policy-version.test",
  adapter_id: "operational-knowledge-correction-adapter.synthetic",
  attestation_digest: "1".repeat(64),
  new_draft_id: "operational-evidence-knowledge-draft.corrected",
  new_draft_version_id: "knowledge-draft-version.corrected",
  new_draft_content_digest: "2".repeat(64),
  new_review_request_id: "operational-knowledge-review-request.corrected",
  new_manifest_id: "knowledge-review-manifest.corrected",
  domain_status: "awaiting_reviewer",
  security_status: "awaiting_reviewer",
  review_generation: 2,
  instance_state: "operational_knowledge_correction_resubmitted",
  canonical_digest: "3".repeat(64),
  correction_created: true,
  corrected_draft_created: true,
  review_resubmitted: true,
  reviewer_assigned: false,
  content_inspection_opened: false,
  domain_review_completed: false,
  security_review_completed: false,
  knowledge_approved: false,
  knowledge_published: false,
  retrieval_published: false,
  model_context_available: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("CorrectionResubmissionPanel", () => {
  it("submits only trusted metadata and resets both review tracks", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: correction }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CorrectionResubmissionPanel decision={decision} />
      </QueryClientProvider>,
    );

    const submit = screen.getByRole("button", { name: "Create new review generation" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Trusted correction submission ID"), {
      target: { value: correction.correction_submission_id },
    });
    fireEvent.change(screen.getByLabelText("Submission digest"), {
      target: { value: correction.correction_submission_digest },
    });
    fireEvent.click(
      screen.getByLabelText("The trusted submission addresses the exact review requirements."),
    );
    fireEvent.click(
      screen.getByLabelText(
        "A new immutable draft and independent review generation will be created.",
      ),
    );
    fireEvent.click(
      screen.getByLabelText(
        "This correction grants no approval, publication, or operational authority.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Review generation resubmitted")).toBeVisible();
    expect(screen.getByText("not granted")).toBeVisible();
    expect(screen.queryByRole("button", { name: /approve|publish|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      schema_version: "atlas.operational-knowledge-correction-input.v1",
      source_review_request_digest: decision.source_review_request_digest,
      source_decision_ids: decision.track_decisions.map((item) => item.decision_id),
      source_decision_digests: decision.track_decisions.map((item) => item.canonical_digest),
      correction_submission_id: correction.correction_submission_id,
      correction_submission_digest: correction.correction_submission_digest,
      correction_policy_id: correction.correction_policy_id,
      correction_policy_digest: policyDigest,
      acknowledged_exact_change_requirements_addressed: true,
      acknowledged_new_immutable_review_generation: true,
      acknowledged_no_approval_or_operational_authority: true,
    });
    expect(new Headers(request?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    for (const forbidden of [
      "corrected_content",
      "correction_patch",
      "findings",
      "approval",
      "publication",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
  });
});
