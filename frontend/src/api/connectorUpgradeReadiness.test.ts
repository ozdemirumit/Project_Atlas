import { describe, expect, it } from "vitest";

import {
  isConnectorUpgradeEvidenceReceipt,
  isConnectorUpgradeEvidenceReceiptVerification,
  isConnectorUpgradeEvidenceSigningKeyTrustInventory,
  isConnectorUpgradeHandoffReadiness,
  isConnectorUpgradeSignedEvidenceReceipt,
  isConnectorUpgradeSignedEvidenceReceiptVerification,
} from "./connectorUpgradeReadiness";

const required = [
  "connector.upgrade.handoff.approval-current",
  "connector.upgrade.handoff.itsm-change-current",
  "connector.upgrade.handoff.maintenance-window-current",
  "connector.upgrade.handoff.audit-readiness-evidence-current",
];

const assessment = {
  assessment_id: "connector-upgrade-handoff-readiness.test",
  schema_version: "atlas.connector-upgrade-handoff-readiness.v5",
  source_record_id: "connector-instance-record.test",
  source_record_version: 1,
  instance_id: "connector-instance.test",
  connector_id: "connector.test",
  request_id: "connector-upgrade-approval-request.test",
  request_digest: "1".repeat(64),
  decision_id: "connector-upgrade-approval-decision.test",
  decision_digest: "2".repeat(64),
  revalidation_id: "connector-upgrade-approval-revalidation.test",
  revalidation_digest: "3".repeat(64),
  plan_id: "connector-upgrade-plan.test",
  plan_digest: "4".repeat(64),
  organization_id: "org.test",
  environment_id: "env.test",
  assessed_by: "subject.test",
  applicability_policy_id: "connector-upgrade-handoff-evidence-applicability.default",
  applicability_policy_version: "v2026.08.12.1",
  applicability_policy_digest: "5".repeat(64),
  audit_readiness_evidence_id: null,
  audit_readiness_evidence_digest: null,
  itsm_change_evidence_id: null,
  itsm_change_evidence_digest: null,
  maintenance_window_evidence_id: null,
  maintenance_window_evidence_digest: null,
  required_check_ids: required,
  satisfied_check_ids: [required[0]],
  not_applicable_check_ids: ["connector.upgrade.handoff.target-binding-current"],
  blocker_ids: [
    "connector.upgrade.handoff.blocked.itsm-change-missing",
    "connector.upgrade.handoff.blocked.maintenance-window-missing",
    "connector.upgrade.handoff.blocked.audit-readiness-evidence-missing",
  ],
  assessed_at: "2026-08-12T00:41:00Z",
  evidence_valid_until: "2026-08-12T01:00:00Z",
  canonical_digest: "6".repeat(64),
  assessment_state: "blocked",
  approval_current: true,
  revalidation_current: true,
  audit_readiness_evidence_current: false,
  itsm_change_evidence_current: false,
  maintenance_window_evidence_current: false,
  handoff_ready: false,
  handoff_artifact_issued: false,
  approval_consumed: false,
  target_contacted: false,
  package_rebound: false,
  configuration_changed: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

describe("connector upgrade handoff readiness validation", () => {
  it("accepts disjoint policy-bound evidence classifications", () => {
    expect(isConnectorUpgradeHandoffReadiness(assessment)).toBe(true);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      audit_readiness_evidence_id: "connector-upgrade-audit-readiness-evidence.test",
      audit_readiness_evidence_digest: "7".repeat(64),
      audit_readiness_evidence_current: true,
      satisfied_check_ids: [required[0], required[3]],
      blocker_ids: assessment.blocker_ids.slice(0, 2),
    })).toBe(true);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      audit_readiness_evidence_id: "connector-upgrade-audit-readiness-evidence.test",
      audit_readiness_evidence_digest: "7".repeat(64),
      audit_readiness_evidence_current: true,
      itsm_change_evidence_id: "connector-upgrade-itsm-change-evidence.test",
      itsm_change_evidence_digest: "8".repeat(64),
      itsm_change_evidence_current: true,
      maintenance_window_evidence_id: "connector-upgrade-maintenance-window-evidence.test",
      maintenance_window_evidence_digest: "9".repeat(64),
      maintenance_window_evidence_current: true,
      satisfied_check_ids: required,
      blocker_ids: [],
      assessment_state: "evidence_complete",
    })).toBe(true);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      itsm_change_evidence_id: "connector-upgrade-itsm-change-evidence.test",
      itsm_change_evidence_digest: "8".repeat(64),
      itsm_change_evidence_current: true,
      satisfied_check_ids: [required[0], required[1]],
      blocker_ids: assessment.blocker_ids.slice(1),
    })).toBe(true);
  });

  it("fails closed for overlapping, duplicate or incomplete classifications", () => {
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      not_applicable_check_ids: [required[0]],
    })).toBe(false);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      itsm_change_evidence_id: "connector-upgrade-itsm-change-evidence.test",
      itsm_change_evidence_digest: "8".repeat(64),
      itsm_change_evidence_current: true,
    })).toBe(false);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      audit_readiness_evidence_id: "connector-upgrade-audit-readiness-evidence.test",
      audit_readiness_evidence_digest: "7".repeat(64),
      audit_readiness_evidence_current: true,
    })).toBe(false);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      blocker_ids: [assessment.blocker_ids[0], assessment.blocker_ids[0], assessment.blocker_ids[2]],
    })).toBe(false);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      blocker_ids: assessment.blocker_ids.slice(1),
    })).toBe(false);
    expect(isConnectorUpgradeHandoffReadiness({
      ...assessment,
      blocker_ids: [
        ...assessment.blocker_ids.slice(0, 2),
        "connector.upgrade.handoff.blocked.unrelated-evidence-missing",
      ],
    })).toBe(false);
  });
});

describe("connector upgrade signing-key trust validation", () => {
  const inventory = {
    schema_version: "atlas.connector-upgrade-signing-key-trust-inventory.v1",
    organization_id: "organization.test",
    environment_id: "environment.test",
    provider_class: "provider.nonproduction-hmac",
    provider_state: "available",
    generated_at: "2026-08-12T12:00:00Z",
    keys: [{
      key_id: "key.connector-upgrade-evidence.test",
      key_version: "version.1",
      signer_profile_id: "signer-profile.nonproduction-hmac",
      signer_workload_id: "workload.connector-upgrade-evidence-signer",
      algorithm: "algorithm.hmac-sha256-nonproduction",
      configured_state: "active",
      effective_state: "active",
      not_before: "2026-08-01T00:00:00Z",
      expires_at: "2030-01-01T00:00:00Z",
      signing_eligible: true,
      verification_trusted: true,
      reason_codes: ["connector.upgrade.signing-key-trust.active"],
    }],
    canonical_digest: "a".repeat(64),
    provider_available: true,
    production_approved: false,
    key_management_authorized: false,
    signing_authorized: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
  };

  it("accepts exact read-only metadata and rejects authority or key material", () => {
    expect(isConnectorUpgradeEvidenceSigningKeyTrustInventory(inventory)).toBe(true);
    expect(isConnectorUpgradeEvidenceSigningKeyTrustInventory({
      ...inventory,
      key_management_authorized: true,
    })).toBe(false);
    expect(isConnectorUpgradeEvidenceSigningKeyTrustInventory({
      ...inventory,
      keys: [{ ...inventory.keys[0], key_material: "unsafe" }],
    })).toBe(false);
    expect(isConnectorUpgradeEvidenceSigningKeyTrustInventory({
      ...inventory,
      provider_state: "unavailable",
      provider_available: false,
      keys: [],
    })).toBe(true);
    expect(isConnectorUpgradeEvidenceSigningKeyTrustInventory({
      ...inventory,
      keys: [{
        ...inventory.keys[0],
        effective_state: "expired",
        signing_eligible: false,
        verification_trusted: true,
        reason_codes: ["connector.upgrade.signing-key-trust.expired"],
      }],
    })).toBe(true);
  });
});

describe("connector upgrade evidence receipt validation", () => {
  const receipt = {
    receipt_id: "connector-upgrade-evidence-receipt.test",
    schema_version: "atlas.connector-upgrade-evidence-receipt.v1",
    version: 1,
    assessment_id: assessment.assessment_id,
    assessment_digest: assessment.canonical_digest,
    request_id: assessment.request_id,
    request_digest: assessment.request_digest,
    decision_id: assessment.decision_id,
    decision_digest: assessment.decision_digest,
    revalidation_id: assessment.revalidation_id,
    revalidation_digest: assessment.revalidation_digest,
    plan_id: assessment.plan_id,
    plan_digest: assessment.plan_digest,
    organization_id: assessment.organization_id,
    environment_id: assessment.environment_id,
    created_by: assessment.assessed_by,
    audit_readiness_evidence_id: "connector-upgrade-audit-readiness-evidence.test",
    audit_readiness_evidence_digest: "7".repeat(64),
    itsm_change_evidence_id: "connector-upgrade-itsm-change-evidence.test",
    itsm_change_evidence_digest: "8".repeat(64),
    maintenance_window_evidence_id: "connector-upgrade-maintenance-window-evidence.test",
    maintenance_window_evidence_digest: "9".repeat(64),
    required_check_ids: required,
    satisfied_check_ids: required,
    not_applicable_check_ids: assessment.not_applicable_check_ids,
    created_at: assessment.assessed_at,
    valid_until: assessment.evidence_valid_until,
    canonical_digest: "a".repeat(64),
    evidence_receipt_only: true,
    runtime_acceptable: false,
    approval_consumed: false,
    handoff_ready: false,
    handoff_artifact_issued: false,
    target_contacted: false,
    package_rebound: false,
    configuration_changed: false,
    execution_authorized: false,
    infrastructure_mutation_performed: false,
  };

  it("accepts a complete non-executable receipt and rejects authority-bearing variants", () => {
    expect(isConnectorUpgradeEvidenceReceipt(receipt)).toBe(true);
    expect(isConnectorUpgradeEvidenceReceipt({ ...receipt, runtime_acceptable: true })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceipt({
      ...receipt,
      satisfied_check_ids: required.slice(1),
    })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceipt({ ...receipt, token: "unsafe" })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceipt({ ...receipt, note: "unexpected" })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceipt({
      ...receipt,
      valid_until: receipt.created_at,
    })).toBe(false);
  });

  it("keeps integrity, current state and authenticity claims separate", () => {
    const verification = {
      verification_id: "connector-upgrade-evidence-verification.test",
      schema_version: "atlas.connector-upgrade-evidence-receipt-verification.v1",
      receipt_id: receipt.receipt_id,
      receipt_digest: receipt.canonical_digest,
      request_id: receipt.request_id,
      organization_id: receipt.organization_id,
      environment_id: receipt.environment_id,
      verified_by: "subject.receipt-auditor",
      verified_at: "2026-08-12T00:45:00Z",
      receipt_valid_until: receipt.valid_until,
      verification_state: "current",
      reason_codes: ["connector.upgrade.evidence-receipt.current"],
      canonical_digest: "b".repeat(64),
      integrity_valid: true,
      current_state_compared: true,
      current_state_matches: true,
      receipt_expired: false,
      authenticity_proven: false,
      evidence_receipt_only: true,
      approval_consumed: false,
      handoff_ready: false,
      handoff_artifact_issued: false,
      target_contacted: false,
      package_rebound: false,
      configuration_changed: false,
      execution_authorized: false,
      infrastructure_mutation_performed: false,
    };
    expect(isConnectorUpgradeEvidenceReceiptVerification(verification)).toBe(true);
    expect(isConnectorUpgradeEvidenceReceiptVerification({
      ...verification,
      authenticity_proven: true,
    })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceiptVerification({
      ...verification,
      current_state_matches: false,
    })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceiptVerification({
      ...verification,
      note: "unexpected",
    })).toBe(false);
    expect(isConnectorUpgradeEvidenceReceiptVerification({
      ...verification,
      verification_state: "expired",
      current_state_compared: false,
      current_state_matches: false,
      receipt_expired: true,
    })).toBe(true);
  });

  it("validates signed origin evidence without accepting operational authority", () => {
    const signed = {
      signed_receipt_id: "connector-upgrade-signed-evidence-receipt.test",
      schema_version: "atlas.connector-upgrade-signed-evidence-receipt.v1",
      version: 1,
      receipt,
      signature: {
        key_id: "key.connector-upgrade-evidence.test",
        key_version: "version.1",
        signer_profile_id: "signer-profile.nonproduction-hmac",
        signer_workload_id: "workload.connector-upgrade-evidence-signer",
        algorithm: "algorithm.hmac-sha256-nonproduction",
        signed_payload_digest: "c".repeat(64),
        signature_value: "A".repeat(43),
        signature_digest: "d".repeat(64),
        issued_at: "2026-08-12T00:42:00Z",
        expires_at: "2026-08-12T00:52:00Z",
      },
      organization_id: receipt.organization_id,
      environment_id: receipt.environment_id,
      request_id: receipt.request_id,
      canonical_digest: "e".repeat(64),
      evidence_receipt_only: true,
      authenticity_claimed: true,
      runtime_acceptable: false,
      approval_consumed: false,
      handoff_ready: false,
      handoff_artifact_issued: false,
      target_contacted: false,
      package_rebound: false,
      configuration_changed: false,
      execution_authorized: false,
      infrastructure_mutation_performed: false,
    };
    expect(isConnectorUpgradeSignedEvidenceReceipt(signed)).toBe(true);
    expect(isConnectorUpgradeSignedEvidenceReceipt({ ...signed, private_key: "unsafe" })).toBe(false);
    expect(isConnectorUpgradeSignedEvidenceReceipt({ ...signed, execution_authorized: true }))
      .toBe(false);

    const verification = {
      verification_id: "connector-upgrade-signed-evidence-verification.test",
      schema_version: "atlas.connector-upgrade-signed-evidence-receipt-verification.v1",
      signed_receipt_id: signed.signed_receipt_id,
      signed_receipt_digest: signed.canonical_digest,
      receipt_id: receipt.receipt_id,
      receipt_digest: receipt.canonical_digest,
      request_id: receipt.request_id,
      organization_id: receipt.organization_id,
      environment_id: receipt.environment_id,
      verified_by: "subject.authenticity-auditor",
      verified_at: "2026-08-12T00:45:00Z",
      key_id: signed.signature.key_id,
      key_version: signed.signature.key_version,
      signer_workload_id: signed.signature.signer_workload_id,
      algorithm: signed.signature.algorithm,
      authenticity_state: "authentic",
      receipt_verification_state: "current",
      reason_codes: ["connector.upgrade.signed-evidence-receipt.authentic"],
      canonical_digest: "f".repeat(64),
      integrity_valid: true,
      authenticity_proven: true,
      current_state_matches: true,
      evidence_receipt_only: true,
      approval_consumed: false,
      handoff_ready: false,
      handoff_artifact_issued: false,
      target_contacted: false,
      package_rebound: false,
      configuration_changed: false,
      execution_authorized: false,
      infrastructure_mutation_performed: false,
    };
    expect(isConnectorUpgradeSignedEvidenceReceiptVerification(verification)).toBe(true);
    expect(isConnectorUpgradeSignedEvidenceReceiptVerification({
      ...verification,
      authenticity_proven: false,
    })).toBe(false);
    expect(isConnectorUpgradeSignedEvidenceReceiptVerification({
      ...verification,
      receipt_verification_state: "stale",
    })).toBe(false);
  });
});
