import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorPackageInstallationReceipt } from "../../api/packageInstallations";
import { PackageInstallationPanel } from "./PackageInstallationPanel";
import { registration } from "./testRegistrationFixture";

const receipt = {
  receipt_id: "connector-package-installation-receipt.test",
  schema_version: "atlas.connector-package-installation-receipt.v1",
  version: 1,
  source_registration_record_id: registration.record_id,
  source_registration_record_digest: registration.canonical_digest,
  source_publication_receipt_id: registration.source_publication_receipt_id,
  source_publication_receipt_digest: registration.source_publication_receipt_digest,
  source_signing_receipt_id: registration.source_signing_receipt_id,
  source_signing_receipt_digest: registration.source_signing_receipt_digest,
  source_approval_request_id: registration.source_approval_request_id,
  source_approval_request_digest: registration.source_approval_request_digest,
  source_final_validation_id: registration.source_final_validation_id,
  source_final_validation_digest: registration.source_final_validation_digest,
  source_acquisition_id: registration.source_acquisition_id,
  source_acquisition_digest: registration.source_acquisition_digest,
  organization_id: registration.organization_id,
  environment_id: registration.environment_id,
  package_digest: registration.package_digest,
  package_size_bytes: registration.package_size_bytes,
  publisher_id: registration.publisher_id,
  connector_id: registration.connector_id,
  release_version: registration.release_version,
  provenance_digest: registration.provenance_digest,
  manifest_digest: registration.manifest.manifest_digest,
  sdk_profile: registration.manifest.sdk_profile,
  registry_profile_id: registration.registry_profile_id,
  registration_policy_id: registration.registration_policy_id,
  registration_policy_digest: registration.registration_policy_digest,
  installation_policy_id: "connector-package-installation-policy.development",
  installation_policy_digest:
    "d9ba6c70baebf8d47188f831c55174c2b4c625e068b2df6d34002ae3eb4ad821",
  installation_policy_version: "version.1.0",
  installation: {
    installer_profile_id: "installer-profile.nonexecuting-v1",
    installation_store_profile_id: "installation-store.nonproduction-immutable",
    artifact_reference_schema: "atlas.connector-installation-artifact-reference.v1",
    package_digest: registration.package_digest,
    package_size_bytes: registration.package_size_bytes,
    stored_at: "2026-08-06T00:00:00Z",
  },
  installed_by: "subject.package-independent-installer",
  purpose: "Install this exact package without instance, target, secret, or runtime authority.",
  installed_at: "2026-08-06T00:00:00Z",
  canonical_digest: "7".repeat(64),
  package_published: true,
  connector_registered: true,
  package_installed: true,
  eligible_for_instance_governance: true,
  promotion_blocked: false,
  reused: false,
  connector_enabled: false,
  instance_created: false,
  target_configured: false,
  credentials_resolved: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorPackageInstallationReceipt;

afterEach(() => vi.unstubAllGlobals());

describe("PackageInstallationPanel", () => {
  it("installs only the exact registration without runtime or destination input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: receipt }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PackageInstallationPanel registration={registration} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByLabelText(
        /package bytes|manifest content|registry address|store path|dependency source|target address|secret reference/i,
      ),
    ).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Installation grants no instance, target, secret, enablement, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Install registered package" }));

    expect(await screen.findByText(receipt.receipt_id)).toBeVisible();
    expect(screen.getByText(receipt.installation.installation_store_profile_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: /configure|enable|execute|deploy/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_registration_record_id: registration.record_id,
      source_registration_record_digest: registration.canonical_digest,
      package_digest: registration.package_digest,
      installation_policy_id: receipt.installation_policy_id,
      installation_policy_digest: receipt.installation_policy_digest,
      acknowledged_installation_grants_no_instance_or_runtime_authority: true,
    });
    for (const forbidden of [
      "package_bytes",
      "manifest",
      "registry_url",
      "artifact_reference",
      "installation_path",
      "dependency_source",
      "instance",
      "target",
      "secret_reference",
      "enable",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
