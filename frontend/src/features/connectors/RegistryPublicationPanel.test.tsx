import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorPackageSigningReceipt } from "../../api/packageSigning";
import type { ConnectorRegistryPublicationReceipt } from "../../api/registryPublications";
import { RegistryPublicationPanel } from "./RegistryPublicationPanel";
import { receipt as signing } from "./testSigningFixture";

const publication = {
  receipt_id: "connector-registry-publication-receipt.test",
  schema_version: "atlas.connector-registry-publication-receipt.v1",
  version: 1,
  source_signing_receipt_id: signing.receipt_id,
  source_signing_receipt_digest: signing.canonical_digest,
  organization_id: signing.organization_id,
  environment_id: signing.environment_id,
  package_digest: signing.envelope.package_digest,
  package_size_bytes: 4096,
  publisher_id: signing.envelope.publisher_id,
  connector_id: signing.envelope.connector_id,
  release_version: signing.envelope.release_version,
  publication_policy_id: "connector-registry-publication-policy.development",
  publication_policy_digest:
    "682b5447532c5fa571a30f20eab4a5a4a238560655d394ac75f9701ec41145d9",
  verification: {
    verifier_profile_id: "verifier-profile.nonproduction-hmac",
    verifier_workload_id: "workload.connector-package-signature-verifier",
    key_id: signing.signature.key_id,
    algorithm: signing.signature.algorithm,
    envelope_digest: signing.envelope.canonical_digest,
    signature_digest: signing.signature.signature_digest,
    verified_at: "2026-08-06T00:00:00Z",
    signature_valid: true,
  },
  publication: {
    registry_profile_id: "registry-profile.nonproduction-internal",
    publisher_workload_id: "workload.connector-registry-publisher",
    artifact_reference_schema: "atlas.connector-registry-artifact-reference.v1",
    package_digest: signing.envelope.package_digest,
    package_size_bytes: 4096,
    source_signing_receipt_digest: signing.canonical_digest,
    publication_digest: "9".repeat(64),
    published_at: "2026-08-06T00:00:00Z",
    integrity_verified: true,
    reused: false,
  },
  requested_by: "subject.package-independent-registry-publisher",
  purpose: "Publish this exact signed package to the governed internal registry.",
  published_at: "2026-08-06T00:00:00Z",
  canonical_digest: "8".repeat(64),
  publisher_attested: true,
  package_signed: true,
  package_published: true,
  eligible_for_registration_governance: true,
  promotion_blocked: false,
  reused: false,
  connector_registered: false,
  connector_installed: false,
  connector_enabled: false,
  target_configured: false,
  credentials_resolved: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorRegistryPublicationReceipt;

afterEach(() => vi.unstubAllGlobals());

describe("RegistryPublicationPanel", () => {
  it("publishes only the exact signed package without registry or lifecycle input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: publication }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RegistryPublicationPanel signing={signing as ConnectorPackageSigningReceipt} />
      </QueryClientProvider>,
    );

    expect(screen.queryByLabelText(/registry address|path|tag|channel|publisher workload/i)).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Publication grants no registration, installation, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Publish signed package" }));

    expect(await screen.findByText(publication.receipt_id)).toBeVisible();
    expect(screen.getByText(publication.package_digest)).toBeVisible();
    expect(screen.getByRole("button", { name: "Register published package" })).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_signing_receipt_id: signing.receipt_id,
      source_signing_receipt_digest: signing.canonical_digest,
      package_digest: signing.envelope.package_digest,
      publication_policy_id: publication.publication_policy_id,
      publication_policy_digest: publication.publication_policy_digest,
      acknowledged_publication_grants_no_runtime_authority: true,
    });
    for (const forbidden of ["registry_url", "path", "tag", "package_bytes", "signature_value"]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
