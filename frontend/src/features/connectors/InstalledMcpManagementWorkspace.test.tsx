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
  getConnectorUpgradePlan,
  getConnectorUpgradeReadiness,
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
    getConnectorUpgradeReadiness: vi.fn(),
    getConnectorUpgradePlan: vi.fn(),
  };
});

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <InstalledMcpManagementWorkspace />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getConnectorPackageInstallations).mockResolvedValue([installation]);
  vi.mocked(getConnectorInstanceCreationPolicies).mockResolvedValue([policy]);
  vi.mocked(getConnectorInstances).mockResolvedValue([instance]);
  vi.mocked(getConnectorUpgradeReadiness).mockResolvedValue(upgradeReadiness);
  vi.mocked(getConnectorUpgradePlan).mockResolvedValue(upgradePlan);
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
    expect(screen.queryByRole("button", { name: /install|apply|execute/i })).toBeNull();
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
