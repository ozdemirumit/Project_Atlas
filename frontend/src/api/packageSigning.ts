import { apiFetch } from "./client";
import type { ConnectorPublisherAttestation } from "./publisherAttestations";

export type ConnectorPackageSigningReceipt = {
  receipt_id: string;
  schema_version: "atlas.connector-package-signing-receipt.v1";
  version: 1;
  envelope: {
    envelope_id: string;
    schema_version: "atlas.connector-package-signing-envelope.v1";
    source_attestation_report_id: string;
    source_attestation_report_digest: string;
    package_digest: string;
    publisher_id: string;
    connector_id: string;
    release_version: string;
    provenance_digest: string;
    signing_policy_id: string;
    signing_policy_digest: string;
    signer_profile_id: string;
    requested_by: string;
    canonical_digest: string;
  };
  signature: {
    signer_profile_id: string;
    signer_workload_id: string;
    key_id: string;
    algorithm: string;
    envelope_digest: string;
    signature_digest: string;
    issued_at: string;
    expires_at: string;
    signature_verified: boolean;
  };
  organization_id: string;
  environment_id: string;
  requested_by: string;
  signing_policy_id: string;
  signing_policy_digest: string;
  signed_at: string;
  canonical_digest: string;
  publisher_attested: true;
  package_signed: true;
  eligible_for_registry_governance: true;
  promotion_blocked: false;
  reused: boolean;
  connector_registered: false;
  connector_installed: false;
  connector_enabled: false;
  target_configured: false;
  credentials_resolved: false;
  runtime_trust_granted: false;
  execution_authorized: false;
  deployment_approved: false;
  infrastructure_mutation_performed: false;
};

function isSigningResponse(value: unknown): value is { data: ConnectorPackageSigningReceipt } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  const signature = record.signature;
  return (
    record.schema_version === "atlas.connector-package-signing-receipt.v1" &&
    record.version === 1 &&
    typeof record.receipt_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    record.publisher_attested === true &&
    record.package_signed === true &&
    record.eligible_for_registry_governance === true &&
    record.promotion_blocked === false &&
    record.connector_registered === false &&
    record.connector_installed === false &&
    record.connector_enabled === false &&
    record.target_configured === false &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false &&
    !!signature &&
    typeof signature === "object" &&
    !("signature_value" in signature) &&
    typeof (signature as Record<string, unknown>).signature_digest === "string"
  );
}

export async function createConnectorPackageSigningReceipt(input: {
  attestation: ConnectorPublisherAttestation;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { attestation, policyId, policyDigest, purpose } = input;
  if (
    !attestation.publisher_attested ||
    !attestation.eligible_for_package_signing_governance ||
    attestation.promotion_blocked ||
    attestation.outcome !== "verified"
  ) {
    throw new Error("A current verified publisher attestation is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("An exact signing policy and bounded purpose are required");
  }
  const response = await apiFetch("/api/v1/connectors/package-signing-receipts", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-package-signing.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-package-signing-input.v1",
      source_attestation_report_id: attestation.report_id,
      source_attestation_report_digest: attestation.canonical_digest,
      package_digest: attestation.package_digest,
      signing_policy_id: policyId,
      signing_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_signing_grants_no_runtime_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector package signing failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isSigningResponse(payload)) {
    throw new Error("Connector registry returned an unsafe signing receipt");
  }
  if (
    payload.data.envelope.source_attestation_report_id !== attestation.report_id ||
    payload.data.envelope.source_attestation_report_digest !== attestation.canonical_digest ||
    payload.data.envelope.package_digest !== attestation.package_digest ||
    payload.data.signing_policy_id !== policyId ||
    payload.data.signing_policy_digest !== policyDigest
  ) {
    throw new Error("Signing receipt does not match the exact attested package");
  }
  return payload;
}
