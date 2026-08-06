import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorPackageRegistrationRecord } from "../../api/packageRegistrations";
import { PackageRegistrationPanel } from "./PackageRegistrationPanel";
import { publication } from "./testPublicationFixture";

const registration = {
  record_id: "connector-package-registration-record.test",
  schema_version: "atlas.connector-package-registration-record.v1",
  version: 1,
  source_publication_receipt_id: publication.receipt_id,
  source_publication_receipt_digest: publication.canonical_digest,
  source_signing_receipt_id: publication.source_signing_receipt_id,
  source_signing_receipt_digest: publication.source_signing_receipt_digest,
  source_approval_request_id: "connector-package-approval-request.test",
  source_approval_request_digest: "1".repeat(64),
  source_final_validation_id: "connector-package-final-validation.test",
  source_final_validation_digest: "2".repeat(64),
  source_acquisition_id: "connector-package-acquisition.test",
  source_acquisition_digest: "3".repeat(64),
  organization_id: publication.organization_id,
  environment_id: publication.environment_id,
  package_digest: publication.package_digest,
  package_size_bytes: publication.package_size_bytes,
  publisher_id: publication.publisher_id,
  connector_id: publication.connector_id,
  release_version: publication.release_version,
  provenance_digest: "4".repeat(64),
  registry_profile_id: publication.publication.registry_profile_id,
  registration_policy_id: "connector-package-registration-policy.development",
  registration_policy_digest:
    "741387e94dbff4338845d602d69415e817605fd09b8d21337eb882728337fac6",
  registration_policy_version: "version.1.0",
  manifest: {
    schema_version: "atlas.connector-manifest.v1",
    connector_id: publication.connector_id,
    manifest_version: "1.0.0",
    release_version: publication.release_version,
    source_status: "quarantined_generated_draft",
    sdk_profile: "atlas.python312.v1",
    target_products: ["Synthetic Storage"],
    network_destination_count: 1,
    configuration_key_count: 2,
    secret_reference_count: 1,
    capabilities: [
      {
        capability_id: "capability.storage.health.read",
        capability_class: "C1",
        required_permission: "storage.health.read",
      },
    ],
    manifest_digest: "5".repeat(64),
  },
  registered_by: "subject.package-independent-registrar",
  purpose: "Register this exact published package without installation or runtime authority.",
  registered_at: "2026-08-06T00:00:00Z",
  canonical_digest: "6".repeat(64),
  package_published: true,
  connector_registered: true,
  eligible_for_installation_governance: true,
  promotion_blocked: false,
  reused: false,
  connector_installed: false,
  connector_enabled: false,
  instance_created: false,
  target_configured: false,
  credentials_resolved: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorPackageRegistrationRecord;

afterEach(() => vi.unstubAllGlobals());

describe("PackageRegistrationPanel", () => {
  it("registers only the exact publication without manifest or lifecycle input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: registration }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PackageRegistrationPanel publication={publication} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByLabelText(/manifest content|capability class|registry address|registry path/i),
    ).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Registration grants no installation, instance, target, secret, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Register published package" }));

    expect(await screen.findByText(registration.record_id)).toBeVisible();
    expect(screen.getByText(registration.manifest.manifest_digest)).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|configure|enable|execute/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_publication_receipt_id: publication.receipt_id,
      source_publication_receipt_digest: publication.canonical_digest,
      package_digest: publication.package_digest,
      registration_policy_id: registration.registration_policy_id,
      registration_policy_digest: registration.registration_policy_digest,
      acknowledged_registration_grants_no_installation_or_runtime_authority: true,
    });
    for (const forbidden of [
      "manifest",
      "capabilities",
      "registry_url",
      "artifact_reference",
      "path",
      "package_bytes",
      "target",
      "secret_reference",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
