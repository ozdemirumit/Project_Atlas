import { apiFetch, ApiRequestError } from "./client";
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

export type ConnectorCredentialAssignmentInventoryItem = {
  assignment_id: string;
  source_target_binding_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  display_name: string;
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
  instance_state: "disabled_credentials_assigned";
  assigned_by: string;
  purpose: string;
  assigned_at: string;
  credential_references_assigned: true;
  eligible_for_configuration_validation: true;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorCredentialAssignmentOption = {
  source_target_binding_id: string;
  credential_profile_id: string;
  credential_profile_digest: string;
  credential_class: string;
  authentication_method: string;
  vendor_role: string;
  privilege_class: string;
  rotation_state: string;
  revocation_state: string;
  next_rotation_at: string;
  credential_profile_expires_at: string;
  credential_policy_id: string;
  credential_policy_digest: string;
  credential_policy_version: string;
  credential_policy_expires_at: string;
  required_assurance_level: string;
  resulting_instance_state: "disabled_credentials_assigned";
  resulting_credential_references_assigned: true;
  eligible_for_configuration_validation: true;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

const hiddenCredentialFields = [
  "secret_reference_id",
  "secret_store_profile_id",
  "secret_store",
  "secret_path",
  "vault_path",
  "secret_value",
  "username",
  "password",
  "access_token",
  "refresh_token",
  "private_key",
  "certificate",
  "target_id",
  "endpoint",
  "host",
  "ip_address",
  "port",
  "signature",
  "request_fingerprint",
  "idempotency_key",
] as const;

function hasHiddenCredentialField(value: Record<string, unknown>): boolean {
  return hiddenCredentialFields.some((field) => field in value);
}

function isAssignment(value: unknown): value is ConnectorCredentialAssignment {
  if (!value || typeof value !== "object") return false;
  const assignment = value as Record<string, unknown>;
  return (
    assignment.schema_version === "atlas.connector-credential-assignment.v1" &&
    assignment.version === 1 &&
    typeof assignment.assignment_id === "string" &&
    typeof assignment.source_target_binding_id === "string" &&
    typeof assignment.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(assignment.canonical_digest) &&
    assignment.instance_state === "disabled_credentials_assigned" &&
    assignment.credential_references_assigned === true &&
    assignment.eligible_for_configuration_validation === true &&
    assignment.credentials_resolved === false &&
    assignment.connector_enabled === false &&
    assignment.runtime_trust_granted === false &&
    assignment.execution_authorized === false &&
    assignment.deployment_approved === false &&
    assignment.infrastructure_mutation_performed === false &&
    !hasHiddenCredentialField(assignment)
  );
}

function isAssignmentResponse(value: unknown): value is { data: ConnectorCredentialAssignment } {
  return Boolean(
    value &&
      typeof value === "object" &&
      "data" in value &&
      isAssignment((value as { data?: unknown }).data),
  );
}

function isInventoryItem(value: unknown): value is ConnectorCredentialAssignmentInventoryItem {
  if (!value || typeof value !== "object") return false;
  const assignment = value as Record<string, unknown>;
  return (
    typeof assignment.assignment_id === "string" &&
    typeof assignment.source_target_binding_id === "string" &&
    typeof assignment.connector_id === "string" &&
    typeof assignment.release_version === "string" &&
    typeof assignment.instance_id === "string" &&
    typeof assignment.display_name === "string" &&
    typeof assignment.credential_profile_id === "string" &&
    typeof assignment.credential_profile_digest === "string" &&
    /^[a-f0-9]{64}$/.test(assignment.credential_profile_digest) &&
    typeof assignment.credential_class === "string" &&
    typeof assignment.authentication_method === "string" &&
    typeof assignment.vendor_role === "string" &&
    typeof assignment.privilege_class === "string" &&
    typeof assignment.rotation_state === "string" &&
    typeof assignment.revocation_state === "string" &&
    typeof assignment.next_rotation_at === "string" &&
    typeof assignment.credential_policy_id === "string" &&
    typeof assignment.credential_policy_digest === "string" &&
    /^[a-f0-9]{64}$/.test(assignment.credential_policy_digest) &&
    typeof assignment.credential_policy_version === "string" &&
    typeof assignment.assigned_by === "string" &&
    typeof assignment.purpose === "string" &&
    typeof assignment.assigned_at === "string" &&
    assignment.instance_state === "disabled_credentials_assigned" &&
    assignment.credential_references_assigned === true &&
    assignment.eligible_for_configuration_validation === true &&
    assignment.credentials_resolved === false &&
    assignment.connector_enabled === false &&
    assignment.runtime_trust_granted === false &&
    assignment.execution_authorized === false &&
    assignment.infrastructure_mutation_performed === false &&
    !hasHiddenCredentialField(assignment)
  );
}

function isOption(value: unknown): value is ConnectorCredentialAssignmentOption {
  if (!value || typeof value !== "object") return false;
  const option = value as Record<string, unknown>;
  return (
    typeof option.source_target_binding_id === "string" &&
    typeof option.credential_profile_id === "string" &&
    typeof option.credential_profile_digest === "string" &&
    /^[a-f0-9]{64}$/.test(option.credential_profile_digest) &&
    typeof option.credential_class === "string" &&
    typeof option.authentication_method === "string" &&
    typeof option.vendor_role === "string" &&
    typeof option.privilege_class === "string" &&
    typeof option.rotation_state === "string" &&
    typeof option.revocation_state === "string" &&
    typeof option.next_rotation_at === "string" &&
    typeof option.credential_profile_expires_at === "string" &&
    typeof option.credential_policy_id === "string" &&
    typeof option.credential_policy_digest === "string" &&
    /^[a-f0-9]{64}$/.test(option.credential_policy_digest) &&
    typeof option.credential_policy_version === "string" &&
    typeof option.credential_policy_expires_at === "string" &&
    typeof option.required_assurance_level === "string" &&
    option.resulting_instance_state === "disabled_credentials_assigned" &&
    option.resulting_credential_references_assigned === true &&
    option.eligible_for_configuration_validation === true &&
    option.credentials_resolved === false &&
    option.connector_enabled === false &&
    option.runtime_trust_granted === false &&
    option.execution_authorized === false &&
    option.infrastructure_mutation_performed === false &&
    !hasHiddenCredentialField(option)
  );
}

export async function getConnectorCredentialAssignments(input?: {
  sourceTargetBindingId?: string;
}): Promise<ConnectorCredentialAssignmentInventoryItem[]> {
  const parameters = new URLSearchParams();
  if (input?.sourceTargetBindingId) {
    parameters.set("source_target_binding_id", input.sourceTargetBindingId);
  }
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const response = await apiFetch(`/api/v1/connectors/credential-assignments${query}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Credential assignment inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Credential assignment inventory returned unsafe records");
  }
  const assignments: ConnectorCredentialAssignmentInventoryItem[] = [];
  for (const candidate of data as unknown[]) {
    if (!isInventoryItem(candidate)) {
      throw new Error("Credential assignment inventory returned unsafe records");
    }
    if (
      input?.sourceTargetBindingId &&
      candidate.source_target_binding_id !== input.sourceTargetBindingId
    ) {
      throw new Error("Credential assignment inventory crossed the requested target scope");
    }
    assignments.push(candidate);
  }
  return assignments;
}

export async function getConnectorCredentialAssignmentOptions(
  sourceTargetBindingId: string,
): Promise<ConnectorCredentialAssignmentOption[]> {
  const parameters = new URLSearchParams({ source_target_binding_id: sourceTargetBindingId });
  const response = await apiFetch(
    `/api/v1/connectors/credential-assignments/options?${parameters.toString()}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("Credential assignment options failed", response.status);
  }
  const payload: unknown = await response.json();
  const data =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : undefined;
  if (!Array.isArray(data)) {
    throw new Error("Credential assignment options returned unsafe evidence");
  }
  const options: ConnectorCredentialAssignmentOption[] = [];
  for (const candidate of data as unknown[]) {
    if (!isOption(candidate) || candidate.source_target_binding_id !== sourceTargetBindingId) {
      throw new Error("Credential assignment options returned unsafe evidence");
    }
    options.push(candidate);
  }
  return options;
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
  ) {
    throw new Error("A current disabled target-configured connector is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(credentialProfileId) ||
    !/^[a-f0-9]{64}$/.test(credentialProfileDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("Exact signed credential profile and policy evidence are required");
  }
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
  if (!response.ok) {
    throw new ApiRequestError("Credential assignment failed", response.status);
  }
  const payload: unknown = await response.json();
  if (!isAssignmentResponse(payload)) {
    throw new Error("Credential service returned unsafe evidence");
  }
  if (
    payload.data.source_target_binding_id !== binding.binding_id ||
    payload.data.source_target_binding_digest !== binding.canonical_digest ||
    payload.data.package_digest !== binding.package_digest ||
    payload.data.instance_id !== binding.instance_id ||
    payload.data.credential_profile_id !== credentialProfileId ||
    payload.data.credential_profile_digest !== credentialProfileDigest ||
    payload.data.credential_policy_id !== policyId ||
    payload.data.credential_policy_digest !== policyDigest
  ) {
    throw new Error("Credential assignment does not match the exact governed evidence");
  }
  return payload;
}
