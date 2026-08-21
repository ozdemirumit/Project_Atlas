import { afterEach, describe, expect, it, vi } from "vitest";

import { connectorInstanceRecord } from "../features/connectors/testInstanceFixture";
import { installationReceipt } from "../features/connectors/testInstallationFixture";
import { createConnectorInstance, retireConnectorInstance } from "./connectorInstances";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("connector instance API client", () => {
  it.each([401, 403, 409])("preserves create response status %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));

    await expect(
      createConnectorInstance({
        installation: installationReceipt,
        instanceKey: `${installationReceipt.connector_id}-managed`,
        displayName: "Managed storage connector",
        policyId: "connector-instance-creation-policy.development",
        policyDigest: "f".repeat(64),
        purpose: "Create a disabled connector identity for governed lifecycle management.",
      }),
    ).rejects.toEqual(
      expect.objectContaining({
        name: "ApiRequestError",
        status,
      }),
    );
  });

  it.each([401, 403, 409])("preserves retirement response status %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));

    await expect(
      retireConnectorInstance({
        instance: connectorInstanceRecord,
        reason: "Retire this unused connector identity while preserving its history.",
      }),
    ).rejects.toEqual(
      expect.objectContaining({
        name: "ApiRequestError",
        status,
      }),
    );
  });
});
