import { describe, expect, it } from "vitest";

import { isSandboxConformance } from "./itsmIntegrations";

function assessment(overrides: Record<string, unknown> = {}) {
  return {
    assessment_id: "itsm-sandbox-conformance.test-01",
    schema_version: "atlas.itsm-sandbox-conformance-assessment.v1",
    version: 1,
    organization_id: "organization.development",
    environment_id: "environment.test",
    site_id: "site.local",
    profile_id: "itsm-integration.test-01",
    profile_version: 1,
    profile_digest: "a".repeat(64),
    mapping_version: 1,
    assessed_by: "subject.test",
    adapter_id: "adapter.itsm.synthetic-no-network",
    adapter_version: "version.1",
    adapter_production_eligible: false,
    diagnostic_contract_version: "contract.itsm-sandbox-conformance.v1",
    challenge_digest: "b".repeat(64),
    observed_at: "2026-08-13T05:00:00Z",
    valid_until: "2026-08-13T05:10:00Z",
    state: "conformant",
    reason_codes: ["itsm.sandbox-conformance.synthetic_contract_conformant"],
    canonical_digest: "c".repeat(64),
    diagnostic_only: true,
    sandbox_conformant: true,
    production_ready: false,
    dispatch_authorized: false,
    external_record_mutation_authorized: false,
    workflow_approved: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
    ...overrides,
  };
}

describe("ITSM sandbox conformance runtime contract", () => {
  it("accepts minimized diagnostic evidence", () => {
    expect(isSandboxConformance(assessment())).toBe(true);
  });

  it("rejects authority escalation and sensitive request metadata", () => {
    expect(isSandboxConformance(assessment({ dispatch_authorized: true }))).toBe(false);
    expect(isSandboxConformance(assessment({ secret_reference_id: "secret.itsm.writer" }))).toBe(
      false,
    );
    expect(isSandboxConformance(assessment({ request_fingerprint: "d".repeat(64) }))).toBe(false);
  });
});
