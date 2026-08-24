import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorRuntimeActivation,
  getConnectorRuntimeActivationOptions,
  getConnectorRuntimeActivations,
} from "./runtimeActivations";
import { secretBrokerageAuthorizationInventoryItem as brokerage } from "../features/connectors/testSecretBrokerageFixture";
import {
  runtimeActivationInventoryItem as activation,
  runtimeActivationOption as option,
} from "../features/connectors/testRuntimeActivationFixture";

afterEach(() => vi.restoreAllMocks());

describe("runtime activation API client", () => {
  it("reloads minimized inventory only within the requested brokerage scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [activation] }), { status: 200 }),
    );

    await expect(getConnectorRuntimeActivations({
      sourceBrokerageAuthorizationId: brokerage.authorization_id,
    })).resolves.toEqual([activation]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      `source_brokerage_authorization_id=${encodeURIComponent(brokerage.authorization_id)}`,
    );
  });

  it("accepts the exact minimized server option contract", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option] }), { status: 200 }),
    );

    await expect(getConnectorRuntimeActivationOptions(brokerage.authorization_id))
      .resolves.toEqual([option]);
  });

  it.each([
    ["signature", "unsafe"],
    ["credential_profile_id", "credential.test"],
    ["secret_reference_id", "secret.test"],
    ["secret_store_profile_id", "store.test"],
    ["broker_id", "broker.test"],
    ["lease_handle", "lease.test"],
    ["runner_command", "start"],
    ["runner_identity_digest", "a".repeat(64)],
    ["image_reference", "registry/image:latest"],
    ["image_digest", "b".repeat(64)],
    ["workload_token", "unsafe"],
    ["health_command", "curl localhost"],
    ["target_hostname", "storage.internal"],
    ["command", "show storage"],
    ["mutable_runner_configuration", { privileged: true }],
  ])("rejects unknown activation option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorRuntimeActivationOptions(brokerage.authorization_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("posts only the exact server-selected profile and policy", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: activation }), { status: 201 }),
    );

    await createConnectorRuntimeActivation({
      brokerage,
      option,
      purpose: "Activate exact isolated runtime and verify signed local health without target access.",
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_brokerage_authorization_id: brokerage.authorization_id,
      source_brokerage_authorization_digest: option.source_brokerage_authorization_digest,
      package_digest: option.package_digest,
      activation_profile_id: option.activation_profile_id,
      activation_profile_digest: option.activation_profile_digest,
      activation_policy_id: option.activation_policy_id,
      activation_policy_digest: option.activation_policy_digest,
      acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment: true,
    });
    for (const forbidden of [
      "credential_profile_id", "secret_reference_id", "secret_store_profile_id", "broker_id",
      "lease_handle", "lease_policy_id", "maximum_lease_seconds", "runner_identity_id",
      "runner_command", "image_reference", "workload_identity_id", "workload_token",
      "delivery_channel", "health_command", "target_profile_id", "endpoint_url", "host", "port",
      "command", "parameters", "execution_authorized", "deployment_approved",
    ]) expect(body).not.toHaveProperty(forbidden);
  });

  it("fails closed on cross-scope or authority-expanded inventory", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{ ...activation, source_brokerage_authorization_id: "connector-brokerage.outside" }],
      }), { status: 200 }),
    );
    await expect(getConnectorRuntimeActivations({
      sourceBrokerageAuthorizationId: brokerage.authorization_id,
    })).rejects.toThrow("crossed the requested brokerage scope");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{ ...activation, target_connection_authorized: true }],
      }), { status: 200 }),
    );
    await expect(getConnectorRuntimeActivations()).rejects.toThrow("unsafe records");
  });

  it.each([
    ["package_digest", "a".repeat(64)],
    ["activation_profile_digest", "b".repeat(64)],
    ["activation_policy_digest", "c".repeat(64)],
    ["canonical_digest", "d".repeat(64)],
  ])("rejects backend-omitted inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...activation, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorRuntimeActivations()).rejects.toThrow("unsafe records");
  });
});
