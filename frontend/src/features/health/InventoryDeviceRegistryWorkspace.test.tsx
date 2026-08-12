import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createInventoryDevice,
  getInventoryDevices,
  retireInventoryDevice,
  type InventoryDevice,
} from "../../api/inventoryDevices";
import InventoryDeviceRegistryWorkspace from "./InventoryDeviceRegistryWorkspace";

vi.mock("../../api/inventoryDevices", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/inventoryDevices")>();
  return {
    ...original,
    createInventoryDevice: vi.fn(),
    getInventoryDevices: vi.fn(),
    retireInventoryDevice: vi.fn(),
  };
});

const device: InventoryDevice = {
  device_id: "inventory-device.test-01",
  schema_version: "atlas.inventory-device-record.v1",
  version: 1,
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.local",
  device_key: "storage.vsp-01",
  display_name: "Primary VSP",
  device_type: "storage",
  vendor: "Hitachi Vantara",
  model: "VSP E790",
  serial_number: "SN-TEST-0001",
  management_address: "vsp-01.lab.example",
  source: "manual",
  lifecycle: "active",
  purpose: "Register the array for governed inventory and read-only health correlation.",
  created_by: "subject.test",
  created_at: "2026-08-11T12:00:00Z",
  updated_by: "subject.test",
  updated_at: "2026-08-11T12:00:00Z",
  retired_by: null,
  retired_at: null,
  retirement_reason: null,
  canonical_digest: "a".repeat(64),
  reused: false,
};

function renderWorkspace(
  governedSessionAvailable = true,
  onRequestEnterpriseLogin?: () => void,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <InventoryDeviceRegistryWorkspace
        governedSessionAvailable={governedSessionAvailable}
        onRequestEnterpriseLogin={onRequestEnterpriseLogin}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getInventoryDevices).mockResolvedValue({
    devices: [device],
    durable: true,
    truncated: false,
  });
  vi.mocked(createInventoryDevice).mockResolvedValue(device);
  vi.mocked(retireInventoryDevice).mockResolvedValue({
    ...device,
    version: 2,
    lifecycle: "retired",
    retired_by: "subject.test",
    retired_at: "2026-08-11T12:10:00Z",
    retirement_reason: "The governed decommissioning workflow has completed.",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InventoryDeviceRegistryWorkspace", () => {
  it("lists authorized devices and exposes create and reversible retirement controls", async () => {
    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Registered infrastructure" })).toBeVisible();
    expect(await screen.findByText("Primary VSP")).toBeVisible();
    expect(screen.getByText("Durable store")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add device" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Retire Primary VSP" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
  });

  it("requires complete device data and the no-action acknowledgement before registration", async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Add device" }));

    const submit = screen.getByRole("button", { name: "Register device" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Device key"), { target: { value: "storage.vsp-02" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Secondary VSP" } });
    fireEvent.change(screen.getByLabelText("Vendor"), { target: { value: "Hitachi Vantara" } });
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "VSP E590" } });
    fireEvent.change(screen.getByLabelText("Serial number"), { target: { value: "SN-TEST-0002" } });
    fireEvent.change(screen.getByLabelText("Management address"), { target: { value: "vsp-02.lab.example" } });
    fireEvent.change(screen.getByLabelText("Registration purpose"), {
      target: { value: "Register this array for governed inventory and health correlation." },
    });
    fireEvent.click(
      screen.getByLabelText("No credentials are stored and no infrastructure action is authorized."),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(createInventoryDevice).toHaveBeenCalledTimes(1));
    expect(vi.mocked(createInventoryDevice).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        deviceKey: "storage.vsp-02",
        displayName: "Secondary VSP",
        managementAddress: "vsp-02.lab.example",
      }),
    );
  });

  it("requires an explicit reason and acknowledgement before retirement", async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Retire Primary VSP" }));

    const submit = screen.getByRole("button", { name: "Retire device" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Retirement reason"), {
      target: { value: "The governed decommissioning workflow has completed successfully." },
    });
    fireEvent.click(
      screen.getByLabelText(
        "Preserve this record and stop using it as an active inventory target.",
      ),
    );
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(retireInventoryDevice).toHaveBeenCalledTimes(1));
    expect(retireInventoryDevice).toHaveBeenCalledWith({
      device,
      reason: "The governed decommissioning workflow has completed successfully.",
    });
  });

  it("updates the query boundary when the lifecycle filter changes", async () => {
    renderWorkspace();
    await screen.findByText("Primary VSP");
    fireEvent.click(screen.getByRole("button", { name: "Retired" }));

    await waitFor(() =>
      expect(getInventoryDevices).toHaveBeenLastCalledWith({ lifecycle: "retired", query: "" }),
    );
  });

  it("keeps development mode read-only and offers enterprise login", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    renderWorkspace(false, onRequestEnterpriseLogin);

    expect(await screen.findByText(/Signed browser session required for device lifecycle changes/i))
      .toBeVisible();
    expect(await screen.findByText("Primary VSP")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add device" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Retire Primary VSP" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Sign in to manage" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledTimes(1);
  });
});
