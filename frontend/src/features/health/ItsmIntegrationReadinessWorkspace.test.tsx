import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  assessItsmSandboxConformance,
  createItsmIntegrationProfile,
  getLatestItsmSandboxConformance,
  getItsmIntegrationProfiles,
  getItsmSandboxOnboardingReadiness,
  retireItsmIntegrationProfile,
  type ItsmIntegrationProfile,
  type ItsmSandboxConformanceAssessment,
  type ItsmSandboxOnboardingReadiness,
} from "../../api/itsmIntegrations";
import ItsmIntegrationReadinessWorkspace from "./ItsmIntegrationReadinessWorkspace";

vi.mock("../../api/itsmIntegrations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/itsmIntegrations")>()),
  createItsmIntegrationProfile: vi.fn(),
  assessItsmSandboxConformance: vi.fn(),
  getLatestItsmSandboxConformance: vi.fn(),
  getItsmIntegrationProfiles: vi.fn(),
  getItsmSandboxOnboardingReadiness: vi.fn(),
  retireItsmIntegrationProfile: vi.fn(),
}));

const profile: ItsmIntegrationProfile = {
  profile_id: "itsm-integration.test-01",
  schema_version: "atlas.itsm-integration-profile.v1",
  version: 1,
  profile_key: "itsm.sandbox.primary",
  display_name: "Primary ITSM sandbox",
  provider_family: "generic_rest",
  instance_reference: "itsm-instance.sandbox.primary",
  owner_id: "team.service-management",
  purpose: "Validate governed report handoff mappings in an isolated ITSM sandbox.",
  endpoint_origin: "https://itsm-sandbox.example.invalid",
  trust_boundary_reference: "trust-boundary.itsm.sandbox",
  credential_reference_configured: true,
  classification_ceiling: "internal",
  allowed_operations: ["append_analysis"],
  mapping_version: 1,
  field_mappings: [
    { source_field: "work_notes", provider_field: "work_notes", write_semantics: "append_only" },
    { source_field: "u_atlas_report_reference", provider_field: "u_atlas_report_reference", write_semantics: "reference_only" },
    { source_field: "u_atlas_review_state", provider_field: "u_atlas_review_state", write_semantics: "reference_only" },
  ],
  sandbox_validation_reference: null,
  sandbox_validation_digest: null,
  audit_profile_id: "audit-profile.itsm.sandbox",
  lifecycle: "active",
  readiness: {
    state: "blocked",
    checks: [
      { check_id: "itsm.readiness.ownership", state: "satisfied", reason_code: "itsm.readiness.satisfied" },
      { check_id: "itsm.readiness.network-trust", state: "satisfied", reason_code: "itsm.readiness.satisfied" },
      { check_id: "itsm.readiness.credential-reference", state: "satisfied", reason_code: "itsm.readiness.satisfied" },
      { check_id: "itsm.readiness.mapping", state: "satisfied", reason_code: "itsm.readiness.satisfied" },
      { check_id: "itsm.readiness.sandbox-validation", state: "blocked", reason_code: "itsm.readiness.sandbox_validation_missing" },
      { check_id: "itsm.readiness.audit", state: "satisfied", reason_code: "itsm.readiness.satisfied" },
    ],
    assessed_at: "2026-08-13T05:00:00Z",
    canonical_digest: "b".repeat(64),
    dispatch_authorized: false,
    external_record_mutation_authorized: false,
    workflow_approved: false,
    execution_authorized: false,
  },
  created_by: "subject.test",
  created_at: "2026-08-13T05:00:00Z",
  updated_by: "subject.test",
  updated_at: "2026-08-13T05:00:00Z",
  retired_by: null,
  retired_at: null,
  retirement_reason: null,
  canonical_digest: "a".repeat(64),
  reused: false,
};

const conformance: ItsmSandboxConformanceAssessment = {
  assessment_id: "itsm-sandbox-conformance.test-01",
  schema_version: "atlas.itsm-sandbox-conformance-assessment.v1",
  version: 1,
  organization_id: "organization.development",
  environment_id: "environment.test",
  site_id: "site.local",
  profile_id: profile.profile_id,
  profile_version: profile.version,
  profile_digest: profile.canonical_digest,
  mapping_version: profile.mapping_version,
  assessed_by: "subject.test",
  adapter_id: "adapter.itsm.synthetic-no-network",
  adapter_version: "version.1",
  adapter_production_eligible: false,
  diagnostic_contract_version: "contract.itsm-sandbox-conformance.v1",
  challenge_digest: "c".repeat(64),
  observed_at: "2026-08-13T05:00:00Z",
  valid_until: "2026-08-13T05:10:00Z",
  state: "conformant",
  reason_codes: ["itsm.sandbox-conformance.synthetic_contract_conformant"],
  canonical_digest: "d".repeat(64),
  diagnostic_only: true,
  sandbox_conformant: true,
  production_ready: false,
  dispatch_authorized: false,
  external_record_mutation_authorized: false,
  workflow_approved: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

const onboarding: ItsmSandboxOnboardingReadiness = {
  schema_version: "atlas.itsm-sandbox-onboarding-readiness.v3",
  version: 1,
  organization_id: "organization.development",
  environment_id: "environment.test",
  site_id: "site.local",
  profile_id: profile.profile_id,
  profile_version: 1,
  profile_digest: profile.canonical_digest,
  mapping_version: 1,
  conformance_assessment_id: conformance.assessment_id,
  conformance_assessment_digest: conformance.canonical_digest,
  adapter_id: conformance.adapter_id,
  adapter_version: conformance.adapter_version,
  policy_id: "policy.itsm-sandbox-onboarding.development",
  policy_version: 1,
  policy_digest: "f".repeat(64),
  policy_issuer: "issuer.atlas-development",
  policy_expires_at: "2026-09-12T05:00:00Z",
  policy_provenance_id: "provenance.policy.itsm-sandbox-onboarding.development.1",
  policy_provenance_digest: "1".repeat(64),
  policy_signing_key_id: "signing-key.itsm-policy.development",
  policy_signing_key_version: "version.1",
  policy_signature_algorithm: "algorithm.hmac-sha256-nonproduction",
  policy_signed_at: "2026-08-13T05:00:00Z",
  policy_verified_at: "2026-08-13T05:00:00Z",
  assessed_at: "2026-08-13T05:00:00Z",
  evidence_observed_at: "2026-08-13T05:00:00Z",
  evidence_valid_until: "2026-08-13T05:10:00Z",
  state: "blocked",
  requirements: [
    ["profile-current", "satisfied", "satisfied"],
    ["conformance-current", "satisfied", "satisfied"],
    ["adapter-registered", "satisfied", "satisfied"],
    ["adapter-sandbox-approved", "blocked", "adapter_not_onboarding_eligible"],
    ["workload-identity", "satisfied", "satisfied"],
    ["credential-ownership", "satisfied", "satisfied"],
    ["network-trust", "satisfied", "satisfied"],
    ["mapping-change-control", "satisfied", "satisfied"],
    ["rate-backpressure", "satisfied", "satisfied"],
    ["audit-routing", "satisfied", "satisfied"],
    ["availability-recovery", "satisfied", "satisfied"],
    ["owner-approvals", "blocked", "owner_approvals_missing"],
  ].map(([id, state, reason]) => ({
    requirement_id: `itsm.sandbox-onboarding.${id}`,
    state: state as "satisfied" | "blocked",
    reason_code: `itsm.sandbox-onboarding.${reason}`,
  })),
  canonical_digest: "e".repeat(64),
  sandbox_onboarding_ready: false,
  production_ready: false,
  dispatch_authorized: false,
  external_record_mutation_authorized: false,
  workflow_approved: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

function renderWorkspace(governedSessionAvailable = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ItsmIntegrationReadinessWorkspace governedSessionAvailable={governedSessionAvailable} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getItsmIntegrationProfiles).mockResolvedValue({
    profiles: [profile],
    durable: true,
    truncated: false,
  });
  vi.mocked(createItsmIntegrationProfile).mockResolvedValue(profile);
  vi.mocked(getLatestItsmSandboxConformance).mockResolvedValue(null);
  vi.mocked(getItsmSandboxOnboardingReadiness).mockResolvedValue(onboarding);
  vi.mocked(assessItsmSandboxConformance).mockResolvedValue(conformance);
  vi.mocked(retireItsmIntegrationProfile).mockResolvedValue({
    ...profile,
    version: 2,
    lifecycle: "retired",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ItsmIntegrationReadinessWorkspace", () => {
  it("shows provider-neutral readiness, allowlisted mappings, and no dispatch controls", async () => {
    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Sandbox integration profiles" })).toBeVisible();
    expect(await screen.findByText("Primary ITSM sandbox")).toBeVisible();
    expect(screen.getByText("Sandbox evidence")).toBeVisible();
    expect(screen.getByText("sandbox validation missing")).toBeVisible();
    expect(screen.getByText("Configured reference")).toBeVisible();
    expect(screen.getByText("Append only")).toBeVisible();
    expect(screen.queryByText(/secret\.itsm/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /dispatch|create ticket|test endpoint/i })).toBeNull();
    expect(await screen.findByRole("heading", { name: "Deployment readiness dossier" })).toBeVisible();
    expect(screen.getByText("Fail closed")).toBeVisible();
    expect(screen.getByText("Sandbox adapter approval")).toBeVisible();
    expect(screen.getByText("adapter not onboarding eligible")).toBeVisible();
    expect(screen.getByText("Security and deployment approvals")).toBeVisible();
    expect(screen.getByText("policy.itsm-sandbox-onboarding.development / v1")).toBeVisible();
    expect(screen.getByText("issuer.atlas-development")).toBeVisible();
    expect(screen.getByText("provenance.policy.itsm-sandbox-onboarding.development.1")).toBeVisible();
    expect(screen.getByText("signing-key.itsm-policy.development / version.1")).toBeVisible();
    expect(screen.getByText("f".repeat(20) + "...")).toBeVisible();
    expect(screen.queryByRole("button", { name: /upload policy|edit policy|approve policy|sign policy|rotate key|revoke key|trust key|configure adapter/i })).toBeNull();
  });

  it("keeps profile lifecycle changes behind a governed browser session", async () => {
    renderWorkspace(false);

    expect(await screen.findByText(/Signed browser session required for profile lifecycle changes/i)).toBeVisible();
    expect(await screen.findByText("Primary ITSM sandbox")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add profile" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Retire Primary ITSM sandbox" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Assess sandbox" })).toBeDisabled();
  });

  it("requires the configuration-only acknowledgement before registration", async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Add profile" }));

    fireEvent.change(screen.getByLabelText("Profile key"), { target: { value: "itsm.sandbox.secondary" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Secondary sandbox" } });
    fireEvent.change(screen.getByLabelText("Instance reference"), { target: { value: "itsm-instance.sandbox.secondary" } });
    fireEvent.change(screen.getByLabelText("Accountable owner"), { target: { value: "team.service-management" } });
    fireEvent.change(screen.getByLabelText("Trust boundary"), { target: { value: "trust-boundary.itsm.sandbox" } });
    fireEvent.change(screen.getByLabelText("HTTPS endpoint origin"), { target: { value: "https://itsm-sandbox.example.invalid" } });
    fireEvent.change(screen.getByLabelText("Credential broker reference"), { target: { value: "secret.itsm.sandbox.writer" } });
    fireEvent.change(screen.getByLabelText("Audit profile"), { target: { value: "audit-profile.itsm.sandbox" } });
    fireEvent.change(screen.getByLabelText("Configuration purpose"), { target: { value: "Validate governed report handoff mappings in an isolated ITSM sandbox." } });

    const submit = screen.getByRole("button", { name: "Register profile" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/This stores configuration only/i));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(createItsmIntegrationProfile).toHaveBeenCalledTimes(1));
  });

  it("runs only the acknowledged profile-bound diagnostic and presents no authority", async () => {
    renderWorkspace();
    const assess = await screen.findByRole("button", { name: "Assess sandbox" });
    fireEvent.click(assess);

    const run = screen.getByRole("button", { name: "Run diagnostic" });
    expect(run).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/diagnostic evidence only/i));
    expect(run).toBeEnabled();
    fireEvent.click(run);

    await waitFor(() => expect(assessItsmSandboxConformance).toHaveBeenCalledTimes(1));
    expect(vi.mocked(assessItsmSandboxConformance).mock.calls[0]?.[0]).toEqual(profile);
    expect(await screen.findByText("conformant")).toBeVisible();
    expect(screen.getAllByText("adapter.itsm.synthetic-no-network")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /dispatch|create ticket|execute/i })).toBeNull();
  });
});
