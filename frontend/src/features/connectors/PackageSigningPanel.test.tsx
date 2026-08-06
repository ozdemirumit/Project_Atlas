import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorPackageSigningReceipt } from "../../api/packageSigning";
import type { ConnectorPublisherAttestation } from "../../api/publisherAttestations";
import { PackageSigningPanel } from "./PackageSigningPanel";

const attestation = {
  report_id: "connector-publisher-attestation.test",
  canonical_digest: "a".repeat(64),
  package_digest: "b".repeat(64),
  environment_id: "environment.development",
  publisher_attested: true,
  eligible_for_package_signing_governance: true,
  promotion_blocked: false,
  outcome: "verified",
} as unknown as ConnectorPublisherAttestation;

const receipt = {
  receipt_id: "connector-package-signing-receipt.test",
  schema_version: "atlas.connector-package-signing-receipt.v1",
  version: 1,
  envelope: {
    envelope_id: "connector-package-signing-envelope.test",
    schema_version: "atlas.connector-package-signing-envelope.v1",
    source_attestation_report_id: attestation.report_id,
    source_attestation_report_digest: attestation.canonical_digest,
    package_digest: attestation.package_digest,
    publisher_id: "publisher.atlas-labs",
    connector_id: "connector.hitachi-ops-center",
    release_version: "version.1.0.0",
    provenance_digest: "c".repeat(64),
    signing_policy_id: "connector-package-signing-policy.development",
    signing_policy_digest:
      "aaa767201869bf63768fe7f57941754094b8d981b93c793b55eecb73b3261881",
    signer_profile_id: "signer-profile.nonproduction-hmac",
    requested_by: "subject.package-independent-signing-requester",
    canonical_digest: "d".repeat(64),
  },
  signature: {
    signer_profile_id: "signer-profile.nonproduction-hmac",
    signer_workload_id: "workload.connector-package-signer",
    key_id: "key.connector-package-signing.nonproduction",
    algorithm: "algorithm.hmac-sha256-nonproduction",
    envelope_digest: "d".repeat(64),
    signature_digest: "e".repeat(64),
    issued_at: "2026-08-06T00:00:00Z",
    expires_at: "2026-08-13T00:00:00Z",
    signature_verified: true,
  },
  organization_id: "organization.development",
  environment_id: "environment.development",
  requested_by: "subject.package-independent-signing-requester",
  signing_policy_id: "connector-package-signing-policy.development",
  signing_policy_digest:
    "aaa767201869bf63768fe7f57941754094b8d981b93c793b55eecb73b3261881",
  signed_at: "2026-08-06T00:00:00Z",
  canonical_digest: "f".repeat(64),
  publisher_attested: true,
  package_signed: true,
  eligible_for_registry_governance: true,
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
} satisfies ConnectorPackageSigningReceipt;

afterEach(() => vi.unstubAllGlobals());

describe("PackageSigningPanel", () => {
  it("requests an exact signature without signer input or later lifecycle controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: receipt }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PackageSigningPanel attestation={attestation} />
      </QueryClientProvider>,
    );

    expect(screen.queryByLabelText(/signer|key|algorithm/i)).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Signing grants no registry, installation, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Request package signature" }));

    expect(await screen.findByText(receipt.receipt_id)).toBeVisible();
    expect(screen.getByText(receipt.signature.signature_digest)).toBeVisible();
    expect(screen.getByRole("button", { name: "Publish signed package" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /register|install|enable|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_attestation_report_id: attestation.report_id,
      source_attestation_report_digest: attestation.canonical_digest,
      package_digest: attestation.package_digest,
      signing_policy_id: receipt.signing_policy_id,
      signing_policy_digest: receipt.signing_policy_digest,
      acknowledged_signing_grants_no_runtime_authority: true,
    });
    for (const forbidden of ["signer_profile_id", "key_id", "algorithm", "signature_value"]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
