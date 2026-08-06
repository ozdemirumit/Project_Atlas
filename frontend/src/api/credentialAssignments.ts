import { apiFetch } from "./client";
import type { ConnectorTargetConfigurationBinding } from "./targetConfigurations";

export type ConnectorCredentialAssignment = {
  assignment_id: string;
  schema_version: "atlas.connector-credential-assignment.v1";
  version: 1;
  source_target_binding_id: string;
  source_target_binding_digest: string;
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
  credential_class: string;
  authentication_method: string;
  vendor_role: string;
  privilege_class: string;
  rotation_state: string;
  revocation_state: string;
  next_rotation_at: string;
  credential_policy_id: string;
  credential_policy_digest: string;
  credential_policy_version: string;
  assignment_version: 1;
  instance_state: "disabled_credentials_assigned";
  assigned_by: string;
  purpose: string;
  assigned_at: string;
  canonical_digest: string;
  package_installed: true;
  instance_created: true;
  target_configured: true;
  eligible_for_credential_governance: true;
  credential_references_assigned: true;
  eligible_for_configuration_validation: true;
  promotion_blocked: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isSafeAssignment(value: unknown): value is { data: ConnectorCredentialAssignment } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-credential-assignment.v1" &&
    record.version === 1 &&
    typeof record.assignment_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "disabled_credentials_assigned" &&
    record.credential_references_assigned === true &&
    record.eligible_for_configuration_validation === true &&
    record.credentials_resolved === false &&
    record.connector_enabled === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("secret_reference_id" in record) &&
    !("secret_store_profile_id" in record) &&
    !("secret_value" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record)
  );
}

export async function createConnectorCredentialAssignment(input: {
  binding: ConnectorTargetConfigurationBinding;
  credentialProfileId: string;
  credentialProfileDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { binding, credentialProfileId, credentialProfileDigest, policyId, policyDigest, purpose } = input;
  if (
    !binding.target_configured ||
    !binding.eligible_for_credential_governance ||
    binding.credentials_resolved ||
    binding.instance_state !== "disabled_target_configured"
  ) throw new Error("A current disabled target-configured connector is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(credentialProfileId) ||
    !/^[a-f0-9]{64}$/.test(credentialProfileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) throw new Error("Exact signed credential profile and policy evidence are required");
  const response = await apiFetch("/api/v1/connectors/credential-assignments", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-credential-assignment.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-credential-assignment-input.v1",
      source_target_binding_id: binding.binding_id,
      source_target_binding_digest: binding.canonical_digest,
      package_digest: binding.package_digest,
      credential_profile_id: credentialProfileId,
      credential_profile_digest: credentialProfileDigest,
      credential_policy_id: policyId,
      credential_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority: true,
    }),
  });
  if (!response.ok) throw new Error(`Credential assignment failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeAssignment(payload)) throw new Error("Credential service returned unsafe evidence");
  if (
    payload.data.source_target_binding_id !== binding.binding_id ||
    payload.data.source_target_binding_digest !== binding.canonical_digest ||
    payload.data.package_digest !== binding.package_digest ||
    payload.data.instance_id !== binding.instance_id ||
    payload.data.credential_profile_id !== credentialProfileId ||
    payload.data.credential_profile_digest !== credentialProfileDigest ||
    payload.data.credential_policy_id !== policyId ||
    payload.data.credential_policy_digest !== policyDigest
  ) throw new Error("Credential assignment does not match the exact governed evidence");
  return payload;
}
