import { apiFetch } from "./client";
import type { McpBuilderCandidateHandoff } from "./mcpBuilder";

export type ConnectorPackageAcquisition = {
  acquisition_id: string;
  schema_version: "atlas.connector-package-acquisition.v1";
  version: 1;
  state: "quarantined";
  source_type: "mcp_builder_handoff";
  source_handoff_id: string;
  source_handoff_digest: string;
  source_project_id: string;
  source_custodied_by: string;
  organization_id: string;
  environment_id: string;
  acquired_by: string;
  acquisition_profile: "atlas.connector-acquisition.builder-handoff.v1";
  archive_contract_version: "mcp-builder-candidate-zip.v1";
  package_filename: string;
  package_digest: string;
  package_size_bytes: number;
  publisher_identity: "unattested.generated";
  signature_state: "unsigned";
  attestation_state: "unattested";
  capabilities: Array<{
    capability_id: string;
    capability_class: "C0" | "C1";
    required_permission: string;
    supported_product_versions: string[];
  }>;
  limitations: string[];
  canonical_digest: string;
  acquired_at: string;
  package_acquired: true;
  integrity_verified: true;
  package_signed: false;
  publisher_attested: false;
  registry_validation_completed: false;
  connector_registered: false;
  connector_approved: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSafeAcquisition(
  value: unknown,
): value is { data: ConnectorPackageAcquisition } {
  if (!isRecord(value) || !isRecord(value.data)) return false;
  const acquisition = value.data;
  const capabilities: unknown[] = Array.isArray(acquisition.capabilities)
    ? acquisition.capabilities
    : [];
  const noAuthority = [
    acquisition.package_signed,
    acquisition.publisher_attested,
    acquisition.registry_validation_completed,
    acquisition.connector_registered,
    acquisition.connector_approved,
    acquisition.connector_installed,
    acquisition.connector_enabled,
    acquisition.target_configured,
    acquisition.credentials_resolved,
    acquisition.runtime_trust_granted,
    acquisition.execution_authorized,
    acquisition.deployment_approved,
    acquisition.infrastructure_mutation_performed,
  ];
  return (
    acquisition.schema_version === "atlas.connector-package-acquisition.v1" &&
    acquisition.version === 1 &&
    acquisition.state === "quarantined" &&
    acquisition.source_type === "mcp_builder_handoff" &&
    acquisition.acquisition_profile === "atlas.connector-acquisition.builder-handoff.v1" &&
    acquisition.archive_contract_version === "mcp-builder-candidate-zip.v1" &&
    acquisition.publisher_identity === "unattested.generated" &&
    acquisition.signature_state === "unsigned" &&
    acquisition.attestation_state === "unattested" &&
    acquisition.package_acquired === true &&
    acquisition.integrity_verified === true &&
    acquisition.acquired_by !== acquisition.source_custodied_by &&
    typeof acquisition.package_digest === "string" &&
    acquisition.package_digest.length === 64 &&
    typeof acquisition.canonical_digest === "string" &&
    acquisition.canonical_digest.length === 64 &&
    typeof acquisition.package_size_bytes === "number" &&
    acquisition.package_size_bytes > 0 &&
    acquisition.package_size_bytes <= 25_000_000 &&
    Array.isArray(acquisition.limitations) &&
    acquisition.limitations.length > 0 &&
    capabilities.length > 0 &&
    capabilities.every(
      (item) =>
        isRecord(item) &&
        typeof item.capability_id === "string" &&
        (item.capability_class === "C0" || item.capability_class === "C1") &&
        typeof item.required_permission === "string" &&
        Array.isArray(item.supported_product_versions),
    ) &&
    noAuthority.every((flag) => flag === false)
  );
}

export async function acquireConnectorPackage(handoff: McpBuilderCandidateHandoff) {
  const response = await apiFetch("/api/v1/connectors/package-acquisitions", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-acquisition.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-acquisition-request.v1",
      source_handoff_id: handoff.handoff_id,
      source_handoff_digest: handoff.canonical_digest,
      package_digest: handoff.package_digest,
      acquisition_profile: "atlas.connector-acquisition.builder-handoff.v1",
      acknowledged_unsigned_unattested_quarantine: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package acquisition failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSafeAcquisition(payload)) {
    throw new Error("Connector registry returned unsafe package acquisition evidence");
  }
  const acquisition = payload.data;
  if (
    acquisition.source_handoff_id !== handoff.handoff_id ||
    acquisition.source_handoff_digest !== handoff.canonical_digest ||
    acquisition.source_project_id !== handoff.project_id ||
    acquisition.source_custodied_by !== handoff.custodied_by ||
    acquisition.organization_id !== handoff.organization_id ||
    acquisition.environment_id !== handoff.environment_id ||
    acquisition.package_filename !== handoff.package_filename ||
    acquisition.package_digest !== handoff.package_digest ||
    acquisition.package_size_bytes !== handoff.package_size_bytes ||
    acquisition.capabilities.length !== handoff.capabilities.length ||
    acquisition.capabilities.some(
      (item, index) => item.capability_id !== handoff.capabilities[index]?.candidate_id,
    )
  ) {
    throw new Error("Connector acquisition does not match the exact Builder handoff");
  }
  return payload;
}

