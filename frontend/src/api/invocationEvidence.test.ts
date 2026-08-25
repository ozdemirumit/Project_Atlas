import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorInvocationEvidence,
  getConnectorInvocationEvidence,
  getConnectorInvocationEvidenceOptions,
} from "./invocationEvidence";
import { boundedInvocationInventoryItem as invocation } from
  "../features/connectors/testBoundedInvocationFixture";
import {
  invocationEvidenceInventoryItem as evidence,
  invocationEvidenceOption as option,
} from "../features/connectors/testInvocationEvidenceFixture";

afterEach(() => vi.restoreAllMocks());

const meta = {
  correlation_id: "cor_invocation_evidence_test",
  generated_at: "2026-08-25T00:00:06Z",
};

describe("invocation evidence API client", () => {
  it("reloads minimized immutable inventory within the exact invocation scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [evidence], meta }), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidence({
      sourceInvocationId: invocation.invocation_id,
    })).resolves.toEqual([evidence]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      "source_invocation_id=" + encodeURIComponent(invocation.invocation_id),
    );
  });

  it("rejects inventory that crosses the requested invocation scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{ ...evidence, source_invocation_id: "connector-invocation.foreign" }],
        meta,
      }), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidence({
      sourceInvocationId: invocation.invocation_id,
    })).rejects.toThrow("crossed the requested invocation scope");
  });

  it("accepts an exact signed server option with normal username-password assurance", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidenceOptions(invocation.invocation_id))
      .resolves.toEqual([option]);
    expect(option.required_assurance_level).toBe("single_factor");
  });

  it.each([
    ["package_digest", invocation.package_digest],
    ["normalized_redacted_result_digest", invocation.normalized_redacted_result_digest],
    ["access_policy_id", "access-policy.connector-evidence"],
    ["access_policy_digest", "5".repeat(64)],
    ["retention_policy_digest", "6".repeat(64)],
    ["encryption_profile_id", "encryption-profile.connector-evidence"],
    ["encryption_profile_digest", "7".repeat(64)],
    ["raw_output", "unsafe"],
    ["target_address", "10.0.0.10"],
    ["storage_location", "bucket://unsafe"],
    ["acl_principals", ["subject.unsafe"]],
    ["encryption_key", "unsafe"],
    ["secret_reference_id", "secret.test"],
    ["idempotency_key", "raw-key"],
    ["mfa_challenge", "unsafe"],
  ])("rejects prohibited option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidenceOptions(invocation.invocation_id))
      .rejects.toThrow("unsafe evidence");
  });

  it.each([
    "source_invocation_digest",
    "ingestion_policy_id",
    "ingestion_policy_digest",
    "classification",
    "retention_policy_id",
    "required_assurance_level",
  ])("rejects an option missing exact field %s", async (field) => {
    const incomplete = { ...option } as Record<string, unknown>;
    delete incomplete[field];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [incomplete], meta }), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidenceOptions(invocation.invocation_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("posts only selected server policy coordinates, purpose and one-way acknowledgement", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: evidence, meta }), { status: 201 }),
    );

    await expect(createConnectorInvocationEvidence({
      invocation,
      option,
      purpose: "Preserve the exact governed connector observations as immutable evidence.",
    })).resolves.toEqual({ data: evidence });
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(
      typeof init?.body === "string" ? init.body : "{}",
    ) as Record<string, unknown>;
    expect(body).toEqual({
      schema_version: "atlas.connector-invocation-evidence-input.v1",
      source_invocation_id: option.source_invocation_id,
      source_invocation_digest: option.source_invocation_digest,
      ingestion_policy_id: option.ingestion_policy_id,
      ingestion_policy_digest: option.ingestion_policy_digest,
      purpose: "Preserve the exact governed connector observations as immutable evidence.",
      acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority: true,
    });
    for (const forbidden of [
      "classification", "access_policy_id", "retention_policy_id", "encryption_profile_id",
      "storage_location", "raw_output", "knowledge_item_created", "scheduled",
      "workflow_continued", "execution_authorized", "deployment_approved",
      "infrastructure_mutation_performed",
    ]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it.each([
    ["raw_output", "unsafe"],
    ["target_endpoint", "https://storage.internal"],
    ["storage_location", "bucket://unsafe"],
    ["claim_id", "claim.internal"],
    ["ingested_by", "subject.internal"],
    ["purpose", "internal purpose"],
  ])("rejects non-minimized inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...evidence, [field]: value }], meta }), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidence({
      sourceInvocationId: invocation.invocation_id,
    })).rejects.toThrow("unsafe records");
  });

  it.each([
    { data: [evidence] },
    { data: [evidence], meta, extra: true },
    { data: [evidence], meta: { ...meta, extra: true } },
    { data: [evidence], meta: { correlation_id: "", generated_at: meta.generated_at } },
  ])("rejects an unsafe response envelope", async (payload) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    await expect(getConnectorInvocationEvidence({
      sourceInvocationId: invocation.invocation_id,
    })).rejects.toThrow("response envelope is unsafe");
  });
});
