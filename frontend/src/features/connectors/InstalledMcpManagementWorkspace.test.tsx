import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorInstance,
  getConnectorInstanceCreationPolicies,
  getConnectorInstances,
  retireConnectorInstance,
  type ConnectorInstanceCreationPolicy,
} from "../../api/connectorInstances";
import {
  createConnectorUpgradeApprovalRequest,
  createConnectorUpgradeChangeContextDraft,
  decideConnectorUpgradeApproval,
  getConnectorUpgradeApprovalRecord,
  getConnectorUpgradeHandoffReadiness,
  getLatestConnectorUpgradeChangeContextDraft,
  getLatestConnectorUpgradeApprovalRevalidation,
  getConnectorUpgradePlan,
  getConnectorUpgradeReadiness,
  revalidateConnectorUpgradeApproval,
  type ConnectorUpgradeApprovalRecord,
  type ConnectorUpgradeApprovalRequest,
  type ConnectorUpgradeApprovalRevalidation,
  type ConnectorUpgradeHandoffReadiness,
  type ConnectorUpgradeChangeContextDraft,
  type ConnectorUpgradePlan,
  type ConnectorUpgradeReadiness,
} from "../../api/connectorUpgradeReadiness";
import { getConnectorPackageInstallations } from "../../api/packageInstallations";
import InstalledMcpManagementWorkspace from "./InstalledMcpManagementWorkspace";
import { connectorInstanceRecord as instance } from "./testInstanceFixture";
import { installationReceipt as installation } from "./testInstallationFixture";

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
  schema_version: "atlas.connector-upgrade-handoff-readiness.v4",
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
  required_check_ids: [
    "connector.upgrade.handoff.approval-current",
    "connector.upgrade.handoff.itsm-change-current",
    "connector.upgrade.handoff.maintenance-window-current",
    "connector.upgrade.handoff.audit-readiness-evidence-current",
    "connector.upgrade.handoff.itsm-change-current",
  ],
  satisfied_check_ids: [
    "connector.upgrade.handoff.approval-current",
    "connector.upgrade.handoff.audit-readiness-evidence-current",
  ],
  not_applicable_check_ids: [
    "connector.upgrade.handoff.target-binding-current",
    "connector.upgrade.handoff.service-impact-evidence-current",
    "connector.upgrade.handoff.runtime-health-evidence-current",
  ],
  blocker_ids: [
    "connector.upgrade.handoff.blocked.maintenance-window-missing",
  ],
  assessed_at: "2026-08-12T00:41:00Z",
  evidence_valid_until: "2026-08-12T01:00:00Z",
  canonical_digest: "4".repeat(64),
  assessment_state: "blocked",
  approval_current: true,
  revalidation_current: true,
  audit_readiness_evidence_current: true,
  itsm_change_evidence_current: true,
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

vi.mock("../../api/connectorUpgradeReadiness", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/connectorUpgradeReadiness")>();
  return {
    ...original,
    createConnectorUpgradeApprovalRequest: vi.fn(),
    decideConnectorUpgradeApproval: vi.fn(),
    getConnectorUpgradeApprovalRecord: vi.fn(),
    getConnectorUpgradeHandoffReadiness: vi.fn(),
    getLatestConnectorUpgradeChangeContextDraft: vi.fn(),
    createConnectorUpgradeChangeContextDraft: vi.fn(),
    getLatestConnectorUpgradeApprovalRevalidation: vi.fn(),
    getConnectorUpgradeReadiness: vi.fn(),
    getConnectorUpgradePlan: vi.fn(),
    revalidateConnectorUpgradeApproval: vi.fn(),
  };
});

function renderWorkspace(subjectId = "subject.connector-operator") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <InstalledMcpManagementWorkspace subjectId={subjectId} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getConnectorPackageInstallations).mockResolvedValue([installation]);
  vi.mocked(getConnectorInstanceCreationPolicies).mockResolvedValue([policy]);
  vi.mocked(getConnectorInstances).mockResolvedValue([instance]);
  vi.mocked(getConnectorUpgradeReadiness).mockResolvedValue(upgradeReadiness);
  vi.mocked(getConnectorUpgradePlan).mockResolvedValue(upgradePlan);
  vi.mocked(getConnectorUpgradeApprovalRecord).mockResolvedValue(null);
  vi.mocked(createConnectorUpgradeApprovalRequest).mockResolvedValue(upgradeApprovalRequest);
  vi.mocked(decideConnectorUpgradeApproval).mockResolvedValue(approvedUpgradeApproval);
  vi.mocked(getLatestConnectorUpgradeApprovalRevalidation).mockResolvedValue(null);
  vi.mocked(getConnectorUpgradeHandoffReadiness).mockResolvedValue(handoffReadiness);
  vi.mocked(getLatestConnectorUpgradeChangeContextDraft).mockResolvedValue(null);
  vi.mocked(createConnectorUpgradeChangeContextDraft).mockResolvedValue(changeContextDraft);
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
    expect(screen.getByRole("button", { name: "Add MCP" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Retire Storage East" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Review update for Storage East" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
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
    expect(await screen.findByText("Handoff blocked")).toBeVisible();
    expect(screen.getByText(/No artifact was issued/i)).toBeVisible();
    expect(screen.getByText("Required evidence missing")).toBeVisible();
    expect(screen.getByText(/maintenance-window-missing/i)).toBeVisible();
    expect(screen.getByText("Satisfied checks")).toBeVisible();
    expect(screen.getByText(/Audit readiness evidence verified/i)).toBeVisible();
    expect(screen.getByText(/Authoritative ITSM change evidence verified/i)).toBeVisible();
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
    expect(screen.getByText(/Not dispatched. Window not approved. Handoff remains blocked./i)).toBeVisible();
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
    fireEvent.click(await screen.findByRole("button", { name: "Retire Storage East" }));

    const submit = screen.getByRole("button", { name: "Retire MCP" });
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
    vi.mocked(getConnectorPackageInstallations).mockResolvedValue([]);
    vi.mocked(getConnectorInstances).mockResolvedValue([]);
    renderWorkspace();

    expect(await screen.findByText(/Complete package installation/i)).toBeVisible();
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
