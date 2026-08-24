import { afterEach, describe, expect, it, vi } from "vitest";

import { configurationValidation as validation } from "../features/connectors/testConfigurationValidationFixture";
import { credentialAssignment as assignment } from "../features/connectors/testCredentialAssignmentFixture";
import {
  createConnectorConfigurationValidation,
  getConnectorConfigurationValidationOptions,
  getConnectorConfigurationValidations,
  toConnectorConfigurationValidationInventoryItem,
  type ConnectorConfigurationValidationOption,
} from "./configurationValidations";

const inventoryItem = {
  validation_id: validation.validation_id,
  source_assignment_id: validation.source_assignment_id,
  connector_id: validation.connector_id,
  release_version: validation.release_version,
  instance_id: validation.instance_id,
  display_name: validation.display_name,
  evidence_id: validation.evidence_id,
  evidence_observed_at: validation.evidence_observed_at,
  configuration_result: validation.configuration_result,
  connectivity_result: validation.connectivity_result,
  tls_result: validation.tls_result,
  endpoint_identity_result: validation.endpoint_identity_result,
  authentication_result: validation.authentication_result,
  authorization_result: validation.authorization_result,
  product_identity_result: validation.product_identity_result,
  latency_band: validation.latency_band,
  completed_checks: validation.completed_checks,
  validation_policy_id: validation.validation_policy_id,
  validation_policy_version: validation.validation_policy_version,
  instance_state: validation.instance_state,
  validated_by: validation.validated_by,
  purpose: validation.purpose,
  validated_at: validation.validated_at,
  configuration_validated: true,
  connectivity_evidence_verified: true,
  eligible_for_capability_governance: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} as const;

const option = {
  source_assignment_id: assignment.assignment_id,
  source_assignment_digest: assignment.canonical_digest,
  package_digest: assignment.package_digest,
  evidence_id: validation.evidence_id,
  evidence_digest: validation.evidence_digest,
  evidence_observed_at: validation.evidence_observed_at,
  evidence_expires_at: "2030-01-01T00:00:00Z",
  configuration_result: validation.configuration_result,
  connectivity_result: validation.connectivity_result,
  tls_result: validation.tls_result,
  endpoint_identity_result: validation.endpoint_identity_result,
  authentication_result: validation.authentication_result,
  authorization_result: validation.authorization_result,
  product_identity_result: validation.product_identity_result,
  latency_band: validation.latency_band,
  completed_checks: validation.completed_checks,
  validation_policy_id: validation.validation_policy_id,
  validation_policy_digest: validation.validation_policy_digest,
  validation_policy_version: validation.validation_policy_version,
  validation_policy_expires_at: "2030-01-01T00:00:00Z",
  required_assurance_level: "SINGLE_FACTOR",
  resulting_instance_state: "disabled_configuration_validated",
  resulting_configuration_validated: true,
  resulting_connectivity_evidence_verified: true,
  eligible_for_capability_governance: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorConfigurationValidationOption;

afterEach(() => vi.restoreAllMocks());

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

describe("configuration validation API client", () => {
  it("reloads validation within the requested assignment scope", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ data: [inventoryItem] }), { status: 200 }));

    const records = await getConnectorConfigurationValidations({
      sourceAssignmentId: assignment.assignment_id,
    });

    expect(records).toHaveLength(1);
    const request = fetchMock.mock.calls[0]?.[0];
    expect(request ? requestUrl(request) : "").toContain(
      `source_assignment_id=${encodeURIComponent(assignment.assignment_id)}`,
    );
  });

  it("rejects options that expose target, secret or raw probe internals", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, raw_probe_output: "vendor payload" }] }), {
        status: 200,
      }),
    );

    await expect(getConnectorConfigurationValidationOptions(assignment.assignment_id))
      .rejects.toThrow("unsafe evidence");
  });

  it.each([
    ["api_key", "secret"],
    ["client_secret", "secret"],
    ["authorization_header", "Bearer secret"],
    ["raw_output", "vendor payload"],
    ["stdout", "probe output"],
    ["stderr", "probe error"],
    ["target_hostname", "storage.internal"],
    ["debug", { response: { password: "secret" } }],
  ])("rejects unknown or nested option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorConfigurationValidationOptions(assignment.assignment_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("rejects unbounded classifications and deployment authority", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ data: [{ ...option, configuration_result: "vendor payload" }] }), {
        status: 200,
      }),
    );
    await expect(getConnectorConfigurationValidationOptions(assignment.assignment_id))
      .rejects.toThrow("unsafe evidence");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ data: [{ ...option, deployment_approved: true }] }), {
        status: 200,
      }),
    );
    await expect(getConnectorConfigurationValidationOptions(assignment.assignment_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("rejects missing fields and nested values in known string fields", async () => {
    const incomplete: Partial<ConnectorConfigurationValidationOption> = { ...option };
    delete incomplete.evidence_expires_at;
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ data: [incomplete] }), { status: 200 }),
    );
    await expect(getConnectorConfigurationValidationOptions(assignment.assignment_id))
      .rejects.toThrow("unsafe evidence");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ data: [{ ...option, evidence_id: { debug: "secret" } }] }), {
        status: 200,
      }),
    );
    await expect(getConnectorConfigurationValidationOptions(assignment.assignment_id))
      .rejects.toThrow("unsafe evidence");
  });

  it("rejects inventory that crosses the requested assignment scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: [{ ...inventoryItem, source_assignment_id: "credential-assignment.outside" }],
        }),
        { status: 200 },
      ),
    );

    await expect(
      getConnectorConfigurationValidations({ sourceAssignmentId: assignment.assignment_id }),
    ).rejects.toThrow("crossed the requested assignment scope");
  });

  it.each([401, 403, 404, 409])("preserves create response status %s", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status }));

    await expect(
      createConnectorConfigurationValidation({
        assignment,
        option,
        purpose: "Verify exact signed configuration evidence without runtime authority.",
      }),
    ).rejects.toEqual(expect.objectContaining({ name: "ApiRequestError", status }));
  });

  it("posts only exact server-selected evidence without operational input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ data: validation }), { status: 201 }));

    await createConnectorConfigurationValidation({
      assignment,
      option,
      purpose: "Verify exact signed configuration evidence without runtime authority.",
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_assignment_id: assignment.assignment_id,
      source_assignment_digest: option.source_assignment_digest,
      evidence_id: option.evidence_id,
      evidence_digest: option.evidence_digest,
      validation_policy_id: option.validation_policy_id,
      validation_policy_digest: option.validation_policy_digest,
    });
    for (const hidden of [
      "endpoint_url",
      "target_ip",
      "host",
      "port",
      "secret_reference_id",
      "username",
      "password",
      "raw_probe_output",
      "command",
      "capability",
    ]) {
      expect(body).not.toHaveProperty(hidden);
    }
  });

  it("projects a create response to the minimized inventory contract", () => {
    const projected = toConnectorConfigurationValidationInventoryItem(validation);

    expect(projected).toEqual(inventoryItem);
    for (const hidden of [
      "source_assignment_digest",
      "package_digest",
      "credential_profile_id",
      "target_profile_id",
      "probe_runner_id",
      "network_zone_id",
      "canonical_digest",
    ]) {
      expect(projected).not.toHaveProperty(hidden);
    }
  });
});
