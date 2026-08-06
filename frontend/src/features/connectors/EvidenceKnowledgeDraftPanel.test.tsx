import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OperationalEvidenceKnowledgeDraft } from "../../api/evidenceDrafts";
import type { ConnectorInvocationEvidence } from "../../api/invocationEvidence";
import { EvidenceKnowledgeDraftPanel } from "./EvidenceKnowledgeDraftPanel";

const policyDigest = "f2c502a3c820e5f239ac5230137bde9c4817957a340d44ad36e8fd4e880168e8";
const evidence = {
  ingestion_id: "connector-invocation-evidence-ingestion.test",
  schema_version: "atlas.connector-invocation-evidence-ingestion.v1",
  version: 1,
  canonical_digest: "1".repeat(64),
  organization_id: "organization.development",
  environment_id: "environment.development",
  source_invocation_id: "connector-bounded-invocation.test",
  evidence_package_id: "connector-evidence-package.test",
  evidence_content_digest: "2".repeat(64),
  connector_id: "connector.test",
  instance_id: "connector-instance.test",
  capability_id: "capability.storage.health.read",
  classification: "classification.internal",
  access_policy_id: "connector-evidence-access.development-tenant",
  retention_policy_id: "connector-evidence-retention.development-30-days",
  encryption_profile_id: "connector-evidence-encryption.development",
  instance_state: "enabled_invocation_evidence_ingested",
  evidence_ingested: true,
  immutable_storage_confirmed: true,
  knowledge_item_created: false,
  retrieval_published: false,
} as unknown as ConnectorInvocationEvidence;

const draft = {
  draft_id: "operational-evidence-knowledge-draft.test",
  schema_version: "atlas.operational-evidence-knowledge-draft.v1",
  version: 1,
  source_ingestion_id: evidence.ingestion_id,
  source_ingestion_digest: evidence.canonical_digest,
  evidence_package_id: evidence.evidence_package_id,
  evidence_content_digest: evidence.evidence_content_digest,
  connector_id: evidence.connector_id,
  instance_id: evidence.instance_id,
  capability_id: evidence.capability_id,
  knowledge_item_id: "knowledge-item.operational-evidence.test",
  title: "Test connector storage health operational evidence",
  draft_domain: "domain.operational",
  source_authority: "source-authority.system-generated",
  knowledge_lifecycle: "draft",
  classification: evidence.classification,
  access_policy_id: evidence.access_policy_id,
  retention_policy_id: evidence.retention_policy_id,
  encryption_profile_id: evidence.encryption_profile_id,
  curation_policy_id: "operational-evidence-knowledge-draft-policy.development",
  curation_policy_digest: policyDigest,
  canonical_digest: "3".repeat(64),
  instance_state: "draft_operational_knowledge_created",
  evidence_ingested: true,
  knowledge_item_created: true,
  immutable_draft_confirmed: true,
  encrypted_at_rest: true,
  transient_buffers_erased: true,
  artifact_channel_closed: true,
  domain_review_completed: false,
  security_review_completed: false,
  knowledge_approved: false,
  knowledge_published: false,
  chunks_created: false,
  embeddings_created: false,
  retrieval_published: false,
  model_context_available: false,
  graph_updated: false,
  scheduled: false,
  workflow_continued: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} as unknown as OperationalEvidenceKnowledgeDraft;

afterEach(() => vi.unstubAllGlobals());

describe("EvidenceKnowledgeDraftPanel", () => {
  it("creates only a non-retrievable draft without content or publication controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: draft }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <EvidenceKnowledgeDraftPanel evidence={evidence} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /draft content|evidence content|title|classification|acl|retention|storage/i,
      }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /approve|publish|index|embed/i })).toBeNull();
    fireEvent.click(screen.getByLabelText(/result is an unapproved/i));
    fireEvent.click(screen.getByRole("button", { name: "Create review draft" }));

    expect(await screen.findByText(draft.title)).toBeVisible();
    expect(screen.getAllByText("draft").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("pending")).toBeVisible();
    expect(screen.getByText("not published")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toEqual({
      schema_version: "atlas.operational-evidence-knowledge-draft-input.v1",
      source_ingestion_id: evidence.ingestion_id,
      source_ingestion_digest: evidence.canonical_digest,
      curation_policy_id: draft.curation_policy_id,
      curation_policy_digest: policyDigest,
      purpose: "Create a governed review-only draft from exact operational evidence.",
      acknowledged_result_is_an_unapproved_non_retrievable_draft: true,
    });
    for (const forbidden of [
      "evidence_content",
      "draft_content",
      "title",
      "classification",
      "acl_principals",
      "retention_policy_id",
      "storage_location",
      "reviewer",
      "approver",
      "retrieval_published",
      "model_context_available",
      "workflow_continued",
      "execution_authorized",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
