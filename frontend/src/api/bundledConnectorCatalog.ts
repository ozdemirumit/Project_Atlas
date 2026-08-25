import { ApiRequestError, apiFetch } from "./client";

export type BundledConnectorDescriptor = {
  catalog_item_id: string;
  schema_version: "atlas.bundled-connector-descriptor.v1";
  version: 1;
  connector_id: string;
  display_name: string;
  vendor_name: string;
  release_version: string;
  sdk_profile: string;
  capability_ids: string[];
  capability_classes: string[];
  canonical_digest: string;
  trusted_bundled: true;
  development_only: true;
  catalog_evidence_only: true;
  target_authority_granted: false;
  credential_authority_granted: false;
  capability_authority_granted: false;
  network_authority_granted: false;
  runtime_authority_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

export type BundledConnectorInstanceResult = {
  record_id: string;
  version: number;
  organization_id: string;
  environment_id: string;
  connector_id: string;
  release_version: string;
  instance_id: string;
  instance_key: string;
  display_name: string;
  instance_state: "disabled_unconfigured";
  purpose: string;
  created_at: string;
  canonical_digest: string;
  eligible_for_configuration_governance: true;
  target_configured: false;
  credentials_resolved: false;
  connector_enabled: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const digest = /^[a-f0-9]{64}$/;

function isDescriptor(value: unknown): value is BundledConnectorDescriptor {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return item.schema_version === "atlas.bundled-connector-descriptor.v1" &&
    item.version === 1 &&
    ["catalog_item_id", "connector_id", "release_version", "sdk_profile"]
      .every((key) => typeof item[key] === "string" && stableId.test(item[key])) &&
    typeof item.display_name === "string" &&
    typeof item.vendor_name === "string" &&
    Array.isArray(item.capability_ids) && item.capability_ids.length > 0 &&
    item.capability_ids.every((capability) => typeof capability === "string" && stableId.test(capability)) &&
    Array.isArray(item.capability_classes) &&
    item.capability_classes.every((capabilityClass) => capabilityClass === "C0" || capabilityClass === "C1") &&
    typeof item.canonical_digest === "string" && digest.test(item.canonical_digest) &&
    item.trusted_bundled === true && item.development_only === true &&
    item.catalog_evidence_only === true && item.target_authority_granted === false &&
    item.credential_authority_granted === false && item.capability_authority_granted === false &&
    item.network_authority_granted === false && item.runtime_authority_granted === false &&
    item.execution_authorized === false && item.deployment_approved === false &&
    item.infrastructure_mutation_performed === false;
}

function isInstanceResult(value: unknown): value is BundledConnectorInstanceResult {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return ["record_id", "organization_id", "environment_id", "connector_id", "release_version", "instance_id", "instance_key"]
    .every((key) => typeof item[key] === "string" && stableId.test(item[key])) &&
    typeof item.display_name === "string" && item.instance_state === "disabled_unconfigured" &&
    typeof item.purpose === "string" && typeof item.created_at === "string" &&
    typeof item.canonical_digest === "string" && digest.test(item.canonical_digest) &&
    item.eligible_for_configuration_governance === true && item.target_configured === false &&
    item.credentials_resolved === false && item.connector_enabled === false &&
    item.runtime_trust_granted === false && item.execution_authorized === false &&
    item.deployment_approved === false && item.infrastructure_mutation_performed === false &&
    typeof item.reused === "boolean";
}

export async function getBundledConnectorCatalog(): Promise<BundledConnectorDescriptor[]> {
  const response = await apiFetch("/api/v1/connectors/catalog", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Bundled MCP catalog failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!Array.isArray(data) || !data.every(isDescriptor)) {
    throw new Error("Bundled MCP catalog returned unsafe records");
  }
  return data;
}

export async function createBundledConnectorInstance(input: {
  descriptor: BundledConnectorDescriptor;
  instanceKey: string;
  displayName: string;
  purpose: string;
}): Promise<BundledConnectorInstanceResult> {
  const response = await apiFetch(
    `/api/v1/connectors/catalog/${encodeURIComponent(input.descriptor.catalog_item_id)}/instances`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `bundled-connector-instance.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.bundled-connector-instance-input.v1",
        catalog_item_digest: input.descriptor.canonical_digest,
        instance_key: input.instanceKey.trim().toLowerCase(),
        display_name: input.displayName.trim(),
        purpose: input.purpose.trim(),
        acknowledged_instance_is_disabled_and_grants_no_authority: true,
      }),
    },
  );
  if (!response.ok) throw new ApiRequestError("Bundled MCP creation failed", response.status);
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!isInstanceResult(data) || data.connector_id !== input.descriptor.connector_id) {
    throw new Error("Bundled MCP creation returned an unsafe instance");
  }
  return data;
}
