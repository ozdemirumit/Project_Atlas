import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorCapabilityEnablement,
  getConnectorCapabilityEnablementOptions,
  getConnectorCapabilityEnablements,
  toConnectorCapabilityEnablementInventoryItem,
} from "./capabilityEnablements";
import { configurationValidation } from "../features/connectors/testConfigurationValidationFixture";
import {
  capabilityEnablement,
  capabilityEnablementInventoryItem,
  capabilityEnablementOption,
} from "../features/connectors/testCapabilityEnablementFixture";

afterEach(() => vi.restoreAllMocks());

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

describe("capability enablement API client", () => {
  it("reloads minimized inventory within the requested validation scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [capabilityEnablementInventoryItem] }), { status: 200 }),
    );

    const records = await getConnectorCapabilityEnablements({
      sourceValidationId: configurationValidation.validation_id,
    });

    expect(records).toEqual([capabilityEnablementInventoryItem]);
    const request = fetchMock.mock.calls[0]?.[0];
    expect(request ? requestUrl(request) : "").toContain(
      `source_validation_id=${encodeURIComponent(configurationValidation.validation_id)}`,
    );
  });

  it("rejects inventory that crosses the requested validation scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{
          ...capabilityEnablementInventoryItem,
          source_validation_id: "connector-configuration-validation.outside",
        }],
      }), { status: 200 }),
    );

    await expect(getConnectorCapabilityEnablements({
      sourceValidationId: configurationValidation.validation_id,
    })).rejects.toThrow("crossed the requested validation scope");
  });

  it.each([
    ["api_key", "secret"],
    ["client_secret", "secret"],
    ["authorization_header", "Bearer secret"],
    ["raw_output", "vendor payload"],
    ["stdout", "connector output"],
    ["stderr", "connector error"],
    ["target_hostname", "storage.internal"],
    ["debug", { nested: { password: "secret" } }],
  ])("rejects unknown or nested option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{ ...capabilityEnablementOption, [field]: value }],
      }), { status: 200 }),
    );

    await expect(
      getConnectorCapabilityEnablementOptions(configurationValidation.validation_id),
    ).rejects.toThrow("unsafe evidence");
  });

  it("rejects nested capability leakage and authority expansion", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{
          ...capabilityEnablementOption,
          capabilities: [{
            ...capabilityEnablementOption.capabilities[0],
            command: "show storage",
          }],
        }],
      }), { status: 200 }),
    );
    await expect(
      getConnectorCapabilityEnablementOptions(configurationValidation.validation_id),
    ).rejects.toThrow("unsafe evidence");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({
        data: [{ ...capabilityEnablementOption, deployment_approved: true }],
      }), { status: 200 }),
    );
    await expect(
      getConnectorCapabilityEnablementOptions(configurationValidation.validation_id),
    ).rejects.toThrow("unsafe evidence");
  });

  it("does not accept a stale selected option from another validation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{
          ...capabilityEnablementOption,
          source_validation_id: "connector-configuration-validation.outside",
        }],
      }), { status: 200 }),
    );

    await expect(
      getConnectorCapabilityEnablementOptions(configurationValidation.validation_id),
    ).rejects.toThrow("unsafe evidence");
  });

  it.each([401, 403, 404, 409])("preserves create response status %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));

    await expect(createConnectorCapabilityEnablement({
      validation: configurationValidation,
      option: capabilityEnablementOption,
      purpose: "Apply exact governed capabilities without operational authority.",
    })).rejects.toEqual(expect.objectContaining({ name: "ApiRequestError", status }));
  });

  it("posts only the exact server-selected profile and policy", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: capabilityEnablementInventoryItem }), { status: 201 }),
    );

    await createConnectorCapabilityEnablement({
      validation: configurationValidation,
      option: capabilityEnablementOption,
      purpose: "Apply exact governed capabilities without operational authority.",
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_validation_id: configurationValidation.validation_id,
      source_validation_digest: capabilityEnablementOption.source_validation_digest,
      package_digest: capabilityEnablementOption.package_digest,
      capability_profile_id: capabilityEnablementOption.capability_profile_id,
      capability_profile_digest: capabilityEnablementOption.capability_profile_digest,
      enablement_policy_id: capabilityEnablementOption.enablement_policy_id,
      enablement_policy_digest: capabilityEnablementOption.enablement_policy_digest,
      acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: true,
    });
    for (const forbidden of [
      "capabilities",
      "capability_class",
      "required_permission",
      "endpoint_url",
      "target_ip",
      "host",
      "port",
      "secret_reference_id",
      "username",
      "password",
      "command",
      "parameters",
      "runtime_trust_granted",
      "execution_authorized",
      "deployment_approved",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("rejects a create response whose capabilities differ from the selected profile", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: {
          ...capabilityEnablementInventoryItem,
          capabilities: [{
            ...capabilityEnablementInventoryItem.capabilities[0],
            required_permission: "connectors.storage.unexpected.read",
          }],
        },
      }), { status: 201 }),
    );

    await expect(createConnectorCapabilityEnablement({
      validation: configurationValidation,
      option: capabilityEnablementOption,
      purpose: "Apply exact governed capabilities without operational authority.",
    })).rejects.toThrow("does not match the exact governed evidence");
  });

  it("rejects mismatched minimized create lineage", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    for (const override of [
      { connector_id: "connector.unexpected" },
      { release_version: "version.9.9.9" },
      { enablement_policy_version: "version.unexpected" },
    ]) {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({
          data: { ...capabilityEnablementInventoryItem, ...override },
        }), { status: 201 }),
      );

      await expect(createConnectorCapabilityEnablement({
        validation: configurationValidation,
        option: capabilityEnablementOption,
        purpose: "Apply exact governed capabilities without operational authority.",
      })).rejects.toThrow("does not match the exact governed evidence");
    }
  });

  it("projects the full mutation response to minimized inventory", () => {
    const projected = toConnectorCapabilityEnablementInventoryItem(capabilityEnablement);

    expect(projected).toEqual(capabilityEnablementInventoryItem);
    for (const hidden of [
      "source_validation_digest",
      "package_digest",
      "manifest_digest",
      "target_profile_id",
      "credential_profile_id",
      "capability_profile_digest",
      "enablement_policy_digest",
      "canonical_digest",
    ]) {
      expect(projected).not.toHaveProperty(hidden);
    }
  });
});
