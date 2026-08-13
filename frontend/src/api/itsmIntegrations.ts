import { ApiRequestError, apiFetch } from "./client";

export type ItsmProviderFamily = "service_now" | "jira_service_management" | "generic_rest";
export type ItsmLifecycle = "active" | "retired";
export type ItsmReadinessState = "ready_for_sandbox" | "blocked";
export type ItsmWriteSemantics = "append_only" | "reference_only";
export type ItsmSandboxConformanceState =
  | "conformant"
  | "unavailable"
  | "profile_blocked"
  | "trust_failed"
  | "credential_failed"
  | "permission_failed"
  | "mapping_failed"
  | "round_trip_failed";

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

export type ItsmSandboxConformanceAssessment = {
  assessment_id: string;
  schema_version: "atlas.itsm-sandbox-conformance-assessment.v1";
  version: 1;
  organization_id: string;
  environment_id: string;
  site_id: string;
  profile_id: string;
  profile_version: number;
  profile_digest: string;
  mapping_version: number;
  assessed_by: string;
  adapter_id: string;
  adapter_version: string;
  adapter_production_eligible: boolean;
  diagnostic_contract_version: string;
  challenge_digest: string;
  observed_at: string;
  valid_until: string;
  state: ItsmSandboxConformanceState;
  reason_codes: string[];
  canonical_digest: string;
  diagnostic_only: true;
  sandbox_conformant: boolean;
  production_ready: false;
  dispatch_authorized: false;
  external_record_mutation_authorized: false;
  workflow_approved: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

export type ItsmSandboxOnboardingReadiness = {
  schema_version: "atlas.itsm-sandbox-onboarding-readiness.v3";
  version: 1;
  organization_id: string;
  environment_id: string;
  site_id: string;
  profile_id: string;
  profile_version: number;
  profile_digest: string;
  mapping_version: number;
  conformance_assessment_id: string | null;
  conformance_assessment_digest: string | null;
  adapter_id: string | null;
  adapter_version: string | null;
  policy_id: string;
  policy_version: number;
  policy_digest: string;
  policy_issuer: string;
  policy_expires_at: string;
  policy_provenance_id: string;
  policy_provenance_digest: string;
  policy_signing_key_id: string;
  policy_signing_key_version: string;
  policy_signature_algorithm: string;
  policy_signed_at: string;
  policy_verified_at: string;
  assessed_at: string;
  evidence_observed_at: string | null;
  evidence_valid_until: string | null;
  state: "ready" | "blocked";
  requirements: Array<{
    requirement_id: string;
    state: "satisfied" | "blocked";
    reason_code: string;
  }>;
  canonical_digest: string;
  sandbox_onboarding_ready: boolean;
  production_ready: false;
  dispatch_authorized: false;
  external_record_mutation_authorized: false;
  workflow_approved: false;
  execution_authorized: false;
  infrastructure_mutation_performed: false;
};

const providerFamilies = new Set<ItsmProviderFamily>([
  "service_now",
  "jira_service_management",
  "generic_rest",
]);
const sandboxStates = new Set<ItsmSandboxConformanceState>([
  "conformant",
  "unavailable",
  "profile_blocked",
  "trust_failed",
  "credential_failed",
  "permission_failed",
  "mapping_failed",
  "round_trip_failed",
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

export function isSandboxConformance(
  value: unknown,
): value is ItsmSandboxConformanceAssessment {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    record.schema_version === "atlas.itsm-sandbox-conformance-assessment.v1" &&
    typeof record.assessment_id === "string" &&
    typeof record.profile_id === "string" &&
    typeof record.profile_version === "number" &&
    typeof record.profile_digest === "string" &&
    typeof record.adapter_id === "string" &&
    typeof record.valid_until === "string" &&
    sandboxStates.has(record.state as ItsmSandboxConformanceState) &&
    Array.isArray(record.reason_codes) &&
    record.diagnostic_only === true &&
    typeof record.sandbox_conformant === "boolean" &&
    record.production_ready === false &&
    record.dispatch_authorized === false &&
    record.external_record_mutation_authorized === false &&
    record.workflow_approved === false &&
    record.execution_authorized === false &&
    record.infrastructure_mutation_performed === false &&
    !("idempotency_key" in record || "request_fingerprint" in record || "secret_reference_id" in record)
  );
}

function readSandboxConformanceResponse(value: unknown): ItsmSandboxConformanceAssessment {
  if (
    !value ||
    typeof value !== "object" ||
    !("data" in value) ||
    !isSandboxConformance(value.data)
  ) {
    throw new ApiRequestError("ITSM sandbox conformance response was unsafe", 500);
  }
  return value.data;
}

export function isSandboxOnboardingReadiness(
  value: unknown,
): value is ItsmSandboxOnboardingReadiness {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  const requirements = record.requirements;
  const forbidden = [
    "endpoint_origin",
    "secret_reference_id",
    "credential",
    "token",
    "request_payload",
    "provider_operation",
    "approval_assertion",
    "policy_payload",
    "policy_override",
    "signature_value",
    "verification_key",
    "key_material",
    "trust_decision",
  ];
  return (
    record.schema_version === "atlas.itsm-sandbox-onboarding-readiness.v3" &&
    record.version === 1 &&
    typeof record.profile_id === "string" &&
    typeof record.profile_version === "number" &&
    typeof record.profile_digest === "string" &&
    typeof record.mapping_version === "number" &&
    typeof record.policy_id === "string" &&
    Number.isInteger(record.policy_version) &&
    (record.policy_version as number) > 0 &&
    typeof record.policy_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.policy_digest) &&
    typeof record.policy_issuer === "string" &&
    typeof record.policy_expires_at === "string" &&
    !Number.isNaN(Date.parse(record.policy_expires_at)) &&
    typeof record.policy_provenance_id === "string" &&
    typeof record.policy_provenance_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.policy_provenance_digest) &&
    typeof record.policy_signing_key_id === "string" &&
    typeof record.policy_signing_key_version === "string" &&
    typeof record.policy_signature_algorithm === "string" &&
    typeof record.policy_signed_at === "string" &&
    !Number.isNaN(Date.parse(record.policy_signed_at)) &&
    typeof record.policy_verified_at === "string" &&
    !Number.isNaN(Date.parse(record.policy_verified_at)) &&
    (record.state === "ready" || record.state === "blocked") &&
    Array.isArray(requirements) &&
    requirements.length === 12 &&
    requirements.every(
      (item) =>
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as Record<string, unknown>).requirement_id === "string" &&
        ((item as Record<string, unknown>).state === "satisfied" ||
          (item as Record<string, unknown>).state === "blocked") &&
        typeof (item as Record<string, unknown>).reason_code === "string",
    ) &&
    typeof record.sandbox_onboarding_ready === "boolean" &&
    record.sandbox_onboarding_ready === (record.state === "ready") &&
    record.production_ready === false &&
    record.dispatch_authorized === false &&
    record.external_record_mutation_authorized === false &&
    record.workflow_approved === false &&
    record.execution_authorized === false &&
    record.infrastructure_mutation_performed === false &&
    forbidden.every((field) => !(field in record))
  );
}

function readSandboxOnboardingReadinessResponse(
  value: unknown,
): ItsmSandboxOnboardingReadiness {
  if (
    !value ||
    typeof value !== "object" ||
    !("data" in value) ||
    !isSandboxOnboardingReadiness(value.data)
  ) {
    throw new ApiRequestError("ITSM sandbox onboarding response was unsafe", 500);
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

export async function assessItsmSandboxConformance(
  profile: ItsmIntegrationProfile,
): Promise<ItsmSandboxConformanceAssessment> {
  const response = await apiFetch(
    `/api/v1/itsm/integrations/${encodeURIComponent(profile.profile_id)}/sandbox-conformance-assessments`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `itsm-sandbox-conformance.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.itsm-sandbox-conformance-input.v1",
        expected_profile_version: profile.version,
        acknowledged_diagnostic_only_and_no_dispatch: true,
      }),
    },
  );
  if (!response.ok) {
    throw new ApiRequestError("ITSM sandbox conformance assessment failed", response.status);
  }
  return readSandboxConformanceResponse(await response.json());
}

export async function getLatestItsmSandboxConformance(
  profileId: string,
): Promise<ItsmSandboxConformanceAssessment | null> {
  const response = await apiFetch(
    `/api/v1/itsm/integrations/${encodeURIComponent(profileId)}/sandbox-conformance-assessments/latest`,
    { headers: { Accept: "application/json" } },
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new ApiRequestError("ITSM sandbox conformance lookup failed", response.status);
  }
  return readSandboxConformanceResponse(await response.json());
}

export async function getItsmSandboxOnboardingReadiness(
  profileId: string,
): Promise<ItsmSandboxOnboardingReadiness> {
  const response = await apiFetch(
    `/api/v1/itsm/integrations/${encodeURIComponent(profileId)}/sandbox-onboarding-readiness`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError("ITSM sandbox onboarding readiness failed", response.status);
  }
  return readSandboxOnboardingReadinessResponse(await response.json());
}
