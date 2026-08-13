import { apiFetch, ApiRequestError } from "./client";
import type { ConnectorPackageInstallationReceipt } from "./packageInstallations";

export type ConnectorInstanceRecord = {
  record_id: string;
  schema_version: "atlas.connector-instance-record.v1";
  version: 1 | 2;
  source_installation_receipt_id: string;
  source_installation_receipt_digest: string;
  organization_id: string;
  environment_id: string;
  package_digest: string;
  connector_id: string;
  release_version: string;
  manifest_digest: string;
  sdk_profile: string;
  instance_policy_id: string;
  instance_policy_digest: string;
  instance_policy_version: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  instance_state: "disabled_unconfigured" | "retired";
  owner_id: string;
  support_group_id: string;
  created_by: string;
  purpose: string;
  created_at: string;
  canonical_digest: string;
  package_published: true;
  connector_registered: true;
  package_installed: true;
  instance_created: true;
  eligible_for_configuration_governance: boolean;
  promotion_blocked: false;
  target_configured: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
  retired_by: string | null;
  retired_at: string | null;
  retirement_reason: string | null;
};

export type ConnectorInstanceCreationPolicy = {
  policy_id: string;
  schema_version: "atlas.connector-instance-creation-policy.v1";
  version: 1;
  organization_id: string;
  environment_id: string;
  policy_version: string;
  allowed_sdk_profiles: string[];
  allowed_capability_classes: string[];
  required_initial_state: "disabled_unconfigured";
  maximum_instance_key_length: number;
  maximum_display_name_length: number;
  expires_at: string;
  canonical_digest: string;
};

function isInstanceResponse(value: unknown): value is { data: ConnectorInstanceRecord } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const activeRetirementMetadata =
    record.retired_by === null &&
    record.retired_at === null &&
    record.retirement_reason === null;
  const retiredMetadata =
    typeof record.retired_by === "string" &&
    typeof record.retired_at === "string" &&
    typeof record.retirement_reason === "string";
  return (
    record.schema_version === "atlas.connector-instance-record.v1" &&
    (record.version === 1 || record.version === 2) &&
    typeof record.record_id === "string" &&
    typeof record.instance_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    (record.instance_state === "disabled_unconfigured" || record.instance_state === "retired") &&
    record.package_published === true &&
    record.connector_registered === true &&
    record.package_installed === true &&
    record.instance_created === true &&
    record.eligible_for_configuration_governance ===
      (record.instance_state === "disabled_unconfigured") &&
    record.promotion_blocked === false &&
    record.target_configured === false &&
    record.credentials_resolved === false &&
    record.connector_enabled === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    typeof record.reused === "boolean" &&
    (record.instance_state === "retired" ? retiredMetadata : activeRetirementMetadata) &&
    !("artifact_reference" in record) &&
    !("installation_store_profile_id" in record) &&
    !("request_fingerprint" in record) &&
    !("idempotency_key" in record) &&
    !("target_endpoint" in record) &&
    !("secret_reference" in record)
  );
}

export async function createConnectorInstance(input: {
  installation: ConnectorPackageInstallationReceipt;
  instanceKey: string;
  displayName: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { installation, instanceKey, displayName, policyId, policyDigest, purpose } = input;
  if (
    !installation.package_installed ||
    !installation.eligible_for_instance_governance ||
    installation.promotion_blocked ||
    installation.instance_created
  ) {
    throw new Error("A current governed package installation is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(instanceKey) ||
    displayName.trim().length < 3 ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("A bounded instance identity and exact policy are required");
  }
  const response = await apiFetch("/api/v1/connectors/instances", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-instance.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-instance-creation-input.v1",
      source_installation_receipt_id: installation.receipt_id,
      source_installation_receipt_digest: installation.canonical_digest,
      package_digest: installation.package_digest,
      instance_key: instanceKey,
      display_name: displayName.trim(),
      instance_policy_id: policyId,
      instance_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector instance creation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isInstanceResponse(payload)) {
    throw new Error("Connector instance service returned an unsafe record");
  }
  if (
    payload.data.source_installation_receipt_id !== installation.receipt_id ||
    payload.data.source_installation_receipt_digest !== installation.canonical_digest ||
    payload.data.package_digest !== installation.package_digest ||
    payload.data.connector_id !== installation.connector_id ||
    payload.data.release_version !== installation.release_version ||
    payload.data.manifest_digest !== installation.manifest_digest ||
    payload.data.instance_key !== instanceKey ||
    payload.data.instance_policy_id !== policyId ||
    payload.data.instance_policy_digest !== policyDigest
  ) {
    throw new Error("Instance record does not match the exact installation and request");
  }
  if (
    payload.data.version !== 1 ||
    payload.data.instance_state !== "disabled_unconfigured" ||
    !payload.data.eligible_for_configuration_governance
  ) {
    throw new Error("Connector instance creation did not remain disabled and unconfigured");
  }
  return payload;
}

function isUnknownArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

function isCreationPolicy(value: unknown): value is ConnectorInstanceCreationPolicy {
  if (!value || typeof value !== "object") return false;
  const policy = value as Record<string, unknown>;
  return (
    policy.schema_version === "atlas.connector-instance-creation-policy.v1" &&
    policy.version === 1 &&
    typeof policy.policy_id === "string" &&
    typeof policy.organization_id === "string" &&
    typeof policy.environment_id === "string" &&
    Array.isArray(policy.allowed_sdk_profiles) &&
    policy.allowed_sdk_profiles.every((item) => typeof item === "string") &&
    Array.isArray(policy.allowed_capability_classes) &&
    policy.allowed_capability_classes.every((item) => typeof item === "string") &&
    policy.required_initial_state === "disabled_unconfigured" &&
    typeof policy.maximum_instance_key_length === "number" &&
    typeof policy.maximum_display_name_length === "number" &&
    typeof policy.expires_at === "string" &&
    typeof policy.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(policy.canonical_digest) &&
    !("signed_by" in policy || "request_fingerprint" in policy || "idempotency_key" in policy)
  );
}

export async function getConnectorInstanceCreationPolicies(): Promise<
  ConnectorInstanceCreationPolicy[]
> {
  const response = await apiFetch("/api/v1/connectors/instances/creation-policies", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Connector instance policies failed", response.status);
  }
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload)) {
    throw new Error("Connector instance policies were malformed");
  }
  const data: unknown = payload.data;
  if (!isUnknownArray(data) || !data.every(isCreationPolicy)) {
    throw new Error("Connector instance policies returned unsafe records");
  }
  return data;
}

export async function getConnectorInstances(input: {
  lifecycle: "active" | "retired" | "all";
  query: string;
}): Promise<ConnectorInstanceRecord[]> {
  const parameters = new URLSearchParams({ lifecycle: input.lifecycle });
  if (input.query.trim()) parameters.set("query", input.query.trim());
  const response = await apiFetch(`/api/v1/connectors/instances?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Connector instance inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload)) {
    throw new Error("Connector instance inventory was malformed");
  }
  const data: unknown = payload.data;
  if (!isUnknownArray(data) || !data.every((item) => isInstanceResponse({ data: item }))) {
    throw new Error("Connector instance inventory returned unsafe records");
  }
  return data as ConnectorInstanceRecord[];
}

export async function retireConnectorInstance(input: {
  instance: ConnectorInstanceRecord;
  reason: string;
}): Promise<ConnectorInstanceRecord> {
  const response = await apiFetch(
    `/api/v1/connectors/instances/${encodeURIComponent(input.instance.record_id)}/retirements`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-instance-retire.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-instance-retirement-input.v1",
        expected_version: input.instance.version,
        reason: input.reason.trim(),
        acknowledged_retirement_preserves_history_and_performs_no_runtime_action: true,
      }),
    },
  );
  if (!response.ok) throw new Error(`Connector instance retirement failed with ${response.status}`);
  const payload: unknown = await response.json();
  if (!isInstanceResponse(payload) || payload.data.instance_state !== "retired") {
    throw new Error("Connector instance retirement returned an unsafe record");
  }
  return payload.data;
}
