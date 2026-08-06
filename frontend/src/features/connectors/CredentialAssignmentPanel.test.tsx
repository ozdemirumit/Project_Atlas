import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorCredentialAssignment } from "../../api/credentialAssignments";
import { CredentialAssignmentPanel } from "./CredentialAssignmentPanel";
import { targetConfigurationBinding as binding } from "./testTargetBindingFixture";

const assignment = {
  assignment_id: "connector-credential-assignment.test",
  schema_version: "atlas.connector-credential-assignment.v1",
  version: 1,
  source_target_binding_id: binding.binding_id,
  source_target_binding_digest: binding.canonical_digest,
  organization_id: binding.organization_id,
  environment_id: binding.environment_id,
  package_digest: binding.package_digest,
  connector_id: binding.connector_id,
  release_version: binding.release_version,
  manifest_digest: binding.manifest_digest,
  instance_id: binding.instance_id,
  instance_key: binding.instance_key,
  display_name: binding.display_name,
  owner_id: binding.owner_id,
  target_profile_id: binding.target_profile_id,
  target_profile_digest: binding.target_profile_digest,
  site_id: binding.site_id,
  target_type: binding.target_type,
  target_product: binding.target_product,
  credential_profile_id: "connector-credential-profile.development-storage-reader",
  credential_profile_digest: "0279f90b6ac015d81a154b723ddbd9bc687b6fccdf286b50cb99ca71e66e1867",
  credential_class: "credential.vendor-api",
  authentication_method: "authentication.api-token",
  vendor_role: "vendor-role.storage-reader",
  privilege_class: "privilege.read-only",
  rotation_state: "rotation.current",
  revocation_state: "revocation.active",
  next_rotation_at: "2026-08-10T00:00:00Z",
  credential_policy_id: "connector-credential-assignment-policy.development",
  credential_policy_digest: "a9ba1da0bb85635e926d69e839c38952153d4349b9e456921101f3b0799f2cca",
  credential_policy_version: "version.1.0",
  assignment_version: 1,
  instance_state: "disabled_credentials_assigned",
  assigned_by: "subject.connector-independent-credential-assigner",
  purpose: "Assign governed credential metadata without secret or runtime access.",
  assigned_at: "2026-08-06T00:00:00Z",
  canonical_digest: "a".repeat(64),
  package_installed: true,
  instance_created: true,
  target_configured: true,
  eligible_for_credential_governance: true,
  credential_references_assigned: true,
  eligible_for_configuration_validation: true,
  promotion_blocked: false,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorCredentialAssignment;

afterEach(() => vi.unstubAllGlobals());

describe("CredentialAssignmentPanel", () => {
  it("assigns exact profile metadata without secret, store, target, or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: assignment }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><CredentialAssignmentPanel binding={binding} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /secret reference|vault|store path|username|password|token value|private key|endpoint|target address|runtime command/i })).toBeNull();
    fireEvent.click(screen.getByLabelText("Assignment grants no secret access, credential resolution, capability, enablement, runtime, execution, or deployment authority."));
    fireEvent.click(screen.getByRole("button", { name: "Assign credential profile" }));

    expect(await screen.findByText(assignment.assignment_id)).toBeVisible();
    expect(screen.getByText(assignment.instance_state)).toBeVisible();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_target_binding_id: binding.binding_id,
      source_target_binding_digest: binding.canonical_digest,
      package_digest: binding.package_digest,
      credential_profile_id: assignment.credential_profile_id,
      credential_profile_digest: assignment.credential_profile_digest,
      credential_policy_id: assignment.credential_policy_id,
      credential_policy_digest: assignment.credential_policy_digest,
      acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority: true,
    });
    for (const forbidden of ["secret_reference_id", "secret_store_profile_id", "vault_path", "secret_value", "username", "password", "access_token", "private_key", "endpoint", "target_id", "capability", "runtime", "execution_authorized"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
