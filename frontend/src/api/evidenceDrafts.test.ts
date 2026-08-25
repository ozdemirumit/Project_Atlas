import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperationalEvidenceKnowledgeDraft,
  getOperationalEvidenceKnowledgeDraftOptions,
  getOperationalEvidenceKnowledgeDrafts,
} from "./evidenceDrafts";
import {
  evidenceKnowledgeDraftInventoryItem as draft,
  evidenceKnowledgeDraftOption as option,
} from "../features/connectors/testEvidenceDraftFixture";
import { invocationEvidenceInventoryItem as evidence } from
  "../features/connectors/testInvocationEvidenceFixture";

const meta = {
  correlation_id: "cor_evidence_draft_test",
  generated_at: "2026-08-25T00:00:08Z",
};

afterEach(() => vi.restoreAllMocks());

describe("operational evidence knowledge draft API client", () => {
  it("loads exact minimized inventory for one evidence source", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [draft], meta }), { status: 200 }),
    );

    await expect(getOperationalEvidenceKnowledgeDrafts({ evidence })).resolves.toEqual([draft]);
    const request = fetchMock.mock.calls[0]?.[0];
    const url = request instanceof Request ? request.url : request;
    expect(url).toContain(`source_ingestion_id=${encodeURIComponent(evidence.ingestion_id)}`);
  });

  it("loads only exact signed server options", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
    );

    await expect(getOperationalEvidenceKnowledgeDraftOptions({ evidence })).resolves.toEqual([option]);
    expect(option.required_assurance_level).toBe("single_factor");
  });

  it.each([
    [{ data: [draft] }],
    [{ data: [draft], meta, extra: true }],
    [{ data: [draft], meta: { ...meta, extra: true } }],
  ])("rejects an unsafe exact envelope", async (payload) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    await expect(getOperationalEvidenceKnowledgeDrafts({ evidence }))
      .rejects.toThrow("response envelope is unsafe");
  });

  it.each([
    ["source_ingestion_id", "connector-invocation-evidence-ingestion.foreign"],
    ["source_ingestion_digest", "d".repeat(64)],
    ["evidence_package_id", "connector-evidence-package.foreign"],
    ["capability_id", "capability.foreign.read"],
    ["classification", "classification.restricted"],
  ])("rejects inventory source mismatch %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...draft, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getOperationalEvidenceKnowledgeDrafts({ evidence }))
      .rejects.toThrow("unsafe records");
  });

  it.each([
    ["claim_id", "claim.internal"],
    ["purpose", "hidden internal purpose"],
    ["draft_content", "unsafe"],
    ["acl_principals", ["subject.unsafe"]],
    ["storage_location", "bucket://unsafe"],
    ["reviewer", "subject.reviewer"],
  ])("rejects forbidden inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...draft, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getOperationalEvidenceKnowledgeDrafts({ evidence }))
      .rejects.toThrow("unsafe records");
  });

  it.each([
    ["source_ingestion_id", "connector-invocation-evidence-ingestion.foreign"],
    ["classification", "classification.restricted"],
    ["raw_output", "unsafe"],
    ["retention_policy_digest", "d".repeat(64)],
  ])("rejects mismatched or forbidden option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getOperationalEvidenceKnowledgeDraftOptions({ evidence }))
      .rejects.toThrow("unsafe records");
  });

  it("posts only the selected option ID, purpose and acknowledgement", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: draft, meta }), { status: 201 }),
    );

    await expect(createOperationalEvidenceKnowledgeDraft({
      evidence,
      option,
      purpose: "Create one governed unapproved draft from exact immutable evidence.",
    })).resolves.toEqual({ data: draft });
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-evidence-knowledge-draft-input.v1",
      source_ingestion_id: evidence.ingestion_id,
      curation_option_id: option.curation_option_id,
      purpose: "Create one governed unapproved draft from exact immutable evidence.",
      acknowledged_result_is_an_unapproved_non_retrievable_draft: true,
    });
    for (const forbidden of [
      "source_ingestion_digest", "curation_policy_id", "curation_policy_digest",
      "classification", "access_policy_id", "retention_policy_id", "draft_content",
      "reviewer", "knowledge_published", "model_context_available", "workflow_continued",
      "execution_authorized", "infrastructure_mutation_performed",
    ]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
