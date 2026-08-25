import { afterEach, describe, expect, it, vi } from "vitest";

import {
  HITACHI_AUTHORIZATION_SECRET_REFERENCE,
  HITACHI_SYSTEM_CA_TRUST_PROFILE,
  getBundledConnectionConfiguration,
  saveBundledConnectionConfiguration,
  testBundledConnectorConnection,
} from "./bundledConnectorConnections";

const instanceId = "connector-instance.hitachi-test";
const configuration = {
  configuration_id: "connection_configuration.hitachi-test",
  connector_id: "connector.hitachi.opscenter.configuration-manager",
  instance_id: instanceId,
  hostname: "opscenter.example.internal",
  port: 23450,
  trust_profile_id: HITACHI_SYSTEM_CA_TRUST_PROFILE,
  secret_reference_id: HITACHI_AUTHORIZATION_SECRET_REFERENCE,
  configured_at: "2026-08-25T12:00:00Z",
  protocol: "https",
  development_only: true,
  secret_material_stored: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("bundled connector connection API", () => {
  it("treats an absent configuration as unconfigured", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    await expect(getBundledConnectionConfiguration(instanceId)).resolves.toBeNull();
  });

  it("stores only HTTPS target metadata and a fixed secret reference", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: configuration })));
    vi.stubGlobal("fetch", fetchMock);
    await saveBundledConnectionConfiguration({
      instanceId,
      hostname: configuration.hostname,
      port: configuration.port,
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toContain(`"secret_reference_id":"${HITACHI_AUTHORIZATION_SECRET_REFERENCE}"`);
    expect(init.body).not.toMatch(/password|token|authorization_header/i);
  });

  it("accepts only minimized non-mutating connection-test results", async () => {
    const result = {
      test_id: "connection-test.hitachi-test",
      connector_id: configuration.connector_id,
      instance_id: instanceId,
      outcome: "passed",
      result_code: "hitachi_api_compatible",
      retryable: false,
      checked_at: "2026-08-25T12:01:00Z",
      duration_ms: 42,
      read_only_request_performed: true,
      target_details_disclosed: false,
      secret_material_disclosed: false,
      managed_infrastructure_contacted: true,
      infrastructure_mutation_performed: false,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: result }))));
    await expect(testBundledConnectorConnection(instanceId)).resolves.toEqual(result);
  });
});
