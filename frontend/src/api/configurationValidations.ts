import { apiFetch } from "./client";
import type { ConnectorCredentialAssignment } from "./credentialAssignments";

export type ConnectorConfigurationValidation = {
  validation_id: string;
  schema_version: "atlas.connector-configuration-validation.v1";
  version: 1;
  source_assignment_id: string;
  source_assignment_digest: string;
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
  privilege_class: string;
  evidence_id: string;
  evidence_digest: string;
  probe_runner_id: string;
  probe_runner_version: string;
  network_zone_id: string;
  configuration_result: string;
  connectivity_result: string;
  tls_result: string;
  endpoint_identity_result: string;
  authentication_result: string;
  authorization_result: string;
  product_identity_result: string;
  latency_band: string;
  completed_checks: string[];
  evidence_observed_at: string;
  validation_policy_id: string;
  validation_policy_digest: string;
  validation_policy_version: string;
  validation_version: 1;
  instance_state: "disabled_configuration_validated";
  validated_by: string;
  purpose: string;
  validated_at: string;
  canonical_digest: string;
  package_installed: true;
  instance_created: true;
  target_configured: true;
  credential_references_assigned: true;
  eligible_for_configuration_validation: true;
  configuration_validated: true;
  connectivity_evidence_verified: true;
  eligible_for_capability_governance: true;
  promotion_blocked: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isSafeValidation(value: unknown): value is { data: ConnectorConfigurationValidation } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-configuration-validation.v1" &&
    record.version === 1 &&
    typeof record.validation_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.instance_state === "disabled_configuration_validated" &&
    record.configuration_validated === true &&
    record.connectivity_evidence_verified === true &&
    record.eligible_for_capability_governance === true &&
    record.credentials_resolved === false &&
    record.connector_enabled === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !("endpoint_url" in record) &&
    !("target_ip" in record) &&
    !("secret_reference_id" in record) &&
    !("secret_store_profile_id" in record) &&
    !("raw_probe_output" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record)
  );
}

export async function createConnectorConfigurationValidation(input: {
  assignment: ConnectorCredentialAssignment;
  evidenceId: string;
  evidenceDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { assignment, evidenceId, evidenceDigest, policyId, policyDigest, purpose } = input;
  if (
    !assignment.credential_references_assigned ||
    !assignment.eligible_for_configuration_validation ||
    assignment.credentials_resolved ||
    assignment.instance_state !== "disabled_credentials_assigned"
  ) throw new Error("A current disabled credential-assigned connector is required");
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(evidenceId) ||
    !/^[a-f0-9]{64}$/.test(evidenceDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) throw new Error("Exact signed validation evidence and policy are required");
  const response = await apiFetch("/api/v1/connectors/configuration-validations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-configuration-validation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-configuration-validation-input.v1",
      source_assignment_id: assignment.assignment_id,
      source_assignment_digest: assignment.canonical_digest,
      package_digest: assignment.package_digest,
      evidence_id: evidenceId,
      evidence_digest: evidenceDigest,
      validation_policy_id: policyId,
      validation_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: true,
    }),
  });
  if (!response.ok) throw new Error(`Configuration validation failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isSafeValidation(payload)) throw new Error("Validation service returned unsafe evidence");
  if (
    payload.data.source_assignment_id !== assignment.assignment_id ||
    payload.data.source_assignment_digest !== assignment.canonical_digest ||
    payload.data.package_digest !== assignment.package_digest ||
    payload.data.instance_id !== assignment.instance_id ||
    payload.data.credential_profile_id !== assignment.credential_profile_id ||
    payload.data.evidence_id !== evidenceId ||
    payload.data.evidence_digest !== evidenceDigest ||
    payload.data.validation_policy_id !== policyId ||
    payload.data.validation_policy_digest !== policyDigest
  ) throw new Error("Configuration validation does not match the exact governed evidence");
  return payload;
}
