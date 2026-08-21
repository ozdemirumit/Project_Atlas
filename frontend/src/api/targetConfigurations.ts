import { apiFetch, ApiRequestError } from "./client";
import type { ConnectorInstanceRecord } from "./connectorInstances";

export type ConnectorTargetConfigurationBinding = {
  binding_id: string;
  schema_version: "atlas.connector-target-configuration-binding.v1";
  version: 1;
  source_instance_record_id: string;
  source_instance_record_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  owner_id: string;
  target_profile_id: string;
  target_profile_digest: string;
  site_id: string;
  target_type: string;
  target_product: string;
  target_version: string;
  configuration_policy_id: string;
  configuration_policy_digest: string;
  configuration_policy_version: string;
  configuration_version: 1;
  instance_state: "disabled_target_configured";
  bound_by: string;
  purpose: string;
  bound_at: string;
  canonical_digest: string;
  package_installed: true;
  instance_created: true;
  target_configured: true;
  eligible_for_credential_governance: true;
  promotion_blocked: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ConnectorTargetConfigurationOption = {
  source_instance_record_id: string;
  target_profile_id: string;
  target_profile_digest: string;
  site_id: string;
  target_type: string;
  target_product: string;
  target_version: string;
  target_profile_expires_at: string;
  configuration_policy_id: string;
  configuration_policy_digest: string;
  configuration_policy_version: string;
  configuration_policy_expires_at: string;
  required_assurance_level: string;
  resulting_instance_state: "disabled_target_configured";
  resulting_target_configured: true;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

const hiddenTargetFields = [
  "endpoint",
  "endpoint_origin",
  "host",
  "ip_address",
  "port",
  "target_id",
  "trust_profile_id",
  "network_route_profile_id",
  "proxy_profile_id",
  "certificate",
  "secret_reference",
  "request_fingerprint",
  "idempotency_key",
] as const;

function hasHiddenTargetField(value: Record<string, unknown>): boolean {
  return hiddenTargetFields.some((field) => field in value);
}

function isBinding(value: unknown): value is ConnectorTargetConfigurationBinding {
  if (!value || typeof value !== "object") return false;
  const binding = value as Record<string, unknown>;
  return (
    binding.schema_version === "atlas.connector-target-configuration-binding.v1" &&
    binding.version === 1 &&
    typeof binding.binding_id === "string" &&
    typeof binding.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(binding.canonical_digest) &&
    binding.instance_state === "disabled_target_configured" &&
    binding.target_configured === true &&
    binding.eligible_for_credential_governance === true &&
    binding.credentials_resolved === false &&
    binding.connector_enabled === false &&
    binding.runtime_trust_granted === false &&
    binding.execution_authorized === false &&
    binding.deployment_approved === false &&
    binding.infrastructure_mutation_performed === false &&
    !hasHiddenTargetField(binding)
  );
}

function isBindingResponse(
  value: unknown,
): value is { data: ConnectorTargetConfigurationBinding } {
  return Boolean(
    value &&
      typeof value === "object" &&
      "data" in value &&
      isBinding((value as { data?: unknown }).data),
  );
}

function isOption(value: unknown): value is ConnectorTargetConfigurationOption {
  if (!value || typeof value !== "object") return false;
  const option = value as Record<string, unknown>;
  return (
    typeof option.source_instance_record_id === "string" &&
    typeof option.target_profile_id === "string" &&
    typeof option.target_profile_digest === "string" &&
    /^[a-f0-9]{64}$/.test(option.target_profile_digest) &&
    typeof option.site_id === "string" &&
    typeof option.target_type === "string" &&
    typeof option.target_product === "string" &&
    typeof option.target_version === "string" &&
    typeof option.target_profile_expires_at === "string" &&
    typeof option.configuration_policy_id === "string" &&
    typeof option.configuration_policy_digest === "string" &&
    /^[a-f0-9]{64}$/.test(option.configuration_policy_digest) &&
    typeof option.configuration_policy_version === "string" &&
    typeof option.configuration_policy_expires_at === "string" &&
    typeof option.required_assurance_level === "string" &&
    option.resulting_instance_state === "disabled_target_configured" &&
    option.resulting_target_configured === true &&
    option.credentials_resolved === false &&
    option.connector_enabled === false &&
    option.runtime_trust_granted === false &&
    option.execution_authorized === false &&
    option.infrastructure_mutation_performed === false &&
    !hasHiddenTargetField(option)
  );
}

export async function getConnectorTargetConfigurations(input?: {
  sourceInstanceRecordId?: string;
}): Promise<ConnectorTargetConfigurationBinding[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceInstanceRecordId) {
    parameters.set("source_instance_record_id", input.sourceInstanceRecordId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/target-configuration-bindings${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Target configuration inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Target configuration inventory returned unsafe records");
  }
  const bindings: ConnectorTargetConfigurationBinding[] = [];
  for (const candidate of data as unknown[]) {
    if (!isBinding(candidate)) {
      throw new Error("Target configuration inventory returned unsafe records");
    }
    if (
      input?.sourceInstanceRecordId &&
      candidate.source_instance_record_id !== input.sourceInstanceRecordId
    ) {
      throw new Error("Target configuration inventory crossed the requested instance scope");
    }
    bindings.push(candidate);
  }
  return bindings;
}

export async function getConnectorTargetConfigurationOptions(
  sourceInstanceRecordId: string,
): Promise<ConnectorTargetConfigurationOption[]> {
  const parameters = new URLSearchParams({
    source_instance_record_id: sourceInstanceRecordId,
  });
  const response = await apiFetch(
    `/api/v1/connectors/target-configuration-bindings/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Target configuration options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Target configuration options returned unsafe evidence");
  }
  const options: ConnectorTargetConfigurationOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_instance_record_id !== sourceInstanceRecordId) {
      throw new Error("Target configuration options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
}

export async function createConnectorTargetConfiguration(input: {
  instance: ConnectorInstanceRecord;
  targetProfileId: string;
  targetProfileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { instance, targetProfileId, targetProfileDigest, policyId, policyDigest, purpose } = input;
  if (
    !instance.instance_created ||
    !instance.eligible_for_configuration_governance ||
    instance.target_configured ||
    instance.instance_state !== "disabled_unconfigured"
  ) {
    throw new Error("A current disabled unconfigured connector instance is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(targetProfileId) ||
    !/^[a-f0-9]{64}$/.test(targetProfileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("Exact signed target profile and policy evidence are required");
  }
  const response = await apiFetch("/api/v1/connectors/target-configuration-bindings", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-target-configuration.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-target-configuration-input.v1",
      source_instance_record_id: instance.record_id,
      source_instance_record_digest: instance.canonical_digest,
      package_digest: instance.package_digest,
      target_profile_id: targetProfileId,
      target_profile_digest: targetProfileDigest,
      configuration_policy_id: policyId,
      configuration_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new ApiRequestError("Target configuration failed", response.status);
  }
  const payload: unknown = await response.json();
  if (!isBindingResponse(payload)) {
    throw new Error("Target configuration service returned an unsafe binding");
  }
  if (
    payload.data.source_instance_record_id !== instance.record_id ||
    payload.data.source_instance_record_digest !== instance.canonical_digest ||
    payload.data.package_digest !== instance.package_digest ||
    payload.data.instance_id !== instance.instance_id ||
    payload.data.target_profile_id !== targetProfileId ||
    payload.data.target_profile_digest !== targetProfileDigest ||
    payload.data.configuration_policy_id !== policyId ||
    payload.data.configuration_policy_digest !== policyDigest
  ) {
    throw new Error("Target binding does not match the exact instance and governed evidence");
  }
  return payload;
}
