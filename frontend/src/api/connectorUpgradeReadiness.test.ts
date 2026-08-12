import { describe, expect, it } from "vitest";

import { isConnectorUpgradeHandoffReadiness } from "./connectorUpgradeReadiness";

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
