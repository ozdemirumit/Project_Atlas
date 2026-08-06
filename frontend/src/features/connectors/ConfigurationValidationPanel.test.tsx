import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorConfigurationValidation } from "../../api/configurationValidations";
import { ConfigurationValidationPanel } from "./ConfigurationValidationPanel";
import { credentialAssignment as assignment } from "./testCredentialAssignmentFixture";

const evidenceDigest = "b".repeat(64);
const policyDigest = "5c683a88f96dd8597098811fb868453e1566767f92ffe940ea2f05cb2ef02aab";
const validation = {
  validation_id: "connector-configuration-validation.test",
  schema_version: "atlas.connector-configuration-validation.v1",
  version: 1,
  source_assignment_id: assignment.assignment_id,
  source_assignment_digest: assignment.canonical_digest,
  organization_id: assignment.organization_id,
  environment_id: assignment.environment_id,
  package_digest: assignment.package_digest,
  connector_id: assignment.connector_id,
  release_version: assignment.release_version,
  manifest_digest: assignment.manifest_digest,
  instance_id: assignment.instance_id,
  instance_key: assignment.instance_key,
  display_name: assignment.display_name,
  owner_id: assignment.owner_id,
  target_profile_id: assignment.target_profile_id,
  target_profile_digest: assignment.target_profile_digest,
  site_id: assignment.site_id,
  target_type: assignment.target_type,
  target_product: assignment.target_product,
  credential_profile_id: assignment.credential_profile_id,
  credential_profile_digest: assignment.credential_profile_digest,
  credential_class: assignment.credential_class,
  authentication_method: assignment.authentication_method,
  privilege_class: assignment.privilege_class,
  evidence_id: "connector-configuration-evidence.development-read-only-probe",
  evidence_digest: evidenceDigest,
  probe_runner_id: "connector-probe-runner.isolated-read-only",
  probe_runner_version: "runner-v1",
  network_zone_id: "network-zone.development-management",
  configuration_result: "configuration.valid",
  connectivity_result: "connectivity.reachable",
  tls_result: "tls.trusted",
  endpoint_identity_result: "endpoint-identity.matched",
  authentication_result: "authentication.succeeded",
  authorization_result: "authorization.read-only-confirmed",
  product_identity_result: "product-identity.matched",
  latency_band: "latency.normal",
  completed_checks: ["check.configuration", "check.connectivity"],
  evidence_observed_at: "2026-08-06T00:00:00Z",
  validation_policy_id: "connector-configuration-validation-policy.development",
  validation_policy_digest: policyDigest,
  validation_policy_version: "policy-v1",
  validation_version: 1,
  instance_state: "disabled_configuration_validated",
  validated_by: "subject.connector-independent-configuration-validator",
  purpose: "Verify bounded signed configuration evidence without runtime authority.",
  validated_at: "2026-08-06T00:00:00Z",
  canonical_digest: "c".repeat(64),
  package_installed: true,
  instance_created: true,
  target_configured: true,
  credential_references_assigned: true,
  eligible_for_configuration_validation: true,
  configuration_validated: true,
  connectivity_evidence_verified: true,
  eligible_for_capability_governance: true,
  promotion_blocked: false,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorConfigurationValidation;

afterEach(() => vi.unstubAllGlobals());

describe("ConfigurationValidationPanel", () => {
  it("verifies exact bounded evidence without target, secret, network, or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: validation }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><ConfigurationValidationPanel assignment={assignment} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /endpoint|target ip|host|port|username|password|token|secret reference|vault|raw probe|command|capability|runtime/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Evidence digest" }), { target: { value: evidenceDigest } });
    fireEvent.click(screen.getByLabelText("Validation grants no target access, secret resolution, capability, enablement, runtime, execution, deployment, or mutation authority."));
    fireEvent.click(screen.getByRole("button", { name: "Verify evidence" }));

    expect(await screen.findByText(validation.validation_id)).toBeVisible();
    expect(screen.getByText(validation.instance_state)).toBeVisible();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy|connect/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_assignment_id: assignment.assignment_id,
      source_assignment_digest: assignment.canonical_digest,
      package_digest: assignment.package_digest,
      evidence_id: validation.evidence_id,
      evidence_digest: evidenceDigest,
      validation_policy_id: validation.validation_policy_id,
      validation_policy_digest: policyDigest,
      acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: true,
    });
    for (const forbidden of ["endpoint_url", "target_ip", "host", "port", "secret_reference_id", "secret_store_profile_id", "vault_path", "secret_value", "username", "password", "access_token", "private_key", "raw_probe_output", "command", "capability", "runtime", "execution_authorized"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
