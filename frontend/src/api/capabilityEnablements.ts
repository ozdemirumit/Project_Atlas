import { apiFetch } from "./client";
import type { ConnectorConfigurationValidation } from "./configurationValidations";

export type ConnectorGovernedCapability = {
  capability_id: string;
  capability_class: "C0" | "C1";
  required_permission: string;
};

export type ConnectorCapabilityEnablement = {
  enablement_id: string;
  schema_version: "atlas.connector-capability-enablement.v1";
  version: 1;
  source_validation_id: string;
  source_validation_digest: string;
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
  credential_profile_id: string;
  credential_profile_digest: string;
  capability_profile_id: string;
  capability_profile_digest: string;
  capabilities: ConnectorGovernedCapability[];
  enablement_policy_id: string;
  enablement_policy_digest: string;
  enablement_policy_version: string;
  enablement_version: 1;
  instance_state: "enabled_capabilities_governed";
  enabled_by: string;
  purpose: string;
  enabled_at: string;
  canonical_digest: string;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  capability_governance_applied: true;
  connector_enabled: true;
  eligible_for_runtime_trust: true;
  promotion_blocked: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isSafeEnablement(value: unknown): value is { data: ConnectorCapabilityEnablement } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const capabilities = record.capabilities;
  return (
    record.schema_version === "atlas.connector-capability-enablement.v1" &&
    record.version === 1 &&
    typeof record.enablement_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    Array.isArray(capabilities) && capabilities.length > 0 &&
    capabilities.every((item) => item && typeof item === "object" && ["C0", "C1"].includes(String((item as Record<string, unknown>).capability_class))) &&
    record.instance_state === "enabled_capabilities_governed" &&
    record.capability_governance_applied === true &&
    record.connector_enabled === true &&
    record.eligible_for_runtime_trust === true &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("endpoint_url" in record) && !("secret_reference_id" in record) &&
    !("command" in record) && !("parameters" in record) &&
    !("request_fingerprint" in record) && !("idempotency_key" in record)
  );
}

export async function createConnectorCapabilityEnablement(input: {
  validation: ConnectorConfigurationValidation;
  profileId: string;
  profileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { validation, profileId, profileDigest, policyId, policyDigest, purpose } = input;
  if (!validation.configuration_validated || !validation.eligible_for_capability_governance || validation.connector_enabled || validation.instance_state !== "disabled_configuration_validated") throw new Error("A current disabled configuration-validated connector is required");
  if (!/^[a-z][a-z0-9_.:-]{2,127}$/.test(profileId) || !/^[a-f0-9]{64}$/.test(profileDigest) || !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) || !/^[a-f0-9]{64}$/.test(policyDigest) || purpose.trim().length < 20) throw new Error("Exact signed capability profile and policy are required");
  const response = await apiFetch("/api/v1/connectors/capability-enablements", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", "Idempotency-Key": `connector-capability-enablement.${crypto.randomUUID()}` },
    body: JSON.stringify({
      schema_version: "atlas.connector-capability-enablement-input.v1",
      source_validation_id: validation.validation_id,
      source_validation_digest: validation.canonical_digest,
      package_digest: validation.package_digest,
      capability_profile_id: profileId,
      capability_profile_digest: profileDigest,
      enablement_policy_id: policyId,
      enablement_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: true,
    }),
  });
  if (!response.ok) throw new Error(`Capability enablement failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeEnablement(payload)) throw new Error("Enablement service returned unsafe evidence");
  if (payload.data.source_validation_id !== validation.validation_id || payload.data.source_validation_digest !== validation.canonical_digest || payload.data.package_digest !== validation.package_digest || payload.data.instance_id !== validation.instance_id || payload.data.capability_profile_id !== profileId || payload.data.capability_profile_digest !== profileDigest || payload.data.enablement_policy_id !== policyId || payload.data.enablement_policy_digest !== policyDigest) throw new Error("Capability enablement does not match the exact governed evidence");
  return payload;
}
