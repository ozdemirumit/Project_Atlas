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
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
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
