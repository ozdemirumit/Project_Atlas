import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorRuntimeTrustGrant } from "../../api/runtimeTrustGrants";
import { RuntimeTrustPanel } from "./RuntimeTrustPanel";
import { capabilityEnablement as enablement } from "./testCapabilityEnablementFixture";

const profileDigest = "a".repeat(64);
const policyDigest = "42157b3d8b23514b4f754a2f0f9f507122c6718289a2ae8986e226287d718d33";
const grant = {
  grant_id: "connector-runtime-trust-grant.test",
  schema_version: "atlas.connector-runtime-trust-grant.v1",
  version: 1,
  source_enablement_id: enablement.enablement_id,
  source_enablement_digest: enablement.canonical_digest,
  organization_id: enablement.organization_id,
  environment_id: enablement.environment_id,
  package_digest: enablement.package_digest,
  connector_id: enablement.connector_id,
  release_version: enablement.release_version,
  manifest_digest: enablement.manifest_digest,
  instance_id: enablement.instance_id,
  instance_key: enablement.instance_key,
  display_name: enablement.display_name,
  capability_profile_id: enablement.capability_profile_id,
  capability_profile_digest: enablement.capability_profile_digest,
  capability_count: enablement.capabilities.length,
  runtime_profile_id: "connector-runtime-trust-profile.development-isolated-read-only",
  runtime_profile_digest: profileDigest,
  sdk_profile: "atlas.python312.v1",
  runner_runtime_id: "runner-runtime.python312",
  runner_pool_id: "runner-pool.development-isolated",
  runner_image_digest: "b".repeat(64),
  runner_workload_identity_id: "workload.connector-runner.read-only",
  isolation_profile_id: "isolation-profile.process-restricted",
  filesystem_policy_id: "filesystem-policy.package-read-only",
  egress_policy_id: "egress-policy.target-bound-disabled-until-invocation",
  secret_delivery_policy_id: "secret-delivery-policy.ephemeral-disabled-until-brokered",
  telemetry_policy_id: "telemetry-policy.connector-redacted",
  resource_limit_profile_id: "resource-limit-profile.connector-read-only",
  trust_policy_id: "connector-runtime-trust-policy.development",
  trust_policy_digest: policyDigest,
  trust_policy_version: "policy-v1",
  trust_version: 1,
  instance_state: "enabled_runtime_trusted",
  granted_by: "subject.connector-runtime-trust-granter",
  purpose: "Bind the exact enabled connector to an isolated runtime without starting it.",
  granted_at: "2026-08-06T00:00:00Z",
  canonical_digest: "c".repeat(64),
  configuration_validated: true,
  connectivity_evidence_verified: true,
  capability_governance_applied: true,
  connector_enabled: true,
  eligible_for_runtime_trust: true,
  runtime_boundary_bound: true,
  runtime_trust_granted: true,
  eligible_for_secret_brokerage: true,
  promotion_blocked: false,
  runner_started: false,
  package_loaded: false,
  credential_resolution_authorized: false,
  credentials_resolved: false,
  target_connection_authorized: false,
  capability_invocation_authorized: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorRuntimeTrustGrant;

afterEach(() => vi.unstubAllGlobals());

describe("RuntimeTrustPanel", () => {
  it("binds exact signed runtime evidence without caller-controlled operational inputs", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: grant }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><RuntimeTrustPanel enablement={enablement} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /runner|image|workload|isolation|filesystem|egress|secret|target|host|port|command|parameter/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Runtime profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Trust binds only the signed isolated runtime boundary/));
    fireEvent.click(screen.getByRole("button", { name: "Grant runtime trust" }));

    expect(await screen.findByText(grant.grant_id)).toBeVisible();
    expect(screen.getByText(grant.instance_state)).toBeVisible();
    expect(screen.getByText("not started")).toBeVisible();
    expect(screen.getByText("not resolved")).toBeVisible();
    expect(screen.getByText("not connected")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_enablement_id: enablement.enablement_id,
      source_enablement_digest: enablement.canonical_digest,
      package_digest: enablement.package_digest,
      runtime_profile_id: grant.runtime_profile_id,
      runtime_profile_digest: profileDigest,
      trust_policy_id: grant.trust_policy_id,
      trust_policy_digest: policyDigest,
      acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority: true,
    });
    for (const forbidden of ["runner_runtime_id", "runner_pool_id", "runner_image_digest", "runner_workload_identity_id", "isolation_profile_id", "filesystem_policy_id", "egress_policy_id", "secret_delivery_policy_id", "target_profile_id", "credential_profile_id", "endpoint_url", "host", "port", "secret_reference_id", "command", "parameters", "execution_authorized", "deployment_approved"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
