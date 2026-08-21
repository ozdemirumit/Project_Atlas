import { afterEach, describe, expect, it, vi } from "vitest";

import { connectorInstanceRecord as instance } from "../features/connectors/testInstanceFixture";
import {
  createConnectorTargetConfiguration,
  getConnectorTargetConfigurationOptions,
  getConnectorTargetConfigurations,
} from "./targetConfigurations";

const bindingPayload = {
  schema_version: "atlas.connector-target-configuration-binding.v1",
  version: 1,
  binding_id: "connector-target-configuration-binding.test",
  source_instance_record_id: instance.record_id,
  canonical_digest: "9".repeat(64),
  instance_state: "disabled_target_configured",
  target_configured: true,
  eligible_for_credential_governance: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
};

const optionPayload = {
  source_instance_record_id: instance.record_id,
  target_profile_id: "connector-target-profile.development-storage",
  target_profile_digest: "a".repeat(64),
  site_id: "site.development-primary",
  target_type: "storage-array",
  target_product: "Synthetic Storage",
  target_version: "version.1.0",
  target_profile_expires_at: "2030-01-01T00:00:00Z",
  configuration_policy_id: "connector-target-configuration-policy.development",
  configuration_policy_digest: "b".repeat(64),
  configuration_policy_version: "version.1.0",
  configuration_policy_expires_at: "2030-01-01T00:00:00Z",
  required_assurance_level: "SINGLE_FACTOR",
  resulting_instance_state: "disabled_target_configured",
  resulting_target_configured: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("target configuration API client", () => {
  it("reloads bindings within the requested connector-instance scope", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ data: [bindingPayload] }), { status: 200 }));

    const bindings = await getConnectorTargetConfigurations({
      sourceInstanceRecordId: instance.record_id,
    });

    expect(bindings).toHaveLength(1);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl =
      request instanceof Request ? request.url : request instanceof URL ? request.href : request;
    expect(requestUrl).toContain(
      `source_instance_record_id=${encodeURIComponent(instance.record_id)}`,
    );
  });

  it("rejects target options that expose hidden connection internals", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ data: [{ ...optionPayload, endpoint: "https://storage.example" }] }),
        { status: 200 },
      ),
    );

    await expect(getConnectorTargetConfigurationOptions(instance.record_id)).rejects.toThrow(
      "unsafe evidence",
    );
  });

  it.each([401, 403, 404, 409])("preserves create response status %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));

    await expect(
      createConnectorTargetConfiguration({
        instance,
        targetProfileId: optionPayload.target_profile_id,
        targetProfileDigest: optionPayload.target_profile_digest,
        policyId: optionPayload.configuration_policy_id,
        policyDigest: optionPayload.configuration_policy_digest,
        purpose: "Bind governed target metadata without runtime authority.",
      }),
    ).rejects.toEqual(expect.objectContaining({ name: "ApiRequestError", status }));
  });
});
