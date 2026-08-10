import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";
import { RecommendationProtectedContentPanel } from "./RecommendationProtectedContentPanel";

const policyDigest = "42b9ea4db8ff1f29994c124011a97c3d2702f46b0db8a1c1535f76aa3032ae9a";
const lease: RecommendationProtectedInspection = {
  lease_id: "recommendation-protected-inspection-lease.test",
  schema_version: "atlas.recommendation-protected-inspection-lease.v1",
  version: 1,
  source_assignment_set_id: "recommendation-reviewer-assignment.test",
  recommendation_id: "recommendation.promoted.test",
  review_request_id: "recommendation-review-request.test",
  readiness_assessment_id: "recommendation-readiness.test",
  promotion_id: "recommendation-promotion.test",
  organization_id: "organization.development",
  environment_id: "environment.development",
  classification: "internal",
  source_outcome: "preferred",
  option_count: 2,
  preferred_count: 1,
  track_code: "review-track.technical",
  opaque_assignment_id: "recommendation-review-assignment.technical",
  lease_holder_subject_digest: "a".repeat(64),
  lease_digest: "b".repeat(64),
  assignment_binding_digest: "c".repeat(64),
  policy_binding_digest: "d".repeat(64),
  cleanup_digest: "e".repeat(64),
  inspection_policy_id: "recommendation-protected-inspection-policy.development",
  inspection_policy_digest: "f".repeat(64),
  inspection_policy_version: "policy-v1",
  lease_broker_id: "recommendation-protected-inspection-broker.synthetic",
  issued_at: "2026-08-10T10:00:00Z",
  expires_at: "2026-08-10T10:10:00Z",
  state: "recommendation_protected_inspection_leased",
  purpose: "Inspect the assigned recommendation track in a governed read-only boundary.",
  canonical_digest: "1".repeat(64),
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

const content = "Headline: <img src=x onerror=alert(1)>\nSafety: Human review is required.";
const presentation: RecommendationProtectedContent = {
  presentation_id: "recommendation-protected-content.test",
  schema_version: "atlas.recommendation-protected-content-presentation.v1",
  version: 1,
  source_lease_id: lease.lease_id,
  source_assignment_set_id: lease.source_assignment_set_id,
  recommendation_id: lease.recommendation_id,
  review_request_id: lease.review_request_id,
  readiness_assessment_id: lease.readiness_assessment_id,
  promotion_id: lease.promotion_id,
  organization_id: lease.organization_id,
  environment_id: lease.environment_id,
  classification: lease.classification,
  source_outcome: lease.source_outcome,
  option_count: lease.option_count,
  preferred_count: lease.preferred_count,
  track_code: lease.track_code,
  opaque_assignment_id: lease.opaque_assignment_id,
  output_media_type: "media-type.text-plain",
  language: "language.en",
  content,
  presented_content_digest: "2".repeat(64),
  protected_content_bytes_returned: new TextEncoder().encode(content).length,
  redaction_digest: "3".repeat(64),
  truncation_digest: "4".repeat(64),
  cleanup_digest: "5".repeat(64),
  presentation_policy_id: "recommendation-protected-content-policy.development",
  presentation_policy_digest: policyDigest,
  presentation_policy_version: "policy-v1",
  presenter_id: "recommendation-protected-content-presenter.synthetic",
  presented_at: "2026-08-10T10:00:00Z",
  expires_at: lease.expires_at,
  state: "recommendation_protected_content_presented",
  purpose: "Inspect the exact assigned-track recommendation snapshot inside a read-only review boundary.",
  canonical_digest: "6".repeat(64),
  review_requested: true,
  reviewer_assigned: true,
  content_inspection_opened: true,
  content_disclosed: true,
  exact_assignee_verified: true,
  browser_session_bound: true,
  source_integrity_verified: true,
  redaction_applied: true,
  truncated: false,
  active_content_rejected: true,
  transient_buffers_erased: true,
  presenter_channel_closed: true,
  human_findings_recorded: false,
  human_review_completed: false,
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
  return render(
    <QueryClientProvider client={client}>
      <RecommendationProtectedContentPanel lease={lease} />
    </QueryClientProvider>,
  );
}

function acknowledgeAndPresent() {
  fireEvent.click(
    screen.getByLabelText("Sensitive redacted recommendation content is displayed as read-only text."),
  );
  fireEvent.click(
    screen.getByLabelText(
      "Presentation records no finding, decision, approval, workflow, ITSM record, or operational authority.",
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Present protected recommendation" }));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("RecommendationProtectedContentPanel", () => {
  it("presents exact-lease content as transient escaped text without later authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: presentation }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { container } = renderPanel();

    expect(screen.getByRole("button", { name: "Present protected recommendation" })).toBeDisabled();
    acknowledgeAndPresent();

    const record = await screen.findByTestId("recommendation-protected-content");
    expect(record).toHaveTextContent("Governed recommendation snapshot");
    expect(container.querySelector("pre.protected-content-text")?.textContent).toBe(content);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByLabelText("Protected recommendation summary")).toHaveTextContent(
      "Review authoritynot granted",
    );
    expect(screen.queryByRole("button", { name: /finding|decide|approve|execute|deploy/i })).toBeNull();
    expect(storageWrite).not.toHaveBeenCalled();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [url, request] = fetchMock.mock.calls[0] ?? [];
    expect(url).toContain(
      `/recommendations/${lease.recommendation_id}/protected-inspections/leases/${lease.lease_id}/presentations`,
    );
    const body = JSON.parse(typeof request?.body === "string" ? request.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_lease_digest: lease.canonical_digest,
      presentation_policy_id: presentation.presentation_policy_id,
      presentation_policy_digest: policyDigest,
      acknowledged_sensitive_read_only_content: true,
      acknowledged_no_finding_decision_approval_or_operational_authority: true,
    });
    for (const forbidden of ["lease_secret", "finding", "decision", "approval", "command"])
      expect(body).not.toHaveProperty(forbidden);
  });

  it("rejects a presentation carrying a forbidden decision field", async () => {
    const unsafe = { ...presentation, decision: "approved" };
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({ data: unsafe }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    renderPanel();
    acknowledgeAndPresent();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Protected recommendation unavailable",
    );
    expect(screen.queryByText(content)).toBeNull();
  });
});
