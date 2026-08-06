import type { ConnectorPackageApprovalRecord } from "./connectors";
import { apiFetch } from "./client";

export type ConnectorPublisherAttestation = {
  report_id: string;
  schema_version: "atlas.connector-publisher-attestation.v1";
  version: 1;
  source_approval_request_id: string;
  source_approval_request_digest: string;
  source_approval_decision_id: string;
  source_approval_decision_digest: string;
  organization_id: string;
  environment_id: string;
  verified_by: string;
  purpose: string;
  package_digest: string;
  publisher_claim_id: string;
  publisher_claim_digest: string;
  publisher_id: string;
  publisher_display_name: string;
  connector_id: string;
  release_version: string;
  provenance_digest: string;
  support_contact_ref: string;
  support_expires_at: string;
  claim_issued_by: string;
  attestation_policy_id: string;
  attestation_policy_digest: string;
  attestation_policy_version: string;
  check_codes: string[];
  outcome: "verified" | "rejected";
  reason_codes: string[];
  verified_at: string;
  canonical_digest: string;
  publisher_attested: boolean;
  eligible_for_package_signing_governance: boolean;
  promotion_blocked: boolean;
  reused: boolean;
  package_signed: false;
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

function isAttestationResponse(
  value: unknown,
): value is { data: ConnectorPublisherAttestation } {
  if (!value || typeof value !== "object" || !("data" in value)) return false;
  const data = (value as { data?: unknown }).data;
  if (!data || typeof data !== "object") return false;
  const record = data as Record<string, unknown>;
  return (
    record.schema_version === "atlas.connector-publisher-attestation.v1" &&
    record.version === 1 &&
    typeof record.report_id === "string" &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    (record.outcome === "verified" || record.outcome === "rejected") &&
    typeof record.publisher_attested === "boolean" &&
    record.package_signed === false &&
    record.connector_registered === false &&
    record.connector_installed === false &&
    record.connector_enabled === false &&
    record.target_configured === false &&
    record.credentials_resolved === false &&
    record.runtime_trust_granted === false &&
    record.execution_authorized === false &&
    record.deployment_approved === false &&
    record.infrastructure_mutation_performed === false
  );
}

export async function createConnectorPublisherAttestation(input: {
  approval: ConnectorPackageApprovalRecord;
  claimId: string;
  claimDigest: string;
  policyId: string;
  policyDigest: string;
  purpose: string;
}) {
  const { approval, claimId, claimDigest, policyId, policyDigest, purpose } = input;
  if (
    !approval.approval_valid ||
    !approval.eligible_for_publisher_governance ||
    approval.promotion_blocked ||
    approval.decision?.outcome !== "approve"
  ) {
    throw new Error("An exact valid package approval is required");
  }
  if (
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(claimId) ||
    !/^[a-f0-9]{64}$/.test(claimDigest) ||
    !/^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) ||
    !/^[a-f0-9]{64}$/.test(policyDigest) ||
    purpose.trim().length < 20
  ) {
    throw new Error("Exact publisher claim, policy, and purpose are required");
  }
  const response = await apiFetch("/api/v1/connectors/publisher-attestations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `connector-publisher-attestation.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.connector-publisher-attestation-input.v1",
      source_approval_request_id: approval.request.request_id,
      source_approval_request_digest: approval.request.canonical_digest,
      package_digest: approval.request.package_digest,
      publisher_claim_id: claimId,
      publisher_claim_digest: claimDigest,
      attestation_policy_id: policyId,
      attestation_policy_digest: policyDigest,
      purpose: purpose.trim(),
      acknowledged_attestation_grants_no_lifecycle_authority: true,
    }),
  });
  if (!response.ok) {
    throw new Error(`Connector publisher attestation failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isAttestationResponse(payload)) {
    throw new Error("Connector registry returned an unsafe publisher attestation");
  }
  if (
    payload.data.source_approval_request_id !== approval.request.request_id ||
    payload.data.source_approval_request_digest !== approval.request.canonical_digest ||
    payload.data.package_digest !== approval.request.package_digest ||
    payload.data.publisher_claim_id !== claimId ||
    payload.data.publisher_claim_digest !== claimDigest ||
    payload.data.attestation_policy_id !== policyId ||
    payload.data.attestation_policy_digest !== policyDigest
  ) {
    throw new Error("Publisher attestation does not match the exact approved package");
  }
  return payload;
}
