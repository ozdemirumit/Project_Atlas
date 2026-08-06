import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorRuntimeActivation } from "../../api/runtimeActivations";
import type { ConnectorSecretBrokerageAuthorization } from "../../api/secretBrokerageAuthorizations";
import { RuntimeActivationPanel } from "./RuntimeActivationPanel";
import { runtimeTrustGrant } from "./testRuntimeTrustFixture";

const profileDigest = "e".repeat(64);
const policyDigest = "08fa8725d665a3f670d665385c90af861e1eedb7b1898b693cc2b265fdbca337";
const brokerage = {
  authorization_id: "connector-secret-brokerage-authorization.test",
  schema_version: "atlas.connector-secret-brokerage-authorization.v1",
  version: 1,
  source_runtime_trust_grant_id: runtimeTrustGrant.grant_id,
  source_runtime_trust_digest: runtimeTrustGrant.canonical_digest,
  organization_id: runtimeTrustGrant.organization_id,
  environment_id: runtimeTrustGrant.environment_id,
  package_digest: runtimeTrustGrant.package_digest,
  connector_id: runtimeTrustGrant.connector_id,
  release_version: runtimeTrustGrant.release_version,
  manifest_digest: runtimeTrustGrant.manifest_digest,
  instance_id: runtimeTrustGrant.instance_id,
  instance_key: runtimeTrustGrant.instance_key,
  display_name: runtimeTrustGrant.display_name,
  credential_class: "credential.api-token",
  authentication_method: "auth.api-token",
  privilege_class: "privilege.read-only",
  rotation_state: "rotation.current",
  revocation_state: "revocation.active",
  next_rotation_at: "2026-08-09T13:00:00Z",
  runtime_profile_id: runtimeTrustGrant.runtime_profile_id,
  runtime_profile_digest: runtimeTrustGrant.runtime_profile_digest,
  runner_workload_identity_id: runtimeTrustGrant.runner_workload_identity_id,
  secret_delivery_policy_id: runtimeTrustGrant.secret_delivery_policy_id,
  brokerage_profile_id: "connector-secret-brokerage-profile.development-memory-only",
  brokerage_profile_digest: "f".repeat(64),
  delivery_policy_id: runtimeTrustGrant.secret_delivery_policy_id,
  lease_policy_id: "secret-lease-policy.single-use-non-renewable",
  maximum_lease_seconds: 300,
  revocation_policy_id: "secret-revocation-policy.check-before-issue-and-use",
  brokerage_policy_id: "connector-secret-brokerage-policy.development",
  brokerage_policy_digest: "a".repeat(64),
  brokerage_policy_version: "policy-v1",
  authorization_version: 1,
  instance_state: "enabled_secret_brokerage_governed",
  authorized_by: "subject.connector-secret-brokerage-authorizer",
  purpose: "Authorize exact future memory-only secret brokerage without issuing a lease.",
  authorized_at: "2026-08-06T00:00:00Z",
  canonical_digest: "9".repeat(64),
  runtime_boundary_bound: true,
  runtime_trust_granted: true,
  eligible_for_secret_brokerage: true,
  secret_brokerage_governed: true,
  credential_resolution_authorized: true,
  eligible_for_runtime_activation: true,
  promotion_blocked: false,
  secret_lease_issued: false,
  credentials_resolved: false,
  runner_started: false,
  package_loaded: false,
  target_connection_authorized: false,
  capability_invocation_authorized: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorSecretBrokerageAuthorization;

const activation = {
  activation_id: "connector-runtime-activation.test",
  schema_version: "atlas.connector-runtime-activation.v1",
  version: 1,
  source_brokerage_authorization_id: brokerage.authorization_id,
  source_brokerage_authorization_digest: brokerage.canonical_digest,
  organization_id: brokerage.organization_id,
  environment_id: brokerage.environment_id,
  package_digest: brokerage.package_digest,
  connector_id: brokerage.connector_id,
  release_version: brokerage.release_version,
  manifest_digest: brokerage.manifest_digest,
  instance_id: brokerage.instance_id,
  instance_key: brokerage.instance_key,
  display_name: brokerage.display_name,
  runtime_profile_digest: brokerage.runtime_profile_digest,
  runner_identity_digest: "1".repeat(64),
  image_digest: "2".repeat(64),
  workload_identity_digest: "3".repeat(64),
  activation_profile_id: "connector-runtime-activation-profile.development-synthetic",
  activation_profile_digest: profileDigest,
  activation_policy_id: "connector-runtime-activation-policy.development",
  activation_policy_digest: policyDigest,
  activation_policy_version: "policy-v1",
  activation_adapter_id: "connector-runtime-activator.synthetic",
  health_probe_results: [
    { probe_id: "health.package-loaded", outcome: "health.passed" },
    { probe_id: "health.runtime-responsive", outcome: "health.passed" },
  ],
  instance_state: "enabled_runtime_healthy",
  activated_by: "subject.connector-runtime-activation-operator",
  purpose: "Activate the exact isolated connector runtime and verify local health only.",
  activated_at: "2026-08-06T00:00:00Z",
  healthy_at: "2026-08-06T00:00:01Z",
  canonical_digest: "8".repeat(64),
  runtime_boundary_bound: true,
  runtime_trust_granted: true,
  secret_brokerage_governed: true,
  credential_resolution_authorized: true,
  secret_lease_issued: true,
  credentials_resolved: true,
  runner_started: true,
  package_loaded: true,
  runtime_health_verified: true,
  lease_delivery_completed: true,
  delivery_channel_closed: true,
  lease_revocation_confirmed: true,
  eligible_for_target_session_authorization: true,
  target_connected: false,
  target_connection_authorized: false,
  capability_invocation_authorized: false,
  capability_invoked: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorRuntimeActivation;

afterEach(() => vi.unstubAllGlobals());

describe("RuntimeActivationPanel", () => {
  it("activates exact signed runtime evidence without target or command controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: activation }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><RuntimeActivationPanel brokerage={brokerage} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /secret reference|secret store|broker id|lease handle|lease ttl|workload identity|runner image|environment variable|health command|target|host|port|command|parameter/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Activation profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Activation starts only the exact isolated runtime/));
    fireEvent.click(screen.getByRole("button", { name: "Activate runtime" }));

    expect(await screen.findByText(activation.activation_id)).toBeVisible();
    expect(screen.getByText("started")).toBeVisible();
    expect(screen.getByText("loaded")).toBeVisible();
    expect(screen.getByText("closed")).toBeVisible();
    expect(screen.getByText("not connected")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_brokerage_authorization_id: brokerage.authorization_id,
      source_brokerage_authorization_digest: brokerage.canonical_digest,
      package_digest: brokerage.package_digest,
      activation_profile_id: activation.activation_profile_id,
      activation_profile_digest: profileDigest,
      activation_policy_id: activation.activation_policy_id,
      activation_policy_digest: policyDigest,
      acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment: true,
    });
    for (const forbidden of ["credential_profile_id", "secret_reference_id", "secret_store_profile_id", "broker_id", "lease_handle", "lease_ttl", "runner_workload_identity_id", "runner_image", "environment_variables", "health_command", "target_profile_id", "endpoint_url", "host", "port", "command", "parameters", "execution_authorized", "deployment_approved"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
