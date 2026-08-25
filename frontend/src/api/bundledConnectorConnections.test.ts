import { afterEach, describe, expect, it, vi } from "vitest";

import {
  HITACHI_AUTHORIZATION_SECRET_REFERENCE,
  HITACHI_SYSTEM_CA_TRUST_PROFILE,
  disableBundledConnectorRuntime,
  enableBundledConnectorRuntime,
  getBundledConnectionConfiguration,
  getBundledConnectorRuntimeState,
  getLatestBundledConnectorConnectionTest,
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

  it("stores only HTTPS target metadata and an operator-provided secret reference", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: configuration })));
    vi.stubGlobal("fetch", fetchMock);
    await saveBundledConnectionConfiguration({
      instanceId,
      hostname: configuration.hostname,
      port: configuration.port,
      secretReferenceId: configuration.secret_reference_id,
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toContain(`"secret_reference_id":"${HITACHI_AUTHORIZATION_SECRET_REFERENCE}"`);
    expect(init.body).not.toMatch(/password|token|authorization_header/i);
  });

  it("reads, enables and disables only the bundled read-only runtime", async () => {
    const disabled = {
      instance_id: instanceId,
      state: "disabled",
      version: 1,
      changed_at: null,
      changed_by: null,
      reason: null,
      managed_infrastructure_contacted: false,
      infrastructure_mutation_performed: false,
    };
    const enabled = {
      ...disabled,
      state: "enabled_read_only",
      version: 2,
      changed_at: "2026-08-25T13:00:00Z",
      changed_by: "subject.connector-operator",
      reason: "Enable the verified read-only connector.",
    };
    const stopped = {
      ...disabled,
      version: 3,
      changed_at: "2026-08-25T13:05:00Z",
      changed_by: "subject.connector-operator",
      reason: "Planned connector maintenance.",
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: disabled })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: enabled })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: stopped })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getBundledConnectorRuntimeState(instanceId)).resolves.toEqual(disabled);
    await expect(enableBundledConnectorRuntime(instanceId)).resolves.toEqual(enabled);
    await expect(disableBundledConnectorRuntime({
      instanceId,
      reason: stopped.reason,
    })).resolves.toEqual(stopped);

    const [, enableInit] = fetchMock.mock.calls[1] as [string, RequestInit];
    const [, disableInit] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect(enableInit.body).toBe(JSON.stringify({
      acknowledged_read_only_operation: true,
    }));
    expect(disableInit.body).toBe(JSON.stringify({
      reason: stopped.reason,
      acknowledged_runtime_stop: true,
    }));
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

  it("retrieves the latest minimized test result and treats absence as no test", async () => {
    const result = {
      test_id: "connection-test.hitachi-latest",
      connector_id: configuration.connector_id,
      instance_id: instanceId,
      outcome: "failed",
      result_code: "connection_test_credentials_unavailable",
      retryable: false,
      checked_at: "2026-08-25T12:02:00Z",
      duration_ms: 0,
      read_only_request_performed: false,
      target_details_disclosed: false,
      secret_material_disclosed: false,
      managed_infrastructure_contacted: false,
      infrastructure_mutation_performed: false,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: result })))
      .mockResolvedValueOnce(new Response(null, { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getLatestBundledConnectorConnectionTest(instanceId)).resolves.toEqual(result);
    await expect(getLatestBundledConnectorConnectionTest(instanceId)).resolves.toBeNull();
  });
});
