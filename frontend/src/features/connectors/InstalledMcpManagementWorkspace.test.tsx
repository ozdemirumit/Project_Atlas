import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorCapabilityEnablement,
  getConnectorCapabilityEnablementOptions,
  getConnectorCapabilityEnablements,
} from "../../api/capabilityEnablements";
import { getConnectorConfigurationValidations } from "../../api/configurationValidations";
import { getConnectorCredentialAssignments } from "../../api/credentialAssignments";
import {
  createConnectorInstance,
  getConnectorInstanceCreationPolicies,
  getConnectorInstances,
  retireConnectorInstance,
  type ConnectorInstanceCreationPolicy,
} from "../../api/connectorInstances";
import {
  assessConnectorUpgradeSigningProviderConformance,
  createConnectorUpgradeApprovalRequest,
  createConnectorUpgradeChangeContextDraft,
  createConnectorUpgradeEvidenceReceipt,
  createConnectorUpgradeSignedEvidenceReceipt,
  decideConnectorUpgradeApproval,
  getConnectorUpgradeApprovalRecord,
  getConnectorUpgradeHandoffReadiness,
  getConnectorUpgradeEvidenceSigningKeyTrustInventory,
  getConnectorUpgradeSigningProviderOnboardingReadiness,
  getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  getLatestConnectorUpgradeSigningProviderConformance,
  getLatestConnectorUpgradeChangeContextDraft,
  getLatestConnectorUpgradeApprovalRevalidation,
  getConnectorUpgradePlan,
  getConnectorUpgradeReadiness,
  revalidateConnectorUpgradeApproval,
  verifyConnectorUpgradeEvidenceReceipt,
  verifyConnectorUpgradeSignedEvidenceReceipt,
  type ConnectorUpgradeApprovalRecord,
  type ConnectorUpgradeApprovalRequest,
  type ConnectorUpgradeApprovalRevalidation,
  type ConnectorUpgradeHandoffReadiness,
  type ConnectorUpgradeChangeContextDraft,
  type ConnectorUpgradeEvidenceReceipt,
  type ConnectorUpgradeEvidenceReceiptVerification,
  type ConnectorUpgradeEvidenceSigningKeyTrustInventory,
  type ConnectorUpgradeSignedEvidenceReceipt,
  type ConnectorUpgradeSignedEvidenceReceiptVerification,
  type ConnectorUpgradeSigningProviderConformanceAssessment,
  type ConnectorUpgradeSigningProviderOnboardingReadiness,
  type ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  type ConnectorUpgradePlan,
  type ConnectorUpgradeReadiness,
} from "../../api/connectorUpgradeReadiness";
import { getConnectorPackageInstallations } from "../../api/packageInstallations";
import {
  createConnectorRuntimeTrustGrant,
  getConnectorRuntimeTrustGrantOptions,
  getConnectorRuntimeTrustGrants,
} from "../../api/runtimeTrustGrants";
import {
  getConnectorTargetConfigurations,
  type ConnectorTargetConfigurationBinding,
} from "../../api/targetConfigurations";
import InstalledMcpManagementWorkspace from "./InstalledMcpManagementWorkspace";
import { configurationValidation } from "./testConfigurationValidationFixture";
import {
  capabilityEnablement,
  capabilityEnablementInventoryItem,
  capabilityEnablementOption,
} from "./testCapabilityEnablementFixture";
import { credentialAssignment } from "./testCredentialAssignmentFixture";
import { connectorInstanceRecord as instance } from "./testInstanceFixture";
import { installationReceipt as installation } from "./testInstallationFixture";
import {
  runtimeTrustGrantInventoryItem as runtimeTrustGrant,
  runtimeTrustGrantOption,
} from "./testRuntimeTrustFixture";

const policy: ConnectorInstanceCreationPolicy = {
  policy_id: "connector-instance-creation-policy.development",
  schema_version: "atlas.connector-instance-creation-policy.v1",
  version: 1,
  organization_id: installation.organization_id,
  environment_id: installation.environment_id,
  policy_version: "version.1.0",
  allowed_sdk_profiles: [installation.sdk_profile],
  allowed_capability_classes: ["C0", "C1"],
  required_initial_state: "disabled_unconfigured",
  maximum_instance_key_length: 64,
  maximum_display_name_length: 120,
  expires_at: "2030-01-01T00:00:00Z",
  canonical_digest: "f".repeat(64),
};

const configuredBinding = {
  binding_id: "connector-target-configuration-binding.test",
  schema_version: "atlas.connector-target-configuration-binding.v1",
  version: 1,
  source_instance_record_id: instance.record_id,
  source_instance_record_digest: instance.canonical_digest,
  organization_id: instance.organization_id,
  environment_id: instance.environment_id,
  package_digest: instance.package_digest,
  connector_id: instance.connector_id,
  release_version: instance.release_version,
  manifest_digest: instance.manifest_digest,
  instance_id: instance.instance_id,
  instance_key: instance.instance_key,
  display_name: instance.display_name,
  owner_id: instance.owner_id,
  target_profile_id: "connector-target-profile.development-storage",
  target_profile_digest: "a".repeat(64),
  site_id: "site.development-primary",
  target_type: "storage-array",
  target_product: "Synthetic Storage",
  target_version: "version.1.0",
  configuration_policy_id: "connector-target-configuration-policy.development",
  configuration_policy_digest: "b".repeat(64),
  configuration_policy_version: "version.1.0",
  configuration_version: 1,
  instance_state: "disabled_target_configured",
  bound_by: "subject.connector-independent-target-configurator",
  purpose: "Bind signed target configuration without runtime authority.",
  bound_at: "2026-08-20T12:00:00Z",
  canonical_digest: "c".repeat(64),
  package_installed: true,
  instance_created: true,
  target_configured: true,
  eligible_for_credential_governance: true,
  promotion_blocked: false,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorTargetConfigurationBinding;

const signingKeyTrustInventory: ConnectorUpgradeEvidenceSigningKeyTrustInventory = {
  schema_version: "atlas.connector-upgrade-signing-key-trust-inventory.v1",
  organization_id: installation.organization_id,
  environment_id: installation.environment_id,
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
  canonical_digest: "0".repeat(64),
  provider_available: true,
  production_approved: false,
  key_management_authorized: false,
  signing_authorized: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const signingProviderConformance: ConnectorUpgradeSigningProviderConformanceAssessment = {
  assessment_id: "connector-upgrade-signing-provider-conformance.test",
  schema_version: "atlas.connector-upgrade-signing-provider-conformance-assessment.v1",
  version: 1,
  organization_id: installation.organization_id,
  environment_id: installation.environment_id,
  assessed_by: "subject.connector-operator",
  provider_class: "provider.nonproduction-hmac",
  production_approved: false,
  key_id: "key.connector-upgrade-evidence.test",
  key_version: "version.1",
  algorithm: "algorithm.hmac-sha256-nonproduction",
  challenge_digest: "1".repeat(64),
  policy_id: "connector-upgrade-signing-provider-conformance.default",
  policy_version: "v2026.08.12.1",
  observed_at: "2026-08-12T12:00:00Z",
  valid_until: "2026-08-12T12:05:00Z",
  state: "conformant",
  reason_codes: ["connector.upgrade.signing-provider-conformance.conformant"],
  request_fingerprint: "2".repeat(64),
  canonical_digest: "3".repeat(64),
  diagnostic_only: true,
  signing_provider_conformant: true,
  key_management_authorized: false,
  receipt_signing_authorized: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

const signingProviderOnboarding: ConnectorUpgradeSigningProviderOnboardingReadiness = {
  dossier_id: "connector-upgrade-signing-provider-onboarding.test",
  schema_version: "atlas.connector-upgrade-signing-provider-onboarding-readiness.v1",
  version: 1,
  organization_id: installation.organization_id,
  environment_id: installation.environment_id,
  provider_class: "provider.nonproduction-hmac",
  key_id: "key.connector-upgrade-evidence.test",
  key_version: "version.1",
  algorithm: "algorithm.hmac-sha256-nonproduction",
  provider_trust_digest: "4".repeat(64),
  conformance_assessment_id: signingProviderConformance.assessment_id,
  conformance_digest: signingProviderConformance.canonical_digest,
  policy_id: "connector-upgrade-signing-provider-onboarding.default",
  policy_version: "v2026.08.12.1",
  policy_digest: "7".repeat(64),
  policy_issued_by: "subject.security-architecture",
  policy_expires_at: "2026-08-13T12:01:00Z",
  policy_attestation_id: "connector-upgrade-onboarding-policy-attestation.test",
  policy_attestation_digest: "8".repeat(64),
  policy_trust_key_id: "key.connector-upgrade-onboarding-policy.test",
  policy_trust_key_version: "version.1",
  policy_trust_algorithm: "algorithm.hmac-sha256-nonproduction",
  evaluated_at: "2026-08-12T12:01:00Z",
  readiness_state: "blocked",
  requirements: [
    {
      requirement_id: "provider-available",
      state: "satisfied",
      reason_code: "connector.upgrade.signing-provider-onboarding.satisfied",
      evidence_reference: `trust-inventory.${"4".repeat(64)}`,
    },
    {
      requirement_id: "provider-production-approved",
      state: "blocked",
      reason_code: (
        "connector.upgrade.signing-provider-onboarding.provider-not-production-approved"
      ),
      evidence_reference: null,
    },
    {
      requirement_id: "security-approval-current",
      state: "blocked",
      reason_code: (
        "connector.upgrade.signing-provider-onboarding.security-approval-evidence-missing"
      ),
      evidence_reference: null,
    },
  ],
  required_external_inputs: [
    "provider-production-approved",
    "security-approval-current",
  ],
  canonical_digest: "6".repeat(64),
  provider_onboarding_ready: false,
  policy_provenance_verified: true,
  evidence_only: true,
  provider_configuration_authorized: false,
  key_management_authorized: false,
  receipt_signing_authorized: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const signingProviderOnboardingProvenance:
ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic = {
  diagnostic_id: "connector-upgrade-onboarding-policy-provenance.test",
  schema_version:
    "atlas.connector-upgrade-signing-provider-onboarding-policy-provenance-diagnostic.v2",
  version: 2,
  organization_id: installation.organization_id,
  environment_id: installation.environment_id,
  evaluated_at: "2026-08-12T12:01:00Z",
  valid_until: "2026-08-13T12:01:00Z",
  state: "verified",
  policy_id: signingProviderOnboarding.policy_id,
  policy_version: signingProviderOnboarding.policy_version,
  policy_digest: signingProviderOnboarding.policy_digest,
  policy_issued_by: signingProviderOnboarding.policy_issued_by,
  attestation_id: signingProviderOnboarding.policy_attestation_id,
  attestation_digest: signingProviderOnboarding.policy_attestation_digest,
  trust_key_id: signingProviderOnboarding.policy_trust_key_id,
  trust_key_version: signingProviderOnboarding.policy_trust_key_version,
  trust_algorithm: signingProviderOnboarding.policy_trust_algorithm,
  trust_key_state: "active",
  checks: [
    "policy-current", "attestation-current", "attestation-binding-valid",
    "trust-key-current", "signature-verified",
  ].map((check_id) => ({
    check_id,
    state: "verified" as const,
    reason_code:
      `connector.upgrade.signing-provider-onboarding-policy-provenance.${check_id}`,
    evidence_reference: "evidence.safe-reference",
    owner_role_id: null,
    evidence_requirement_id: null,
    next_action_id: null,
    external_input_required: false,
  })),
  reason_codes: [],
  canonical_digest: "9".repeat(64),
  provenance_verified: true,
  diagnostic_only: true,
  policy_authoring_authorized: false,
  trust_management_authorized: false,
  provider_configuration_authorized: false,
  key_management_authorized: false,
  receipt_signing_authorized: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const upgradeReadiness: ConnectorUpgradeReadiness = {
  schema_version: "atlas.connector-upgrade-readiness.v1",
  source_record_id: instance.record_id,
  source_record_version: instance.version,
  instance_id: instance.instance_id,
  instance_key: instance.instance_key,
  connector_id: instance.connector_id,
  current_release_version: instance.release_version,
  current_package_digest: instance.package_digest,
  current_manifest_digest: instance.manifest_digest,
  current_receipt_id: instance.source_installation_receipt_id,
  current_receipt_digest: instance.source_installation_receipt_digest,
  target_configured: false,
  candidates: [
    {
      receipt_id: "connector-package-installation-receipt.storage-v2",
      receipt_digest: "a".repeat(64),
      package_digest: "b".repeat(64),
      manifest_digest: "c".repeat(64),
      release_version: "version.2.0.0",
      publisher_id: installation.publisher_id,
      sdk_profile: installation.sdk_profile,
      installed_at: "2026-08-11T18:00:00Z",
      upgrade_class: "major",
      risk_level: "high",
      capability_changes: [{ capability_id: "storage.capacity.read", change_type: "added", current_class: null, candidate_class: "C1", current_permission: null, candidate_permission: "connectors.storage.capacity.read" }],
      target_products_added: [],
      target_products_removed: [],
      network_destinations_added: ["telemetry.storage.example"],
      network_destinations_removed: [],
      configuration_key_delta: 1,
      secret_reference_delta: 1,
      policy_review_required: true,
      configuration_migration_required: true,
      rollback_receipt_id: instance.source_installation_receipt_id,
      rollback_receipt_digest: instance.source_installation_receipt_digest,
      review_eligible: true,
      blockers: [],
      canonical_digest: "d".repeat(64),
      execution_authorized: false,
      infrastructure_mutation_performed: false,
    },
  ],
  generated_at: "2026-08-11T19:00:00Z",
  canonical_digest: "e".repeat(64),
  decision_support_only: true,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const upgradePlan: ConnectorUpgradePlan = {
  plan_id: "connector-upgrade-plan.test",
  schema_version: "atlas.connector-upgrade-plan.v1",
  source_record_id: instance.record_id,
  source_record_version: instance.version,
  instance_id: instance.instance_id,
  connector_id: instance.connector_id,
  current_release_version: instance.release_version,
  current_receipt_id: instance.source_installation_receipt_id,
  current_receipt_digest: instance.source_installation_receipt_digest,
  candidate_release_version: "version.2.0.0",
  candidate_receipt_id: upgradeReadiness.candidates[0]!.receipt_id,
  candidate_receipt_digest: upgradeReadiness.candidates[0]!.receipt_digest,
  readiness_digest: upgradeReadiness.canonical_digest,
  candidate_digest: upgradeReadiness.candidates[0]!.canonical_digest,
  risk_level: "high",
  target_configured: false,
  target_id: null,
  site_id: null,
  target_product: null,
  plan_state: "ready_for_human_review",
  plan_eligible: true,
  prerequisite_ids: ["connector.upgrade.prerequisite.human-approval"],
  steps: ["approval", "precheck", "quiescence", "package_binding", "configuration", "verification", "rollback_gate"].map((phase, index) => ({
    step_id: `connector.upgrade.step.${phase.replaceAll("_", "-")}`,
    sequence: index + 1,
    phase: phase as ConnectorUpgradePlan["steps"][number]["phase"],
    expected_minutes: index === 0 ? 0 : 2,
    requires_service_interruption: false,
    rollback_boundary: index >= 2,
  })),
  validation_check_ids: ["connector.upgrade.verify.runtime-health"],
  stop_condition_ids: ["connector.upgrade.stop.source-drift"],
  rollback_step_ids: ["connector.upgrade.rollback.restore-package-binding"],
  blockers: [],
  unknowns: [],
  estimated_interruption_min_minutes: 0,
  estimated_interruption_max_minutes: 0,
  rollback_window_minutes: 60,
  generated_at: "2026-08-12T00:00:00Z",
  expires_at: "2026-08-12T01:00:00Z",
  canonical_digest: "9".repeat(64),
  approval_required: true,
  decision_support_only: true,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const upgradeApprovalRequest: ConnectorUpgradeApprovalRequest = {
  request_id: "connector-upgrade-approval-request.test",
  schema_version: "atlas.connector-upgrade-approval-request.v1",
  version: 1,
  source_record_id: instance.record_id,
  source_record_version: instance.version,
  instance_id: instance.instance_id,
  connector_id: instance.connector_id,
  plan_id: upgradePlan.plan_id,
  plan_digest: upgradePlan.canonical_digest,
  readiness_digest: upgradePlan.readiness_digest,
  current_release_version: upgradePlan.current_release_version,
  current_receipt_id: upgradePlan.current_receipt_id,
  current_receipt_digest: upgradePlan.current_receipt_digest,
  candidate_release_version: upgradePlan.candidate_release_version,
  candidate_receipt_id: upgradePlan.candidate_receipt_id,
  candidate_receipt_digest: upgradePlan.candidate_receipt_digest,
  candidate_digest: upgradePlan.candidate_digest,
  risk_level: upgradePlan.risk_level,
  organization_id: instance.organization_id,
  environment_id: instance.environment_id,
  requested_by: "subject.connector-operator",
  purpose: "Submit this exact connector upgrade plan for independent human review.",
  approval_policy_id: "connector-upgrade-approval-policy.development",
  approval_policy_digest: "8".repeat(64),
  approval_policy_version: "version.1.0",
  created_at: "2026-08-12T00:00:00Z",
  expires_at: "2026-08-12T02:00:00Z",
  state: "pending",
  canonical_digest: "7".repeat(64),
  separation_of_duties_required: true,
  approval_granted: false,
  decision_recorded: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

const pendingUpgradeApproval: ConnectorUpgradeApprovalRecord = {
  request: upgradeApprovalRequest,
  decision: null,
  state: "pending",
  approval_valid: false,
  approval_granted: false,
  decision_recorded: false,
  separation_of_duties_enforced: true,
  package_rebound: false,
  configuration_changed: false,
  target_contacted: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const approvedUpgradeApproval: ConnectorUpgradeApprovalRecord = {
  ...pendingUpgradeApproval,
  decision: {
    decision_id: "connector-upgrade-approval-decision.test",
    schema_version: "atlas.connector-upgrade-approval-decision.v1",
    version: 1,
    request_id: upgradeApprovalRequest.request_id,
    request_version: 1,
    request_digest: upgradeApprovalRequest.canonical_digest,
    plan_id: upgradePlan.plan_id,
    plan_digest: upgradePlan.canonical_digest,
    outcome: "approve",
    decided_by: "subject.connector-independent-approver",
    rationale: "Approve this exact immutable plan after independent evidence review.",
    organization_id: instance.organization_id,
    environment_id: instance.environment_id,
    approval_policy_id: upgradeApprovalRequest.approval_policy_id,
    approval_policy_digest: upgradeApprovalRequest.approval_policy_digest,
    decided_at: "2026-08-12T00:30:00Z",
    canonical_digest: "6".repeat(64),
    execution_authorized: false,
    infrastructure_mutation_performed: false,
    reused: false,
  },
  state: "approved",
  approval_valid: true,
  approval_granted: true,
  decision_recorded: true,
};

const upgradeApprovalRevalidation: ConnectorUpgradeApprovalRevalidation = {
  revalidation_id: "connector-upgrade-approval-revalidation.test",
  schema_version: "atlas.connector-upgrade-approval-revalidation.v1",
  version: 1,
  source_record_id: instance.record_id,
  source_record_version: instance.version,
  instance_id: instance.instance_id,
  connector_id: instance.connector_id,
  request_id: upgradeApprovalRequest.request_id,
  request_version: 1,
  request_digest: upgradeApprovalRequest.canonical_digest,
  decision_id: approvedUpgradeApproval.decision!.decision_id,
  decision_version: 1,
  decision_digest: approvedUpgradeApproval.decision!.canonical_digest,
  plan_id: upgradePlan.plan_id,
  plan_digest: upgradePlan.canonical_digest,
  readiness_digest: upgradePlan.readiness_digest,
  current_receipt_id: upgradePlan.current_receipt_id,
  current_receipt_digest: upgradePlan.current_receipt_digest,
  candidate_receipt_id: upgradePlan.candidate_receipt_id,
  candidate_receipt_digest: upgradePlan.candidate_receipt_digest,
  approval_policy_id: upgradeApprovalRequest.approval_policy_id,
  approval_policy_version: upgradeApprovalRequest.approval_policy_version,
  approval_policy_digest: upgradeApprovalRequest.approval_policy_digest,
  organization_id: instance.organization_id,
  environment_id: instance.environment_id,
  requester_id: upgradeApprovalRequest.requested_by,
  approver_id: approvedUpgradeApproval.decision!.decided_by,
  revalidated_by: "subject.connector-independent-verifier",
  purpose: "Revalidate the exact approved plan without granting handoff authority.",
  check_ids: [
    "connector.upgrade.revalidation.request-integrity",
    "connector.upgrade.revalidation.decision-integrity",
  ],
  revalidated_at: "2026-08-12T00:40:00Z",
  valid_until: "2026-08-12T01:00:00Z",
  canonical_digest: "5".repeat(64),
  approval_current_at_revalidation: true,
  governance_ready: true,
  handoff_ready: false,
  target_configured: false,
  package_rebound: false,
  configuration_changed: false,
  target_contacted: false,
  handoff_artifact_issued: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
  reused: false,
};

const handoffReadiness: ConnectorUpgradeHandoffReadiness = {
  assessment_id: "connector-upgrade-handoff-readiness.test",
  schema_version: "atlas.connector-upgrade-handoff-readiness.v5",
  source_record_id: instance.record_id,
  source_record_version: instance.version,
  instance_id: instance.instance_id,
  connector_id: instance.connector_id,
  request_id: upgradeApprovalRequest.request_id,
  request_digest: upgradeApprovalRequest.canonical_digest,
  decision_id: approvedUpgradeApproval.decision!.decision_id,
  decision_digest: approvedUpgradeApproval.decision!.canonical_digest,
  revalidation_id: upgradeApprovalRevalidation.revalidation_id,
  revalidation_digest: upgradeApprovalRevalidation.canonical_digest,
  plan_id: upgradePlan.plan_id,
  plan_digest: upgradePlan.canonical_digest,
  organization_id: instance.organization_id,
  environment_id: instance.environment_id,
  assessed_by: "subject.connector-independent-verifier",
  applicability_policy_id: "connector-upgrade-handoff-evidence-applicability.default",
  applicability_policy_version: "v2026.08.12.1",
  applicability_policy_digest: "6".repeat(64),
  audit_readiness_evidence_id: "connector-upgrade-audit-readiness-evidence.test",
  audit_readiness_evidence_digest: "7".repeat(64),
  itsm_change_evidence_id: "connector-upgrade-itsm-change-evidence.test",
  itsm_change_evidence_digest: "8".repeat(64),
  maintenance_window_evidence_id: "connector-upgrade-maintenance-window-evidence.test",
  maintenance_window_evidence_digest: "9".repeat(64),
  required_check_ids: [
    "connector.upgrade.handoff.approval-current",
    "connector.upgrade.handoff.revalidation-current",
    "connector.upgrade.handoff.identity-separation-current",
    "connector.upgrade.handoff.policy-current",
    "connector.upgrade.handoff.plan-lineage-current",
    "connector.upgrade.handoff.prior-execution-absent",
    "connector.upgrade.handoff.audit-readiness-evidence-current",
    "connector.upgrade.handoff.itsm-change-current",
    "connector.upgrade.handoff.maintenance-window-current",
  ],
  satisfied_check_ids: [
    "connector.upgrade.handoff.approval-current",
    "connector.upgrade.handoff.revalidation-current",
    "connector.upgrade.handoff.identity-separation-current",
    "connector.upgrade.handoff.policy-current",
    "connector.upgrade.handoff.plan-lineage-current",
    "connector.upgrade.handoff.prior-execution-absent",
    "connector.upgrade.handoff.audit-readiness-evidence-current",
    "connector.upgrade.handoff.itsm-change-current",
    "connector.upgrade.handoff.maintenance-window-current",
  ],
  not_applicable_check_ids: [
    "connector.upgrade.handoff.target-binding-current",
    "connector.upgrade.handoff.service-impact-evidence-current",
    "connector.upgrade.handoff.runtime-health-evidence-current",
  ],
  blocker_ids: [],
  assessed_at: "2026-08-12T00:41:00Z",
  evidence_valid_until: "2026-08-12T01:00:00Z",
  canonical_digest: "4".repeat(64),
  assessment_state: "evidence_complete",
  approval_current: true,
  revalidation_current: true,
  audit_readiness_evidence_current: true,
  itsm_change_evidence_current: true,
  maintenance_window_evidence_current: true,
  handoff_ready: false,
  handoff_artifact_issued: false,
  approval_consumed: false,
  target_contacted: false,
  package_rebound: false,
  configuration_changed: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
};

const changeContextDraft: ConnectorUpgradeChangeContextDraft = {
  draft_id: "connector-upgrade-change-context-draft.test",
  schema_version: "atlas.connector-upgrade-change-context-draft.v1",
  source_record_id: instance.record_id, source_record_version: instance.version,
  instance_id: instance.instance_id, connector_id: instance.connector_id,
  request_id: upgradeApprovalRequest.request_id,
  request_digest: upgradeApprovalRequest.canonical_digest,
  decision_digest: approvedUpgradeApproval.decision!.canonical_digest,
  revalidation_id: upgradeApprovalRevalidation.revalidation_id,
  revalidation_digest: upgradeApprovalRevalidation.canonical_digest,
  readiness_digest: handoffReadiness.canonical_digest,
  organization_id: instance.organization_id, environment_id: instance.environment_id,
  created_by: "subject.connector-independent-verifier",
  justification: "Prepare this exact connector upgrade for governed ITSM review.",
  proposed_window_start: "2026-08-12T03:00:00Z",
  proposed_window_end: "2026-08-12T04:00:00Z",
  itsm_draft_title: "Review connector upgrade storage.connector for environment.development",
  itsm_draft_digest: "7".repeat(64), created_at: "2026-08-12T00:42:00Z",
  valid_until: "2026-08-12T01:00:00Z", canonical_digest: "8".repeat(64), state: "draft",
  itsm_dispatched: false, window_approved: false, handoff_ready: false,
  handoff_artifact_issued: false, approval_consumed: false, target_contacted: false,
  package_rebound: false, configuration_changed: false, execution_authorized: false,
  infrastructure_mutation_performed: false, reused: false,
};

const evidenceReceipt: ConnectorUpgradeEvidenceReceipt = {
  receipt_id: "connector-upgrade-evidence-receipt.test",
  schema_version: "atlas.connector-upgrade-evidence-receipt.v1",
  version: 1,
  assessment_id: handoffReadiness.assessment_id,
  assessment_digest: handoffReadiness.canonical_digest,
  request_id: handoffReadiness.request_id,
  request_digest: handoffReadiness.request_digest,
  decision_id: handoffReadiness.decision_id,
  decision_digest: handoffReadiness.decision_digest,
  revalidation_id: handoffReadiness.revalidation_id,
  revalidation_digest: handoffReadiness.revalidation_digest,
  plan_id: handoffReadiness.plan_id,
  plan_digest: handoffReadiness.plan_digest,
  organization_id: handoffReadiness.organization_id,
  environment_id: handoffReadiness.environment_id,
  created_by: "subject.connector-independent-verifier",
  audit_readiness_evidence_id: handoffReadiness.audit_readiness_evidence_id!,
  audit_readiness_evidence_digest: handoffReadiness.audit_readiness_evidence_digest!,
  itsm_change_evidence_id: handoffReadiness.itsm_change_evidence_id!,
  itsm_change_evidence_digest: handoffReadiness.itsm_change_evidence_digest!,
  maintenance_window_evidence_id: handoffReadiness.maintenance_window_evidence_id!,
  maintenance_window_evidence_digest: handoffReadiness.maintenance_window_evidence_digest!,
  required_check_ids: handoffReadiness.required_check_ids,
  satisfied_check_ids: handoffReadiness.satisfied_check_ids,
  not_applicable_check_ids: handoffReadiness.not_applicable_check_ids,
  created_at: handoffReadiness.assessed_at,
  valid_until: handoffReadiness.evidence_valid_until,
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

const evidenceReceiptVerification: ConnectorUpgradeEvidenceReceiptVerification = {
  verification_id: "connector-upgrade-evidence-verification.test",
  schema_version: "atlas.connector-upgrade-evidence-receipt-verification.v1",
  receipt_id: evidenceReceipt.receipt_id,
  receipt_digest: evidenceReceipt.canonical_digest,
  request_id: evidenceReceipt.request_id,
  organization_id: evidenceReceipt.organization_id,
  environment_id: evidenceReceipt.environment_id,
  verified_by: "subject.connector-independent-verifier",
  verified_at: "2026-08-12T00:45:00Z",
  receipt_valid_until: evidenceReceipt.valid_until,
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

const signedEvidenceReceipt: ConnectorUpgradeSignedEvidenceReceipt = {
  signed_receipt_id: "connector-upgrade-signed-evidence-receipt.test",
  schema_version: "atlas.connector-upgrade-signed-evidence-receipt.v1",
  version: 1,
  receipt: evidenceReceipt,
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
  organization_id: evidenceReceipt.organization_id,
  environment_id: evidenceReceipt.environment_id,
  request_id: evidenceReceipt.request_id,
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

const signedEvidenceVerification: ConnectorUpgradeSignedEvidenceReceiptVerification = {
  verification_id: "connector-upgrade-signed-evidence-verification.test",
  schema_version: "atlas.connector-upgrade-signed-evidence-receipt-verification.v1",
  signed_receipt_id: signedEvidenceReceipt.signed_receipt_id,
  signed_receipt_digest: signedEvidenceReceipt.canonical_digest,
  receipt_id: evidenceReceipt.receipt_id,
  receipt_digest: evidenceReceipt.canonical_digest,
  request_id: evidenceReceipt.request_id,
  organization_id: evidenceReceipt.organization_id,
  environment_id: evidenceReceipt.environment_id,
  verified_by: "subject.connector-authenticity-auditor",
  verified_at: "2026-08-12T00:45:00Z",
  key_id: signedEvidenceReceipt.signature.key_id,
  key_version: signedEvidenceReceipt.signature.key_version,
  signer_workload_id: signedEvidenceReceipt.signature.signer_workload_id,
  algorithm: "algorithm.hmac-sha256-nonproduction",
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

vi.mock("../../api/connectorInstances", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/connectorInstances")>();
  return {
    ...original,
    createConnectorInstance: vi.fn(),
    getConnectorInstanceCreationPolicies: vi.fn(),
    getConnectorInstances: vi.fn(),
    retireConnectorInstance: vi.fn(),
  };
});

vi.mock("../../api/packageInstallations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/packageInstallations")>();
  return { ...original, getConnectorPackageInstallations: vi.fn() };
});

vi.mock("../../api/targetConfigurations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/targetConfigurations")>();
  return { ...original, getConnectorTargetConfigurations: vi.fn() };
});

vi.mock("../../api/credentialAssignments", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/credentialAssignments")>();
  return { ...original, getConnectorCredentialAssignments: vi.fn() };
});

vi.mock("../../api/configurationValidations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/configurationValidations")>();
  return { ...original, getConnectorConfigurationValidations: vi.fn() };
});

vi.mock("../../api/capabilityEnablements", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/capabilityEnablements")>();
  return {
    ...original,
    createConnectorCapabilityEnablement: vi.fn(),
    getConnectorCapabilityEnablementOptions: vi.fn(),
    getConnectorCapabilityEnablements: vi.fn(),
  };
});

vi.mock("../../api/runtimeTrustGrants", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/runtimeTrustGrants")>();
  return {
    ...original,
    createConnectorRuntimeTrustGrant: vi.fn(),
    getConnectorRuntimeTrustGrantOptions: vi.fn(),
    getConnectorRuntimeTrustGrants: vi.fn(),
  };
});

vi.mock("../../api/connectorUpgradeReadiness", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/connectorUpgradeReadiness")>();
  return {
    ...original,
    createConnectorUpgradeApprovalRequest: vi.fn(),
    decideConnectorUpgradeApproval: vi.fn(),
    getConnectorUpgradeApprovalRecord: vi.fn(),
    getConnectorUpgradeHandoffReadiness: vi.fn(),
    getConnectorUpgradeEvidenceSigningKeyTrustInventory: vi.fn(),
    assessConnectorUpgradeSigningProviderConformance: vi.fn(),
    getLatestConnectorUpgradeSigningProviderConformance: vi.fn(),
    getConnectorUpgradeSigningProviderOnboardingReadiness: vi.fn(),
    getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic: vi.fn(),
    getLatestConnectorUpgradeChangeContextDraft: vi.fn(),
    createConnectorUpgradeChangeContextDraft: vi.fn(),
    createConnectorUpgradeEvidenceReceipt: vi.fn(),
    createConnectorUpgradeSignedEvidenceReceipt: vi.fn(),
    verifyConnectorUpgradeEvidenceReceipt: vi.fn(),
    verifyConnectorUpgradeSignedEvidenceReceipt: vi.fn(),
    getLatestConnectorUpgradeApprovalRevalidation: vi.fn(),
    getConnectorUpgradeReadiness: vi.fn(),
    getConnectorUpgradePlan: vi.fn(),
    revalidateConnectorUpgradeApproval: vi.fn(),
  };
});

function renderWorkspace(
  subjectId = "subject.connector-operator",
  onRequestEnterpriseLogin?: () => void,
  onOpenBuilder?: () => void,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <InstalledMcpManagementWorkspace
        onOpenBuilder={onOpenBuilder}
        onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        subjectId={subjectId}
        organizationId="org.atlas"
        environmentId="env.atlas"
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getConnectorPackageInstallations).mockResolvedValue([installation]);
  vi.mocked(getConnectorInstanceCreationPolicies).mockResolvedValue([policy]);
  vi.mocked(getConnectorInstances).mockResolvedValue([instance]);
  vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([]);
  vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([]);
  vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([]);
  vi.mocked(getConnectorCapabilityEnablements).mockResolvedValue([]);
  vi.mocked(getConnectorCapabilityEnablementOptions).mockResolvedValue([]);
  vi.mocked(createConnectorCapabilityEnablement).mockResolvedValue({
    data: capabilityEnablementInventoryItem,
  });
  vi.mocked(getConnectorRuntimeTrustGrants).mockResolvedValue([]);
  vi.mocked(getConnectorRuntimeTrustGrantOptions).mockResolvedValue([]);
  vi.mocked(createConnectorRuntimeTrustGrant).mockResolvedValue({ data: runtimeTrustGrant });
  vi.mocked(getConnectorUpgradeReadiness).mockResolvedValue(upgradeReadiness);
  vi.mocked(getConnectorUpgradePlan).mockResolvedValue(upgradePlan);
  vi.mocked(getConnectorUpgradeApprovalRecord).mockResolvedValue(null);
  vi.mocked(createConnectorUpgradeApprovalRequest).mockResolvedValue(upgradeApprovalRequest);
  vi.mocked(decideConnectorUpgradeApproval).mockResolvedValue(approvedUpgradeApproval);
  vi.mocked(getLatestConnectorUpgradeApprovalRevalidation).mockResolvedValue(null);
  vi.mocked(getConnectorUpgradeHandoffReadiness).mockResolvedValue(handoffReadiness);
  vi.mocked(getConnectorUpgradeEvidenceSigningKeyTrustInventory).mockResolvedValue(
    signingKeyTrustInventory,
  );
  vi.mocked(getLatestConnectorUpgradeSigningProviderConformance).mockResolvedValue(
    signingProviderConformance,
  );
  vi.mocked(assessConnectorUpgradeSigningProviderConformance).mockResolvedValue(
    signingProviderConformance,
  );
  vi.mocked(getConnectorUpgradeSigningProviderOnboardingReadiness).mockResolvedValue(
    signingProviderOnboarding,
  );
  vi.mocked(
    getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
  ).mockResolvedValue(signingProviderOnboardingProvenance);
  vi.mocked(getLatestConnectorUpgradeChangeContextDraft).mockResolvedValue(null);
  vi.mocked(createConnectorUpgradeChangeContextDraft).mockResolvedValue(changeContextDraft);
  vi.mocked(createConnectorUpgradeEvidenceReceipt).mockResolvedValue(evidenceReceipt);
  vi.mocked(createConnectorUpgradeSignedEvidenceReceipt).mockResolvedValue(signedEvidenceReceipt);
  vi.mocked(verifyConnectorUpgradeEvidenceReceipt).mockResolvedValue(evidenceReceiptVerification);
  vi.mocked(verifyConnectorUpgradeSignedEvidenceReceipt).mockResolvedValue(
    signedEvidenceVerification,
  );
  vi.mocked(revalidateConnectorUpgradeApproval).mockResolvedValue(upgradeApprovalRevalidation);
  vi.mocked(createConnectorInstance).mockResolvedValue({ data: instance });
  vi.mocked(retireConnectorInstance).mockResolvedValue({
    ...instance,
    version: 2,
    instance_state: "retired",
    eligible_for_configuration_governance: false,
    retired_by: "subject.operator",
    retired_at: "2026-08-11T17:00:00Z",
    retirement_reason: "The unused MCP identity has completed governed retirement.",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InstalledMcpManagementWorkspace", () => {
  it("shows installed MCP inventory with visible add and reversible retirement controls", async () => {
    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Installed MCPs" })).toBeVisible();
    expect(await screen.findByText("Storage East")).toBeVisible();
    expect(screen.getByText("Backend authorization enforced")).toBeVisible();
    expect(screen.getByText("1 governed package")).toBeVisible();
    expect(screen.getByText("1 creation policy")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add MCP" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Remove Storage East" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Review update for Storage East" }))
      .toHaveTextContent("Review update");
    expect(screen.getByRole("button", { name: "Remove Storage East" }))
      .toHaveTextContent("Remove");
    expect(screen.getByText("Security and onboarding diagnostics")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Signing trust" })).not.toBeVisible();

    fireEvent.click(screen.getByText("Security and onboarding diagnostics"));
    expect(screen.getByRole("heading", { name: "Signing trust" })).toBeVisible();
    expect(screen.getByText("Signing-provider conformance")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Provider onboarding readiness" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Policy provenance diagnostic" })).toBeVisible();
    expect(screen.getByText("Policy provenance verified")).toBeVisible();
    expect(screen.getAllByText("signature verified")).toHaveLength(2);
    expect(screen.getByText("2 requirements blocked")).toBeVisible();
    expect(screen.getByText("provider production approved")).toBeVisible();
    expect(screen.getByText("security approval current")).toBeVisible();
    expect(screen.getAllByText("connector-upgrade-signing-provider-onboarding.default"))
      .toHaveLength(2);
    expect(screen.getAllByText("subject.security-architecture")).toHaveLength(2);
    expect(screen.getAllByText("7777777777777777")).toHaveLength(2);
    expect(screen.getByText("Issuer attestation verified")).toBeVisible();
    expect(screen.getAllByText(/key\.connector-upgrade-onboarding-policy\.test/)).toHaveLength(2);
    expect(screen.getByText("8888888888888888")).toBeVisible();
    expect(screen.getAllByText("key.connector-upgrade-evidence.test")).toHaveLength(2);
    expect(screen.getByText("Verification trusted")).toBeVisible();
    expect(screen.getByText(/No key management or signing authority/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Review update for Storage East" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /rotate|revoke|disable|export key/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /configure provider|approve provider/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /upload|trust key|sign policy/i })).toBeNull();
  });

  it("restores configured target state and hides retirement for the bound MCP", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    renderWorkspace();

    expect(await screen.findByText("Disabled / target configured")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Remove Storage East" })).toBeNull();
    const viewTarget = screen.getByRole("button", { name: "View target for Storage East" });
    expect(viewTarget).toBeVisible();
    fireEvent.click(viewTarget);

    expect(
      screen.getByRole("dialog", { name: "Manage target for Storage East" }),
    ).toBeVisible();
    expect(screen.getByText(configuredBinding.binding_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Bind governed target" })).toBeNull();
  });

  it("restores credential-assigned state without target mutation or retirement controls", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    renderWorkspace();

    expect(await screen.findByText("Disabled / credentials assigned")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Remove Storage East" })).toBeNull();
    expect(screen.getByRole("button", { name: "View target for Storage East" })).toBeVisible();
    const viewCredentials = screen.getByRole("button", {
      name: "View credentials for Storage East",
    });
    expect(viewCredentials).toBeVisible();
    fireEvent.click(viewCredentials);

    expect(
      screen.getByRole("dialog", { name: "Manage credentials for Storage East" }),
    ).toBeVisible();
    expect(screen.getByText(credentialAssignment.assignment_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Assign credential profile" })).toBeNull();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy/i })).toBeNull();
  });

  it("restores configuration-validated state as read-only evidence", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    renderWorkspace();

    expect(await screen.findByText("Disabled / configuration validated")).toBeVisible();
    expect(screen.getByText("Configuration validated")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Remove Storage East" })).toBeNull();
    expect(screen.getByRole("button", { name: "View target for Storage East" })).toBeVisible();
    expect(screen.getByRole("button", { name: "View credentials for Storage East" })).toBeVisible();
    const viewValidation = screen.getByRole("button", {
      name: "View configuration for Storage East",
    });
    expect(viewValidation).toHaveTextContent("View validation");
    fireEvent.click(viewValidation);

    expect(
      screen.getByRole("dialog", { name: "Validate configuration for Storage East" }),
    ).toBeVisible();
    expect(screen.getByText(configurationValidation.validation_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Verify signed evidence" })).toBeNull();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy|connect/i })).toBeNull();
  });

  it("restores capability-governed state with read-only capability metadata", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    vi.mocked(getConnectorCapabilityEnablements).mockResolvedValue([
      capabilityEnablementInventoryItem,
    ]);
    renderWorkspace();

    expect(await screen.findByText("Enabled / capabilities governed")).toBeVisible();
    expect(screen.getByText("Capabilities governed")).toBeVisible();
    const viewCapabilities = screen.getByRole("button", {
      name: "View capabilities for Storage East",
    });
    expect(viewCapabilities).toHaveTextContent("View capabilities");
    fireEvent.click(viewCapabilities);

    const dialog = screen.getByRole("dialog", { name: "Manage capabilities for Storage East" });
    expect(dialog).toBeVisible();
    expect(await screen.findByText(capabilityEnablement.enablement_id)).toBeVisible();
    expect(screen.getByText("health.read")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Enable governed capabilities" })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /connect|run|execute|deploy|runtime/i }))
      .toBeNull();
    expect(within(dialog).queryByRole("heading", { name: "Runtime trust" })).toBeNull();
  });

  it("transitions a validated MCP to capability governed using server options", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    vi.mocked(getConnectorCapabilityEnablementOptions).mockResolvedValue([
      capabilityEnablementOption,
    ]);
    renderWorkspace();

    expect(await screen.findByText("Disabled / configuration validated")).toBeVisible();
    const manageCapabilities = screen.getByRole("button", {
      name: "Manage capabilities for Storage East",
    });
    expect(manageCapabilities).toHaveTextContent("Enable governed capabilities");
    fireEvent.click(manageCapabilities);

    expect(
      await screen.findByRole("combobox", {
        name: "Governed capability profile and policy",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: /profile id|profile digest|policy id|policy digest/i }),
    ).toBeNull();
    fireEvent.click(screen.getByLabelText(/Enablement selects only the exact signed C0\/C1/i));
    fireEvent.click(screen.getByRole("button", { name: "Enable governed capabilities" }));

    await waitFor(() => expect(createConnectorCapabilityEnablement).toHaveBeenCalledOnce());
    const createInput = vi.mocked(createConnectorCapabilityEnablement).mock.calls[0]?.[0];
    expect(createInput?.validation).toBe(configurationValidation);
    expect(createInput?.option).toBe(capabilityEnablementOption);
    expect(createInput?.purpose).toMatch(/exact signed C0 and C1 capability policy/i);
    expect(await screen.findByText(capabilityEnablement.enablement_id)).toBeVisible();
    expect(screen.getByText("Enabled / capabilities governed")).toBeVisible();
    expect(screen.getByText("Capabilities governed")).toBeVisible();
    expect(screen.getByRole("button", { name: "View capabilities for Storage East" }))
      .toHaveTextContent("View capabilities");
    const dialog = screen.getByRole("dialog", { name: "Manage capabilities for Storage East" });
    expect(within(dialog).queryByRole("button", { name: /connect|run|execute|deploy/i })).toBeNull();
  });

  it("restores runtime-trusted state with a read-only runtime boundary", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    vi.mocked(getConnectorCapabilityEnablements).mockResolvedValue([
      capabilityEnablementInventoryItem,
    ]);
    vi.mocked(getConnectorRuntimeTrustGrants).mockResolvedValue([runtimeTrustGrant]);
    renderWorkspace();

    expect(await screen.findByText("Enabled / runtime trusted")).toBeVisible();
    expect(screen.getByText("Runtime trusted")).toBeVisible();
    const viewRuntime = screen.getByRole("button", {
      name: "View runtime trust for Storage East",
    });
    expect(viewRuntime).toHaveTextContent("View runtime trust");
    fireEvent.click(viewRuntime);
    const dialog = screen.getByRole("dialog", { name: "Manage runtime trust for Storage East" });
    expect(await within(dialog).findByText(runtimeTrustGrant.grant_id)).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "Establish runtime trust" })).toBeNull();
    expect(within(dialog).queryByRole("heading", { name: /secret brokerage/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /^(connect|run|invoke|execute|deploy|resolve secret)/i }))
      .toBeNull();
  });

  it("transitions a capability-governed MCP to runtime trusted using server options", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    vi.mocked(getConnectorCapabilityEnablements).mockResolvedValue([
      capabilityEnablementInventoryItem,
    ]);
    vi.mocked(getConnectorRuntimeTrustGrantOptions).mockResolvedValue([runtimeTrustGrantOption]);
    renderWorkspace();

    expect(await screen.findByText("Enabled / capabilities governed")).toBeVisible();
    const establish = screen.getByRole("button", {
      name: "Establish runtime trust for Storage East",
    });
    fireEvent.click(establish);
    expect(
      await screen.findByRole("combobox", { name: "Signed runtime profile and trust policy" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: /profile id|profile digest|policy id|policy digest/i }),
    ).toBeNull();
    fireEvent.click(screen.getByLabelText(/Trust binds only this signed isolated boundary/i));
    fireEvent.click(screen.getByRole("button", { name: "Establish runtime trust" }));

    await waitFor(() => expect(createConnectorRuntimeTrustGrant).toHaveBeenCalledOnce());
    const input = vi.mocked(createConnectorRuntimeTrustGrant).mock.calls[0]?.[0];
    expect(input?.enablement).toBe(capabilityEnablementInventoryItem);
    expect(input?.option).toBe(runtimeTrustGrantOption);
    expect(await screen.findByText("Enabled / runtime trusted")).toBeVisible();
    expect(screen.getByRole("button", { name: "View runtime trust for Storage East" }))
      .toHaveTextContent("View runtime trust");
  });

  it("keeps earlier lifecycle controls available when runtime trust inventory is unavailable", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    vi.mocked(getConnectorCapabilityEnablements).mockResolvedValue([
      capabilityEnablementInventoryItem,
    ]);
    vi.mocked(getConnectorRuntimeTrustGrants).mockRejectedValue(
      new ApiRequestError("Runtime trust inventory failed", 403),
    );
    renderWorkspace();

    expect(await screen.findByText("Enabled / capabilities governed")).toBeVisible();
    expect(screen.getByRole("button", { name: "View target for Storage East" })).toBeVisible();
    expect(screen.getByRole("button", { name: "View capabilities for Storage East" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /runtime trust for Storage East/i })).toBeNull();
    expect(screen.getByText("Runtime trust permission is required")).toBeVisible();
  });

  it("keeps existing lifecycle controls available when capability inventory is unavailable", async () => {
    vi.mocked(getConnectorTargetConfigurations).mockResolvedValue([configuredBinding]);
    vi.mocked(getConnectorCredentialAssignments).mockResolvedValue([credentialAssignment]);
    vi.mocked(getConnectorConfigurationValidations).mockResolvedValue([configurationValidation]);
    vi.mocked(getConnectorCapabilityEnablements).mockRejectedValue(
      new ApiRequestError("Capability enablement inventory failed", 403),
    );
    renderWorkspace();

    expect(await screen.findByText("Disabled / configuration validated")).toBeVisible();
    expect(screen.getByRole("button", { name: "View target for Storage East" })).toBeVisible();
    expect(screen.getByRole("button", { name: "View credentials for Storage East" })).toBeVisible();
    expect(screen.getByRole("button", { name: "View configuration for Storage East" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /capabilities for Storage East/i })).toBeNull();
    expect(screen.getByText("Capability governance permission is required")).toBeVisible();
    expect(screen.queryByText("Connector lifecycle permission is required")).toBeNull();
  });

  it("runs a bounded provider assessment without exposing signing or key controls", async () => {
    vi.mocked(getLatestConnectorUpgradeSigningProviderConformance).mockResolvedValue(null);
    renderWorkspace();

    fireEvent.click(await screen.findByText("Security and onboarding diagnostics"));
    const run = await screen.findByRole("button", { name: "Run assessment" });
    expect(await screen.findByText(/No bounded provider assessment/i)).toBeVisible();
    fireEvent.click(run);

    await waitFor(() =>
      expect(assessConnectorUpgradeSigningProviderConformance).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("conformant")).toBeVisible();
    expect(screen.getByText("provider.nonproduction-hmac")).toBeVisible();
    expect(screen.getByText(/not approved for production/i)).toBeVisible();
    expect(screen.getByText(/Server-generated challenge only/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /sign receipt|rotate|revoke|export/i })).toBeNull();
  });

  it("explains blocked policy provenance without exposing trust mutation controls", async () => {
    const blockedChecks = signingProviderOnboardingProvenance.checks.map((check, index) =>
      index === 0
        ? check
        : {
            ...check,
            state: "unavailable" as const,
            reason_code: index === 1
              ? "connector.upgrade.signing-provider-onboarding-policy-provenance.attestation-unavailable"
              : "connector.upgrade.signing-provider-onboarding-policy-provenance.prerequisite-unavailable",
            evidence_reference: null,
            owner_role_id: index === 1
              ? "role.security-policy-attestation-owner"
              : "role.connector-upgrade-provenance-coordinator",
            evidence_requirement_id: index === 1
              ? "evidence.current-policy-attestation"
              : "evidence.prior-provenance-check",
            next_action_id: index === 1
              ? "action.publish-policy-attestation"
              : "action.resolve-prior-provenance-check",
            external_input_required: index === 1,
          });
    vi.mocked(
      getConnectorUpgradeSigningProviderOnboardingPolicyProvenanceDiagnostic,
    ).mockResolvedValue({
      ...signingProviderOnboardingProvenance,
      valid_until: null,
      state: "blocked",
      attestation_id: null,
      attestation_digest: null,
      trust_key_id: null,
      trust_key_version: null,
      trust_algorithm: null,
      trust_key_state: null,
      checks: blockedChecks,
      reason_codes: blockedChecks.slice(1).map((check) => check.reason_code),
      provenance_verified: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByText("Security and onboarding diagnostics"));
    expect(await screen.findByText("4 provenance checks blocked")).toBeVisible();
    expect(screen.getAllByText("prerequisite unavailable")).toHaveLength(3);
    expect(screen.getByText("security policy attestation owner")).toBeVisible();
    expect(screen.getByText("current policy attestation")).toBeVisible();
    expect(screen.getByText("publish policy attestation")).toBeVisible();
    expect(screen.getByText("External deployment input required")).toBeVisible();
    expect(screen.getAllByText("connector upgrade provenance coordinator")).toHaveLength(3);
    expect(screen.getByText(/No verified validity horizon/i)).toBeVisible();
    expect(screen.getByText(/No trust-store, policy, key or provider mutation authority/i))
      .toBeVisible();
    expect(screen.queryByRole("button", { name: /upload|trust|sign|approve|configure/i }))
      .toBeNull();
  });

  it("does not block a single-factor identity solely because of its assurance level", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    renderWorkspace("subject.local-operator", onRequestEnterpriseLogin);

    expect(await screen.findByText("Storage East")).toBeVisible();
    expect(screen.getByText("Backend authorization enforced")).toBeVisible();
    expect(screen.queryByText(/MFA/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Add MCP" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Review update for Storage East" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Remove Storage East" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Add MCP" }));
    expect(screen.getByRole("dialog", { name: "Add MCP" })).toBeVisible();
    expect(onRequestEnterpriseLogin).not.toHaveBeenCalled();
  });

  it("offers retry without re-login guidance for generic lifecycle query failures", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(getConnectorPackageInstallations)
      .mockRejectedValue(new Error("Connector package inventory failed with 503"));
    renderWorkspace("subject.connector-operator", onRequestEnterpriseLogin);

    expect(await screen.findByText("Connector lifecycle data is unavailable")).toBeVisible();
    expect(screen.getByText(/could not be loaded\. Retry the request/i)).toBeVisible();
    expect(screen.queryByText(/Sign in again|authorized browser session/i)).toBeNull();
    expect(screen.queryByRole("button", { name: "Sign in again" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(getConnectorPackageInstallations).toHaveBeenCalledTimes(2));
    expect(onRequestEnterpriseLogin).not.toHaveBeenCalled();
  });

  it("offers re-login only for a verified 401 lifecycle response", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(getConnectorInstances)
      .mockRejectedValue(new ApiRequestError("Connector instance inventory failed", 401));
    renderWorkspace("subject.connector-operator", onRequestEnterpriseLogin);

    expect(await screen.findByText("Your signed-in session has expired")).toBeVisible();
    expect(screen.getByText(/Sign in again; the MCP inventory will refresh automatically/i))
      .toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledTimes(1);
  });

  it("reports a verified 403 as missing authorization without suggesting re-login", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(getConnectorInstances)
      .mockRejectedValue(new ApiRequestError("Connector instance inventory failed", 403));
    renderWorkspace("subject.connector-operator", onRequestEnterpriseLogin);

    expect(await screen.findByText("Connector lifecycle permission is required")).toBeVisible();
    expect(screen.getByText(/missing a required role or scope/i)).toBeVisible();
    expect(screen.queryByText(/Sign in again|authorized browser session/i)).toBeNull();
    expect(screen.queryByRole("button", { name: "Sign in again" })).toBeNull();
    expect(onRequestEnterpriseLogin).not.toHaveBeenCalled();
  });

  it("shows evidence-based upgrade readiness without exposing an update action", async () => {
    renderWorkspace();
    fireEvent.click(
      await screen.findByRole("button", { name: "Review update for Storage East" }),
    );

    expect(await screen.findByRole("heading", { name: "Review update for Storage East" })).toBeVisible();
    expect(await screen.findByText("version.2.0.0")).toBeVisible();
    expect(screen.getByText("high risk")).toBeVisible();
    expect(screen.getByText("added: storage.capacity.read")).toBeVisible();
    expect(screen.getByText(/does not install an update/i)).toBeVisible();
    expect(getConnectorUpgradeReadiness).toHaveBeenCalledWith(instance.record_id);
    expect(screen.queryByRole("button", { name: /install|apply|execute/i })).toBeNull();
    expect(screen.getByRole("button", { name: "Close review" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Review plan for version.2.0.0" }));
    expect(await screen.findByRole("heading", { name: "version.1.0.0 to version.2.0.0" })).toBeVisible();
    expect(screen.getByText("ready for human review")).toBeVisible();
    expect(screen.getByText("0-0 minutes")).toBeVisible();
    expect(screen.getByText(/does not rebind a package/i)).toBeVisible();
    expect(getConnectorUpgradePlan).toHaveBeenCalledWith(
      instance.record_id,
      upgradePlan.candidate_receipt_id,
    );
    const request = await screen.findByRole("button", { name: "Request human approval" });
    expect(request).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/This creates a review request only/i));
    expect(request).toBeEnabled();
    fireEvent.click(request);
    await waitFor(() => expect(createConnectorUpgradeApprovalRequest).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Pending human review")).toBeVisible();
    expect(screen.getByText("Requester cannot decide")).toBeVisible();
    expect(screen.getByText(/grants no execution authority/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|apply|execute/i })).toBeNull();
  });

  it("restores a pending request and lets only an independent human record a non-executable decision", async () => {
    vi.mocked(getConnectorUpgradeApprovalRecord).mockResolvedValue(pendingUpgradeApproval);
    renderWorkspace("subject.connector-independent-approver");
    fireEvent.click(await screen.findByRole("button", { name: "Review update for Storage East" }));
    fireEvent.click(await screen.findByRole("button", { name: "Review plan for version.2.0.0" }));

    expect(await screen.findByText("Pending human review")).toBeVisible();
    expect(screen.getByRole("button", { name: "Approve" })).toHaveAttribute("aria-pressed", "false");
    const recordDecision = screen.getByRole("button", { name: "Record decision" });
    expect(recordDecision).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.change(screen.getByLabelText("Decision rationale"), {
      target: { value: "Approve this exact immutable plan after independent evidence review." },
    });
    fireEvent.click(screen.getByLabelText(/records a human decision only/i));
    expect(recordDecision).toBeEnabled();
    fireEvent.click(recordDecision);

    await waitFor(() => expect(decideConnectorUpgradeApproval).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Human decision: approved")).toBeVisible();
    expect(screen.getByText("subject.connector-independent-approver")).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|apply|execute/i })).toBeNull();
  });

  it("lets only a third human revalidate an approved decision without exposing handoff or execution", async () => {
    vi.mocked(getConnectorUpgradeApprovalRecord).mockResolvedValue(approvedUpgradeApproval);
    renderWorkspace("subject.connector-independent-verifier");
    fireEvent.click(await screen.findByRole("button", { name: "Review update for Storage East" }));
    fireEvent.click(await screen.findByRole("button", { name: "Review plan for version.2.0.0" }));

    expect(await screen.findByText("Independent approval revalidation")).toBeVisible();
    const revalidate = screen.getByRole("button", { name: "Revalidate approval" });
    expect(revalidate).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/produces evidence only/i));
    expect(revalidate).toBeEnabled();
    fireEvent.click(revalidate);

    await waitFor(() => expect(revalidateConnectorUpgradeApproval).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Governance ready")).toBeVisible();
    expect(screen.getByText(/Handoff remains blocked/i)).toBeVisible();
    expect(await screen.findByText("Evidence review complete")).toBeVisible();
    expect(screen.getByText(/No artifact was issued/i)).toBeVisible();
    expect(screen.queryByText("Required evidence missing")).toBeNull();
    expect(screen.getByText("Satisfied checks")).toBeVisible();
    expect(screen.getByText(/Audit readiness evidence verified/i)).toBeVisible();
    expect(screen.getByText(/Authoritative ITSM change evidence verified/i)).toBeVisible();
    expect(screen.getByText(/Approved maintenance-window evidence is current/i)).toBeVisible();
    expect(screen.getByText("Non-executable evidence receipt")).toBeVisible();
    const createReceipt = screen.getByRole("button", { name: "Create evidence receipt" });
    expect(createReceipt).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/This receipt is evidence only/i));
    expect(createReceipt).toBeEnabled();
    fireEvent.click(createReceipt);
    await waitFor(() => expect(createConnectorUpgradeEvidenceReceipt).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Evidence receipt ready")).toBeVisible();
    expect(screen.getByRole("button", { name: "Download JSON receipt" })).toBeVisible();
    expect(screen.getByText(/Runtime acceptable: no. Approval consumed: no./i)).toBeVisible();
    const authenticateOrigin = screen.getByRole("button", { name: "Authenticate Atlas origin" });
    expect(authenticateOrigin).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Authenticate Atlas origin only/i));
    expect(authenticateOrigin).toBeEnabled();
    fireEvent.click(authenticateOrigin);
    await waitFor(() => expect(createConnectorUpgradeSignedEvidenceReceipt).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Origin authenticated")).toBeVisible();
    expect(screen.getByRole("button", { name: "Download signed receipt" })).toBeVisible();
    const verifyReceipt = screen.getByRole("button", { name: "Verify evidence receipt" });
    expect(verifyReceipt).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Receipt JSON"), {
      target: {
        files: [new File([JSON.stringify(signedEvidenceReceipt)], "signed-receipt.json", {
          type: "application/json",
        })],
      },
    });
    fireEvent.click(await screen.findByLabelText(/A valid signature authenticates Atlas origin only/i));
    const verifySignedReceipt = await screen.findByRole("button", { name: "Verify signed receipt" });
    await waitFor(() => expect(verifySignedReceipt).toBeEnabled());
    fireEvent.click(verifySignedReceipt);
    await waitFor(() => expect(verifyConnectorUpgradeSignedEvidenceReceipt).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Signature authentic")).toBeVisible();
    expect(screen.getByText(/Atlas origin authenticated: yes. Current state matches: yes./i))
      .toBeVisible();
    expect(screen.getByText("Not applicable in this context")).toBeVisible();
    expect(screen.getByText(/target-binding-current/i)).toBeVisible();
    expect(screen.getByText(/Applicability policy v2026.08.12.1/i)).toBeVisible();
    expect(screen.getByText("Prepare change-context draft")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Proposed window start"), { target: { value: "2026-08-12T03:00" } });
    fireEvent.change(screen.getByLabelText("Proposed window end"), { target: { value: "2026-08-12T04:00" } });
    fireEvent.click(screen.getByLabelText(/creates an internal draft only/i));
    fireEvent.click(screen.getByRole("button", { name: "Record change-context draft" }));
    await waitFor(() => expect(createConnectorUpgradeChangeContextDraft).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Change-context draft recorded")).toBeVisible();
    expect(screen.getByText(/Not dispatched. This internal draft grants no window or handoff authority./i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|apply|execute|handoff/i })).toBeNull();
  });

  it("requires a third verifier when the approved decision belongs to the current subject", async () => {
    vi.mocked(getConnectorUpgradeApprovalRecord).mockResolvedValue(approvedUpgradeApproval);
    renderWorkspace("subject.connector-independent-approver");
    fireEvent.click(await screen.findByRole("button", { name: "Review update for Storage East" }));
    fireEvent.click(await screen.findByRole("button", { name: "Review plan for version.2.0.0" }));

    expect(await screen.findByText("Third verifier required")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Revalidate approval" })).toBeNull();
  });

  it("adds only an acknowledged disabled instance from a governed installed package", async () => {
    renderWorkspace();
    const add = await screen.findByRole("button", { name: "Add MCP" });
    await waitFor(() => expect(add).toBeEnabled());
    fireEvent.click(add);

    expect(screen.getByLabelText("Installed package")).toHaveValue(installation.receipt_id);
    const submit = screen.getByRole("button", { name: "Add disabled MCP" });
    expect(submit).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(/The MCP remains disabled and unconfigured/i),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(createConnectorInstance).toHaveBeenCalledTimes(1));
    expect(vi.mocked(createConnectorInstance).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        installation,
        instanceKey: `${installation.connector_id}-managed`,
      }),
    );
  });

  it("offers re-login when MCP creation returns a verified 401", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(createConnectorInstance).mockRejectedValue(
      new ApiRequestError("Connector instance creation failed", 401),
    );
    renderWorkspace("subject.connector-operator", onRequestEnterpriseLogin);

    const add = await screen.findByRole("button", { name: "Add MCP" });
    await waitFor(() => expect(add).toBeEnabled());
    fireEvent.click(add);
    fireEvent.click(screen.getByLabelText(/The MCP remains disabled and unconfigured/i));
    fireEvent.click(screen.getByRole("button", { name: "Add disabled MCP" }));

    expect(await screen.findByText("Your signed-in session has expired")).toBeVisible();
    expect(screen.getByText(/Sign in again before changing MCP lifecycle records/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledTimes(1);
  });

  it("reports a verified 403 retirement denial without suggesting re-login", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(retireConnectorInstance).mockRejectedValue(
      new ApiRequestError("Connector instance retirement failed", 403),
    );
    renderWorkspace("subject.connector-operator", onRequestEnterpriseLogin);

    fireEvent.click(await screen.findByRole("button", { name: "Remove Storage East" }));
    fireEvent.change(screen.getByLabelText("Retirement reason"), {
      target: { value: "Retire this unused connector identity while preserving its history." },
    });
    fireEvent.click(screen.getByLabelText(/history is preserved/i));
    fireEvent.click(screen.getByRole("button", { name: "Confirm retirement" }));

    expect(await screen.findByText("Connector lifecycle permission is required")).toBeVisible();
    expect(screen.getByText(/missing the required role or scope/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Sign in again" })).toBeNull();
    expect(onRequestEnterpriseLogin).not.toHaveBeenCalled();
  });

  it("refreshes authoritative inventory after a verified 409 lifecycle conflict", async () => {
    vi.mocked(retireConnectorInstance).mockRejectedValue(
      new ApiRequestError("Connector instance retirement failed", 409),
    );
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: "Remove Storage East" }));
    fireEvent.change(screen.getByLabelText("Retirement reason"), {
      target: { value: "Retire this unused connector identity while preserving its history." },
    });
    fireEvent.click(screen.getByLabelText(/history is preserved/i));
    fireEvent.click(screen.getByRole("button", { name: "Confirm retirement" }));

    expect(await screen.findByText("MCP lifecycle changed")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Refresh inventory" }));
    await waitFor(() => expect(getConnectorInstances).toHaveBeenCalledTimes(2));
  });

  it("does not expose an approval request control for a blocked upgrade plan", async () => {
    vi.mocked(getConnectorUpgradePlan).mockResolvedValue({
      ...upgradePlan,
      plan_state: "blocked",
      plan_eligible: false,
      target_configured: true,
      target_id: "target.storage-east",
      site_id: "site.primary",
      target_product: "product.storage",
      blockers: ["connector.upgrade.impact-evidence-required"],
      unknowns: ["Current service impact is not established."],
      estimated_interruption_min_minutes: null,
      estimated_interruption_max_minutes: null,
    });
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Review update for Storage East" }));
    fireEvent.click(await screen.findByRole("button", { name: "Review plan for version.2.0.0" }));

    expect(await screen.findByText("blocked")).toBeVisible();
    expect(screen.getByText(/impact-evidence-required/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Request human approval" })).toBeNull();
  });

  it("requires a reason and explicit no-runtime-action acknowledgement before retirement", async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Remove Storage East" }));

    expect(screen.getByRole("heading", { name: "Remove Storage East" })).toBeVisible();
    const submit = screen.getByRole("button", { name: "Confirm retirement" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Retirement reason"), {
      target: { value: "The unused MCP identity has completed governed retirement." },
    });
    fireEvent.click(screen.getByLabelText(/history is preserved/i));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(retireConnectorInstance).toHaveBeenCalledTimes(1));
    expect(vi.mocked(retireConnectorInstance).mock.calls[0]?.[0]).toEqual({
      instance,
      reason: "The unused MCP identity has completed governed retirement.",
    });
  });

  it("changes the instance query boundary and explains the governed package prerequisite", async () => {
    const onOpenBuilder = vi.fn();
    vi.mocked(getConnectorPackageInstallations).mockResolvedValue([]);
    vi.mocked(getConnectorInstances).mockResolvedValue([]);
    renderWorkspace("subject.connector-operator", undefined, onOpenBuilder);

    expect(await screen.findByText(/Complete package installation/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Open Builder workflow" }));
    expect(onOpenBuilder).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retired" }));
    await waitFor(() =>
      expect(getConnectorInstances).toHaveBeenLastCalledWith({ lifecycle: "retired", query: "" }),
    );
    const add = screen.getByRole("button", { name: "Add MCP" });
    await waitFor(() => expect(add).toBeEnabled());
    fireEvent.click(add);
    expect(screen.getByText("No governed package is installed")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add disabled MCP" })).toBeDisabled();
  });
});
