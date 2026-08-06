import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorBoundedInvocation } from "../../api/boundedInvocations";
import type { ConnectorInvocationEvidence } from "../../api/invocationEvidence";
import { InvocationEvidencePanel } from "./InvocationEvidencePanel";

const policyDigest = "f06fd15735d2a77887160bbed9ea603da8e2a449f65fcc3431ce57fb20c32b6f";
const invocation = {
  invocation_id: "connector-bounded-invocation.test",
  canonical_digest: "1".repeat(64),
  organization_id: "organization.development",
  environment_id: "environment.development",
  package_digest: "2".repeat(64),
  instance_id: "connector-instance.test",
  capability_id: "capability.storage.health.read",
  normalized_redacted_result_digest: "3".repeat(64),
  instance_state: "enabled_bounded_capability_invocation_completed",
  authorization_consumed: true,
  capability_invoked: true,
  result_validated: true,
  result_redacted: true,
  target_session_closed: true,
  lease_revocation_confirmed: true,
  target_connected: false,
  evidence_ingested: false,
} as unknown as ConnectorBoundedInvocation;

const evidence = {
  ingestion_id: "connector-invocation-evidence-ingestion.test",
  schema_version: "atlas.connector-invocation-evidence-ingestion.v1",
  version: 1,
  source_invocation_id: invocation.invocation_id,
  source_invocation_digest: invocation.canonical_digest,
  package_digest: invocation.package_digest,
  instance_id: invocation.instance_id,
  capability_id: invocation.capability_id,
  normalized_redacted_result_digest: invocation.normalized_redacted_result_digest,
  evidence_package_id: "connector-evidence-package.test",
  evidence_item_count: 1,
  classification: "classification.internal",
  ingestion_policy_id: "connector-invocation-evidence-policy.development",
  ingestion_policy_digest: policyDigest,
  canonical_digest: "4".repeat(64),
  instance_state: "enabled_invocation_evidence_ingested",
  source_invocation_completed: true,
  evidence_ingested: true,
  immutable_storage_confirmed: true,
  encrypted_at_rest: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
  knowledge_item_created: false,
  retrieval_published: false,
  model_context_available: false,
  graph_updated: false,
  scheduled: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} as unknown as ConnectorInvocationEvidence;

afterEach(() => vi.unstubAllGlobals());

describe("InvocationEvidencePanel", () => {
  it("preserves only governed metadata without content or publication controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: evidence }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <InvocationEvidencePanel invocation={invocation} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /evidence content|observation value|storage location|acl principal|encryption key/i,
      }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /publish|index|embed/i })).toBeNull();
    fireEvent.click(screen.getByLabelText(/ingestion is one-way/i));
    fireEvent.click(screen.getByRole("button", { name: "Preserve evidence" }));

    expect(await screen.findByText(evidence.evidence_package_id)).toBeVisible();
    expect(screen.getByText("internal")).toBeVisible();
    expect(screen.getByText("at rest")).toBeVisible();
    expect(screen.getByText("not published")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.connector-invocation-evidence-input.v1",
      source_invocation_id: invocation.invocation_id,
      source_invocation_digest: invocation.canonical_digest,
      ingestion_policy_id: evidence.ingestion_policy_id,
      ingestion_policy_digest: policyDigest,
      purpose: "Preserve the exact governed connector observations as immutable evidence.",
      acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority: true,
    });
    for (const forbidden of [
      "evidence_content",
      "observation_values",
      "classification",
      "acl_principals",
      "retention_policy_id",
      "storage_location",
      "encryption_key",
      "retrieval_published",
      "model_context_available",
      "workflow_continued",
      "execution_authorized",
      "deployment_approved",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
