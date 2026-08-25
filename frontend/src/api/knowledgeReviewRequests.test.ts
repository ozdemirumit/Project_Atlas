import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperationalKnowledgeReviewRequest,
  getOperationalKnowledgeReviewRequestOptions,
  getOperationalKnowledgeReviewRequests,
} from "./knowledgeReviewRequests";
import { evidenceKnowledgeDraftInventoryItem as draft } from
  "../features/connectors/testEvidenceDraftFixture";
import {
  knowledgeReviewRequestInventoryItem as reviewRequest,
  knowledgeReviewRequestOption as option,
} from "../features/connectors/testKnowledgeReviewRequestFixture";

const meta = {
  correlation_id: "cor_review_request_test",
  generated_at: "2026-08-25T00:00:10Z",
};

afterEach(() => vi.restoreAllMocks());

describe("operational knowledge review request API client", () => {
  it("loads exact authoritative inventory and signed options for one draft", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [reviewRequest], meta }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
      );

    await expect(getOperationalKnowledgeReviewRequests({ draft }))
      .resolves.toEqual([reviewRequest]);
    await expect(getOperationalKnowledgeReviewRequestOptions({ draft }))
      .resolves.toEqual([option]);
    for (const call of fetchMock.mock.calls) {
      const request = call[0];
      const url = request instanceof Request ? request.url : request;
      expect(url).toContain(`source_draft_id=${encodeURIComponent(draft.draft_id)}`);
    }
  });

  it.each([
    [{ data: [reviewRequest] }],
    [{ data: [reviewRequest], meta, extra: true }],
    [{ data: [reviewRequest], meta: { ...meta, extra: true } }],
  ])("rejects an unsafe exact envelope", async (payload) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    await expect(getOperationalKnowledgeReviewRequests({ draft }))
      .rejects.toThrow("response envelope is unsafe");
  });

  it.each([
    ["source_draft_id", "operational-evidence-knowledge-draft.foreign"],
    ["source_draft_digest", "f".repeat(64)],
    ["connector_id", "connector.foreign"],
    ["instance_id", "connector-instance.foreign"],
    ["capability_id", "capability.foreign.read"],
    ["classification", "classification.restricted"],
    ["retention_policy_id", "retention-policy.foreign"],
    ["reviewer_id", "subject.reviewer"],
  ])("rejects mismatched or forbidden inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ data: [{ ...reviewRequest, [field]: value }], meta }),
        { status: 200 },
      ),
    );

    await expect(getOperationalKnowledgeReviewRequests({ draft }))
      .rejects.toThrow("unsafe records");
  });

  it("rejects missing inventory and option fields", async () => {
    const missingInventory = { ...reviewRequest } as Partial<typeof reviewRequest>;
    delete missingInventory.manifest_bytes;
    const missingOption = { ...option } as Partial<typeof option>;
    delete missingOption.knowledge_item_id;
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [missingInventory], meta }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [missingOption], meta }), { status: 200 }),
      );

    await expect(getOperationalKnowledgeReviewRequests({ draft }))
      .rejects.toThrow("unsafe records");
    await expect(getOperationalKnowledgeReviewRequestOptions({ draft }))
      .rejects.toThrow("unsafe records");
  });

  it.each([
    ["source_draft_digest", "f".repeat(64)],
    ["capability_id", "capability.foreign.read"],
    ["retention_policy_id", "retention-policy.foreign"],
    ["domain_queue_id", "review-queue.unsafe"],
    ["reviewer_id", "subject.reviewer"],
  ])("rejects mismatched or forbidden option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getOperationalKnowledgeReviewRequestOptions({ draft }))
      .rejects.toThrow("unsafe records");
  });

  it("rejects duplicate signed option identifiers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option, option], meta }), { status: 200 }),
    );

    await expect(getOperationalKnowledgeReviewRequestOptions({ draft }))
      .rejects.toThrow("unsafe records");
  });

  it("posts only the draft ID, selected option ID, purpose and acknowledgement", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: reviewRequest, meta }), { status: 201 }),
    );

    await expect(createOperationalKnowledgeReviewRequest({
      draft,
      option,
      purpose: "Request independent review for this exact immutable knowledge draft.",
    })).resolves.toEqual({ data: reviewRequest });
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-knowledge-review-request-input.v1",
      source_draft_id: draft.draft_id,
      review_request_option_id: option.review_request_option_id,
      purpose: "Request independent review for this exact immutable knowledge draft.",
      acknowledged_result_is_only_an_unassigned_review_request: true,
    });
    for (const forbidden of [
      "source_draft_digest", "orchestration_policy_id", "orchestration_policy_digest",
      "domain_queue_id", "security_queue_id", "reviewer_id", "reviewer_group",
      "assignment_strategy", "draft_content", "acl_principals", "retention_policy_id",
      "encryption_profile_id", "review_decision", "knowledge_approved", "knowledge_published",
      "execution_authorized", "infrastructure_mutation_performed",
    ]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
