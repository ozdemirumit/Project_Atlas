import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorSecretBrokerageAuthorization } from "../../api/secretBrokerageAuthorizations";
import { SecretBrokeragePanel } from "./SecretBrokeragePanel";
import { runtimeTrustGrant } from "./testRuntimeTrustFixture";

const profileDigest = "f".repeat(64);
const policyDigest = "be0056e233010d40f427b23cd80f6089e52264adf8a503d39c0d130fa85ced59";
const authorization = {
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
  brokerage_profile_digest: profileDigest,
  delivery_policy_id: runtimeTrustGrant.secret_delivery_policy_id,
  lease_policy_id: "secret-lease-policy.single-use-non-renewable",
  maximum_lease_seconds: 300,
  revocation_policy_id: "secret-revocation-policy.check-before-issue-and-use",
  brokerage_policy_id: "connector-secret-brokerage-policy.development",
  brokerage_policy_digest: policyDigest,
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

afterEach(() => vi.unstubAllGlobals());

describe("SecretBrokeragePanel", () => {
  it("authorizes exact signed brokerage evidence without secret or lease controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: authorization }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><SecretBrokeragePanel runtimeTrust={runtimeTrustGrant} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /secret reference|secret store|broker id|lease ttl|lease seconds|workload identity|delivery policy|target|host|port|command|parameter/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Brokerage profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Authorization grants no lease issuance/));
    fireEvent.click(screen.getByRole("button", { name: "Authorize brokerage" }));

    expect(await screen.findByText(authorization.authorization_id)).toBeVisible();
    expect(screen.getByText(authorization.instance_state)).toBeVisible();
    expect(screen.getByText("not issued")).toBeVisible();
    expect(screen.getByText("not resolved")).toBeVisible();
    expect(screen.getByText("not started")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_runtime_trust_grant_id: runtimeTrustGrant.grant_id,
      source_runtime_trust_digest: runtimeTrustGrant.canonical_digest,
      package_digest: runtimeTrustGrant.package_digest,
      brokerage_profile_id: authorization.brokerage_profile_id,
      brokerage_profile_digest: profileDigest,
      brokerage_policy_id: authorization.brokerage_policy_id,
      brokerage_policy_digest: policyDigest,
      acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment: true,
    });
    for (const forbidden of ["credential_profile_id", "secret_reference_id", "secret_store_profile_id", "broker_id", "lease_policy_id", "maximum_lease_seconds", "runner_workload_identity_id", "delivery_policy_id", "target_profile_id", "endpoint_url", "host", "port", "command", "parameters", "execution_authorized", "deployment_approved"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
