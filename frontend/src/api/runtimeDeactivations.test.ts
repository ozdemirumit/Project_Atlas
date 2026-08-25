import { afterEach, describe, expect, it, vi } from "vitest";

import { deactivateConnectorRuntime, getConnectorRuntimeDeactivations } from "./runtimeDeactivations";
import type { ConnectorRuntimeActivationInventoryItem } from "./runtimeActivations";

const activation = {
  activation_id: "connector-runtime-activation.test",
  connector_id: "connector.hitachi.opscenter",
  instance_id: "connector-instance.test",
} as ConnectorRuntimeActivationInventoryItem;

const deactivation = {
  deactivation_id: "connector-runtime-deactivation.test",
  activation_id: activation.activation_id,
  activation_version: 1,
  connector_id: activation.connector_id,
  instance_id: activation.instance_id,
  effective_runtime_state: "disabled_runtime",
  deactivated_by: "subject.test.operator",
  reason: "Disable the Atlas runtime during planned maintenance.",
  deactivated_at: "2026-08-25T12:00:00Z",
  atlas_runtime_disabled: true,
  target_authority_revoked: true,
  managed_infrastructure_contacted: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("runtime deactivation API", () => {
  it("lists minimized safe records", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: [deactivation],
    }), { status: 200 })));

    await expect(getConnectorRuntimeDeactivations()).resolves.toEqual([deactivation]);
  });

  it("disables only the selected Atlas runtime with an exact version precondition", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: deactivation,
    }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deactivateConnectorRuntime({
      activation,
      reason: deactivation.reason,
    })).resolves.toEqual(deactivation);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(`${activation.activation_id}/deactivations`);
    expect(init.method).toBe("POST");
    expect(init.body).toContain('"expected_activation_version":1');
    expect(init.body).toContain('"acknowledged_runtime_only_deactivation":true');
  });

  it("rejects authority-expanding or malformed responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: { ...deactivation, infrastructure_mutation_performed: true },
    }), { status: 200 })));

    await expect(getConnectorRuntimeDeactivations()).rejects.toThrow("unsafe records");
  });
});
