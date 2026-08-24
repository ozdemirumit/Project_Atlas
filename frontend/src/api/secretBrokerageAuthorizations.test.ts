import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorSecretBrokerageAuthorization,
  getConnectorSecretBrokerageAuthorizationOptions,
  getConnectorSecretBrokerageAuthorizations,
} from "./secretBrokerageAuthorizations";
import { runtimeTrustGrantInventoryItem as runtimeTrust } from "../features/connectors/testRuntimeTrustFixture";
import {
  secretBrokerageAuthorizationInventoryItem as authorization,
  secretBrokerageAuthorizationOption as option,
} from "../features/connectors/testSecretBrokerageFixture";

afterEach(() => vi.restoreAllMocks());

describe("secret brokerage API client", () => {
  it("reloads minimized inventory only within the requested runtime trust scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [authorization] }), { status: 200 }),
    );

    await expect(getConnectorSecretBrokerageAuthorizations({
      sourceRuntimeTrustGrantId: runtimeTrust.grant_id,
    })).resolves.toEqual([authorization]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      `source_runtime_trust_grant_id=${encodeURIComponent(runtimeTrust.grant_id)}`,
    );
  });

  it.each([
    ["signature", "unsafe"],
    ["credential_profile_id", "credential.test"],
    ["secret_reference_id", "secret.test"],
    ["secret_store_profile_id", "store.test"],
    ["broker_id", "broker.test"],
    ["lease_handle", "lease.test"],
    ["target_hostname", "storage.internal"],
    ["command", "show storage"],
    ["mutable_runner_configuration", { privileged: true }],
  ])("rejects unknown brokerage option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorSecretBrokerageAuthorizationOptions(runtimeTrust.grant_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("posts only the exact server-selected profile and policy", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: authorization }), { status: 201 }),
    );

    await createConnectorSecretBrokerageAuthorization({
      runtimeTrust,
      option,
      purpose: "Authorize the exact signed memory-only brokerage boundary without operational authority.",
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_runtime_trust_grant_id: runtimeTrust.grant_id,
      source_runtime_trust_digest: option.source_runtime_trust_digest,
      package_digest: option.package_digest,
      brokerage_profile_id: option.brokerage_profile_id,
      brokerage_profile_digest: option.brokerage_profile_digest,
      brokerage_policy_id: option.brokerage_policy_id,
      brokerage_policy_digest: option.brokerage_policy_digest,
      acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment: true,
    });
    for (const forbidden of [
      "credential_profile_id", "secret_reference_id", "secret_store_profile_id", "broker_id",
      "delivery_policy_id", "lease_policy_id", "maximum_lease_seconds",
      "runner_workload_identity_id", "lease_handle", "target_profile_id", "endpoint_url", "host",
      "port", "command", "parameters", "execution_authorized", "deployment_approved",
    ]) expect(body).not.toHaveProperty(forbidden);
  });

  it("fails closed on cross-scope or authority-expanded inventory", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{
          ...authorization,
          source_runtime_trust_grant_id: "connector-runtime-trust-grant.outside",
        }],
      }), { status: 200 }),
    );
    await expect(getConnectorSecretBrokerageAuthorizations({
      sourceRuntimeTrustGrantId: runtimeTrust.grant_id,
    })).rejects.toThrow("crossed the requested runtime trust scope");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{ ...authorization, secret_lease_issued: true }],
      }), { status: 200 }),
    );
    await expect(getConnectorSecretBrokerageAuthorizations())
      .rejects.toThrow("unsafe records");
  });
});
