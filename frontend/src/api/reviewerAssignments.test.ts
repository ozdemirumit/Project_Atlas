import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperationalKnowledgeReviewerAssignment,
  getOperationalKnowledgeReviewerAssignmentOptions,
  getOperationalKnowledgeReviewerAssignments,
} from "./reviewerAssignments";
import { knowledgeReviewRequestInventoryItem as reviewRequest } from
  "../features/connectors/testKnowledgeReviewRequestFixture";
import {
  reviewerAssignmentInventoryItem as assignment,
  reviewerAssignmentOption as option,
} from "../features/connectors/testReviewerAssignmentFixture";

const meta = {
  correlation_id: "cor_reviewer_assignment_test",
  generated_at: "2026-08-25T00:10:10Z",
};

afterEach(() => vi.restoreAllMocks());

describe("operational knowledge reviewer assignment API client", () => {
  it("loads exact authoritative inventory and signed options for one review request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [assignment], meta }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
      );

    await expect(getOperationalKnowledgeReviewerAssignments({ reviewRequest }))
      .resolves.toEqual([assignment]);
    await expect(getOperationalKnowledgeReviewerAssignmentOptions({ reviewRequest }))
      .resolves.toEqual([option]);
    for (const call of fetchMock.mock.calls) {
      const request = call[0];
      const url = request instanceof Request ? request.url : request;
      expect(url).toContain(
        `source_review_request_id=${encodeURIComponent(reviewRequest.review_request_id)}`,
      );
    }
  });

  it.each([
    [{ data: [assignment] }],
    [{ data: [assignment], meta, extra: true }],
    [{ data: [assignment], meta: { ...meta, extra: true } }],
  ])("rejects an unsafe exact envelope", async (payload) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    await expect(getOperationalKnowledgeReviewerAssignments({ reviewRequest }))
      .rejects.toThrow("response envelope is unsafe");
  });

  it.each([
    ["source_review_request_id", "operational-knowledge-review-request.foreign"],
    ["source_review_request_digest", "f".repeat(64)],
    ["connector_id", "connector.foreign"],
    ["instance_id", "connector-instance.foreign"],
    ["capability_id", "capability.foreign.read"],
    ["reviewer_name", "Hidden Reviewer"],
    ["reviewer_username", "hidden.reviewer"],
    ["reviewer_email", "hidden@example.invalid"],
    ["domain_reviewer_subject_digest", "c".repeat(64)],
    ["requested_by", "subject.requester"],
  ])("rejects mismatched or forbidden inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...assignment, [field]: value }], meta }), {
        status: 200,
      }),
    );

    await expect(getOperationalKnowledgeReviewerAssignments({ reviewRequest }))
      .rejects.toThrow("unsafe records");
  });

  it("rejects missing inventory and option fields", async () => {
    const missingInventory = { ...assignment } as Partial<typeof assignment>;
    delete missingInventory.expires_at;
    const missingOption = { ...option } as Partial<typeof option>;
    delete missingOption.assignment_policy_version;
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [missingInventory], meta }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [missingOption], meta }), { status: 200 }),
      );

    await expect(getOperationalKnowledgeReviewerAssignments({ reviewRequest }))
      .rejects.toThrow("unsafe records");
    await expect(getOperationalKnowledgeReviewerAssignmentOptions({ reviewRequest }))
      .rejects.toThrow("unsafe records");
  });

  it.each([
    ["source_review_request_digest", "f".repeat(64)],
    ["capability_id", "capability.foreign.read"],
    ["domain_queue_id", "review-queue.unsafe"],
    ["reviewer_id", "subject.reviewer"],
    ["reviewer_group", "group.reviewers"],
    ["directory_query", "all-users"],
    ["routing_digest", "c".repeat(64)],
  ])("rejects mismatched or forbidden option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getOperationalKnowledgeReviewerAssignmentOptions({ reviewRequest }))
      .rejects.toThrow("unsafe records");
  });

  it("rejects duplicate signed option identifiers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option, option], meta }), { status: 200 }),
    );

    await expect(getOperationalKnowledgeReviewerAssignmentOptions({ reviewRequest }))
      .rejects.toThrow("unsafe records");
  });

  it("posts only the review request ID, selected option ID, purpose and acknowledgement", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: assignment, meta }), { status: 201 }),
    );

    await expect(createOperationalKnowledgeReviewerAssignment({
      reviewRequest,
      option,
      purpose: "Assign distinct eligible domain and security reviewers without exposing identity.",
    })).resolves.toEqual({ data: assignment });
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-knowledge-reviewer-assignment-input.v1",
      source_review_request_id: reviewRequest.review_request_id,
      assignment_option_id: option.assignment_option_id,
      purpose: "Assign distinct eligible domain and security reviewers without exposing identity.",
      acknowledged_assignment_opens_no_content_and_records_no_decision: true,
    });
    for (const forbidden of [
      "source_review_request_digest", "assignment_policy_id", "assignment_policy_digest",
      "domain_reviewer_id", "security_reviewer_id", "reviewer_name", "reviewer_username",
      "reviewer_email", "reviewer_group", "domain_queue_id", "security_queue_id",
      "directory_query", "routing_digest", "assignment_result", "review_decision",
      "knowledge_approved", "knowledge_published", "execution_authorized",
      "infrastructure_mutation_performed",
    ]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
