import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createItsmIntegrationProfile,
  getItsmIntegrationProfiles,
  retireItsmIntegrationProfile,
  type ItsmIntegrationProfile,
} from "../../api/itsmIntegrations";
import ItsmIntegrationReadinessWorkspace from "./ItsmIntegrationReadinessWorkspace";

vi.mock("../../api/itsmIntegrations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/itsmIntegrations")>()),
  createItsmIntegrationProfile: vi.fn(),
  getItsmIntegrationProfiles: vi.fn(),
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
  });

  it("keeps profile lifecycle changes behind a governed browser session", async () => {
    renderWorkspace(false);

    expect(await screen.findByText(/Signed browser session required for profile lifecycle changes/i)).toBeVisible();
    expect(await screen.findByText("Primary ITSM sandbox")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add profile" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Retire Primary ITSM sandbox" })).toBeDisabled();
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
});
