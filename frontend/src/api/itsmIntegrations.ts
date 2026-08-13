import { ApiRequestError, apiFetch } from "./client";

export type ItsmProviderFamily = "service_now" | "jira_service_management" | "generic_rest";
export type ItsmLifecycle = "active" | "retired";
export type ItsmReadinessState = "ready_for_sandbox" | "blocked";
export type ItsmWriteSemantics = "append_only" | "reference_only";

export type ItsmFieldMapping = {
  source_field: string;
  provider_field: string;
  write_semantics: ItsmWriteSemantics;
};

export type ItsmReadinessCheck = {
  check_id: string;
  state: "satisfied" | "blocked";
  reason_code: string;
};

export type ItsmIntegrationProfile = {
  profile_id: string;
  schema_version: "atlas.itsm-integration-profile.v1";
  version: number;
  profile_key: string;
  display_name: string;
  provider_family: ItsmProviderFamily;
  instance_reference: string;
  owner_id: string;
  purpose: string;
  endpoint_origin: string;
  trust_boundary_reference: string;
  credential_reference_configured: boolean;
  classification_ceiling: "public" | "internal" | "confidential" | "restricted";
  allowed_operations: Array<"append_analysis" | "create_incident_draft">;
  mapping_version: number;
  field_mappings: ItsmFieldMapping[];
  sandbox_validation_reference: string | null;
  sandbox_validation_digest: string | null;
  audit_profile_id: string;
  lifecycle: ItsmLifecycle;
  readiness: {
    state: ItsmReadinessState;
    checks: ItsmReadinessCheck[];
    assessed_at: string;
    canonical_digest: string;
    dispatch_authorized: false;
    external_record_mutation_authorized: false;
    workflow_approved: false;
    execution_authorized: false;
  };
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  retired_by: string | null;
  retired_at: string | null;
  retirement_reason: string | null;
  canonical_digest: string;
  reused: boolean;
};

export type ItsmIntegrationInventory = {
  profiles: ItsmIntegrationProfile[];
  durable: boolean;
  truncated: boolean;
};

const providerFamilies = new Set<ItsmProviderFamily>([
  "service_now",
  "jira_service_management",
  "generic_rest",
]);

function isProfile(value: unknown): value is ItsmIntegrationProfile {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  const readiness = record.readiness as Record<string, unknown> | undefined;
  return (
    record.schema_version === "atlas.itsm-integration-profile.v1" &&
    typeof record.profile_id === "string" &&
    typeof record.profile_key === "string" &&
    providerFamilies.has(record.provider_family as ItsmProviderFamily) &&
    (record.lifecycle === "active" || record.lifecycle === "retired") &&
    record.credential_reference_configured === true &&
    Array.isArray(record.field_mappings) &&
    Boolean(readiness) &&
    Array.isArray(readiness?.checks) &&
    (readiness?.state === "blocked" || readiness?.state === "ready_for_sandbox") &&
    readiness?.dispatch_authorized === false &&
    readiness.external_record_mutation_authorized === false &&
    readiness.workflow_approved === false &&
    readiness.execution_authorized === false &&
    !("secret_reference_id" in record || "create_idempotency_key" in record)
  );
}

function readProfileResponse(value: unknown): ItsmIntegrationProfile {
  if (!value || typeof value !== "object" || !("data" in value) || !isProfile(value.data)) {
    throw new ApiRequestError("ITSM integration response was unsafe", 500);
  }
  return value.data;
}

export async function getItsmIntegrationProfiles(
  lifecycle: ItsmLifecycle | "all",
): Promise<ItsmIntegrationInventory> {
  const parameters = new URLSearchParams({ limit: "100" });
  if (lifecycle !== "all") parameters.set("lifecycle", lifecycle);
  const response = await apiFetch(`/api/v1/itsm/integrations?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("ITSM profile inventory failed", response.status);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload)) {
    throw new ApiRequestError("ITSM profile inventory was malformed", response.status);
  }
  const data = payload.data as Record<string, unknown>;
  if (
    !Array.isArray(data.profiles) ||
    !data.profiles.every(isProfile) ||
    typeof data.durable !== "boolean" ||
    typeof data.truncated !== "boolean"
  ) {
    throw new ApiRequestError("ITSM profile inventory was unsafe", response.status);
  }
  return data as ItsmIntegrationInventory;
}

export type CreateItsmIntegrationInput = {
  profileKey: string;
  displayName: string;
  providerFamily: ItsmProviderFamily;
  instanceReference: string;
  ownerId: string;
  purpose: string;
  endpointOrigin: string;
  trustBoundaryReference: string;
  credentialReferenceId: string;
  auditProfileId: string;
  sandboxValidationReference: string;
  sandboxValidationDigest: string;
};

export async function createItsmIntegrationProfile(
  input: CreateItsmIntegrationInput,
): Promise<ItsmIntegrationProfile> {
  const sandboxReference = input.sandboxValidationReference.trim();
  const response = await apiFetch("/api/v1/itsm/integrations", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `itsm-profile-create.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.itsm-integration-profile-create-input.v1",
      profile_key: input.profileKey.trim().toLowerCase(),
      display_name: input.displayName.trim(),
      provider_family: input.providerFamily,
      instance_reference: input.instanceReference.trim().toLowerCase(),
      owner_id: input.ownerId.trim().toLowerCase(),
      purpose: input.purpose.trim(),
      endpoint_origin: input.endpointOrigin.trim().replace(/\/$/, ""),
      trust_boundary_reference: input.trustBoundaryReference.trim().toLowerCase(),
      secret_reference_id: input.credentialReferenceId.trim().toLowerCase(),
      classification_ceiling: "internal",
      allowed_operations: ["append_analysis"],
      mapping_version: 1,
      field_mappings: [
        { source_field: "work_notes", provider_field: "work_notes", write_semantics: "append_only" },
        { source_field: "u_atlas_report_reference", provider_field: "u_atlas_report_reference", write_semantics: "reference_only" },
        { source_field: "u_atlas_review_state", provider_field: "u_atlas_review_state", write_semantics: "reference_only" },
      ],
      sandbox_validation_reference: sandboxReference || null,
      sandbox_validation_digest: sandboxReference
        ? input.sandboxValidationDigest.trim().toLowerCase()
        : null,
      audit_profile_id: input.auditProfileId.trim().toLowerCase(),
      acknowledged_configuration_only: true,
    }),
  });
  if (!response.ok) throw new ApiRequestError("ITSM profile creation failed", response.status);
  return readProfileResponse(await response.json());
}

export async function retireItsmIntegrationProfile(input: {
  profile: ItsmIntegrationProfile;
  reason: string;
}): Promise<ItsmIntegrationProfile> {
  const response = await apiFetch(
    `/api/v1/itsm/integrations/${encodeURIComponent(input.profile.profile_id)}/retirements`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `itsm-profile-retire.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.itsm-integration-profile-retirement-input.v1",
        expected_version: input.profile.version,
        reason: input.reason.trim(),
        acknowledged_history_preserved_and_dispatch_absent: true,
      }),
    },
  );
  if (!response.ok) throw new ApiRequestError("ITSM profile retirement failed", response.status);
  return readProfileResponse(await response.json());
}
