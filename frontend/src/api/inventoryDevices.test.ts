import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createInventoryDevice,
  getInventoryDevices,
  reactivateInventoryDevice,
  retireInventoryDevice,
  updateInventoryDevice,
  type InventoryDevice,
} from "./inventoryDevices";

const scope = {
  organizationId: "organization.test",
  environmentId: "environment.test",
  siteId: "site.local",
};

function device(overrides: Record<string, unknown> = {}): InventoryDevice {
  return {
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
    purpose: "Register the array for governed inventory and health correlation.",
    created_by: "subject.test",
    created_at: "2026-08-11T12:00:00Z",
    updated_by: "subject.test",
    updated_at: "2026-08-11T12:00:00Z",
    retired_by: null,
    retired_at: null,
    retirement_reason: null,
    canonical_digest: "a".repeat(64),
    reused: false,
    ...overrides,
  };
}

function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({ data }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("inventory device API client", () => {
  it("reads the bounded lifecycle inventory contract", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ devices: [device()], durable: true, truncated: false }),
    );

    await expect(
      getInventoryDevices({ lifecycle: "active", query: "  vsp  ", scope }),
    ).resolves.toEqual({
      devices: [device()],
      durable: true,
      truncated: false,
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/inventory/devices?limit=100&lifecycle=active&query=vsp",
    );
  });

  it("fails closed on sensitive fields and inconsistent lifecycle evidence", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        devices: [device({ credential: "must-not-render" })],
        durable: true,
        truncated: false,
      }),
    );
    await expect(
      getInventoryDevices({ lifecycle: "all", query: "", scope }),
    ).rejects.toMatchObject({
      status: 200,
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        devices: [device({ lifecycle: "retired" })],
        durable: true,
        truncated: false,
      }),
    );
    await expect(
      getInventoryDevices({ lifecycle: "all", query: "", scope }),
    ).rejects.toMatchObject({
      status: 200,
    });
  });

  it("registers a normalized device through the acknowledged create contract", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(device(), 201));

    await createInventoryDevice({
      deviceKey: " Storage.VSP-01 ",
      displayName: " Primary VSP ",
      deviceType: "storage",
      vendor: " Hitachi Vantara ",
      model: " VSP E790 ",
      serialNumber: " SN-TEST-0001 ",
      managementAddress: " VSP-01.LAB.EXAMPLE ",
      purpose: " Register the array for governed inventory and health correlation. ",
      scope,
    });

    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(request?.method).toBe("POST");
    expect(headers.get("Idempotency-Key")).toMatch(/^inventory-device-create\./);
    if (typeof request?.body !== "string") throw new Error("Expected a JSON request body");
    expect(JSON.parse(request.body)).toEqual({
      schema_version: "atlas.inventory-device-create-input.v1",
      device_key: "storage.vsp-01",
      display_name: "Primary VSP",
      device_type: "storage",
      vendor: "Hitachi Vantara",
      model: "VSP E790",
      serial_number: "SN-TEST-0001",
      management_address: "vsp-01.lab.example",
      purpose: "Register the array for governed inventory and health correlation.",
      acknowledged_no_credentials_or_infrastructure_action: true,
    });
  });

  it("removes a device from active use through version-bound retirement", async () => {
    const retired = device({
      version: 2,
      lifecycle: "retired",
      retired_by: "subject.test",
      retired_at: "2026-08-11T12:10:00Z",
      retirement_reason: "The governed decommissioning workflow has completed.",
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(retired));

    await retireInventoryDevice({
      device: device(),
      reason: " The governed decommissioning workflow has completed. ",
    });

    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/inventory/devices/inventory-device.test-01/retirements",
    );
    expect(headers.get("Idempotency-Key")).toMatch(/^inventory-device-retire\./);
    if (typeof request?.body !== "string") throw new Error("Expected a JSON request body");
    expect(JSON.parse(request.body)).toEqual({
      schema_version: "atlas.inventory-device-retirement-input.v1",
      expected_version: 1,
      reason: "The governed decommissioning workflow has completed.",
      acknowledged_retirement_preserves_history_and_stops_active_use: true,
    });
  });

  it("updates mutable device details through the exact version-bound contract", async () => {
    const updated = device({
      version: 2,
      display_name: "Primary Production VSP",
      device_type: "storage",
      vendor: "Hitachi Vantara",
      model: "VSP E790H",
      serial_number: null,
      management_address: "vsp-prod.example.net",
      purpose: "Use this array for production inventory and health correlation.",
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(updated));

    await updateInventoryDevice({
      device: device(),
      changes: {
        displayName: " Primary Production VSP ",
        deviceType: "storage",
        vendor: " Hitachi Vantara ",
        model: " VSP E790H ",
        serialNumber: " ",
        managementAddress: " VSP-PROD.EXAMPLE.NET ",
        purpose: " Use this array for production inventory and health correlation. ",
      },
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/inventory/devices/inventory-device.test-01",
    );
    const request = fetchMock.mock.calls[0]?.[1];
    expect(request?.method).toBe("PATCH");
    if (typeof request?.body !== "string") throw new Error("Expected a JSON request body");
    expect(JSON.parse(request.body)).toEqual({
      schema_version: "atlas.inventory-device-update-input.v1",
      expected_version: 1,
      display_name: "Primary Production VSP",
      device_type: "storage",
      vendor: "Hitachi Vantara",
      model: "VSP E790H",
      serial_number: null,
      management_address: "vsp-prod.example.net",
      purpose: "Use this array for production inventory and health correlation.",
    });
  });

  it("reactivates a retired device with only its schema and expected version", async () => {
    const retired = device({
      version: 2,
      lifecycle: "retired",
      retired_by: "subject.test",
      retired_at: "2026-08-11T12:10:00Z",
      retirement_reason: "The governed decommissioning workflow has completed.",
    });
    const reactivated = device({ version: 3 });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(reactivated));

    await reactivateInventoryDevice({ device: retired });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/inventory/devices/inventory-device.test-01/reactivations",
    );
    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(request?.method).toBe("POST");
    expect(headers.get("Idempotency-Key")).toMatch(/^inventory-device-reactivate\./);
    if (typeof request?.body !== "string") throw new Error("Expected a JSON request body");
    expect(JSON.parse(request.body)).toEqual({
      schema_version: "atlas.inventory-device-reactivation-input.v1",
      expected_version: 2,
    });
  });

  it("fails closed when list scope or requested lifecycle does not match", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        devices: [device({ organization_id: "organization.foreign" })],
        durable: true,
        truncated: false,
      }),
    );
    await expect(
      getInventoryDevices({ lifecycle: "active", query: "", scope }),
    ).rejects.toMatchObject({ status: 200 });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        devices: [
          device({
            lifecycle: "retired",
            version: 2,
            retired_by: "subject.test",
            retired_at: "2026-08-11T12:10:00Z",
            retirement_reason: "The governed decommissioning workflow has completed.",
          }),
        ],
        durable: true,
        truncated: false,
      }),
    );
    await expect(
      getInventoryDevices({ lifecycle: "active", query: "", scope }),
    ).rejects.toMatchObject({ status: 200 });
  });

  it("binds create and retirement responses to the exact request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(device({ device_key: "storage.other" }), 201),
    );
    await expect(
      createInventoryDevice({
        deviceKey: "storage.vsp-01",
        displayName: "Primary VSP",
        deviceType: "storage",
        vendor: "Hitachi Vantara",
        model: "VSP E790",
        serialNumber: "SN-TEST-0001",
        managementAddress: "vsp-01.lab.example",
        purpose: "Register the array for governed inventory and health correlation.",
        scope,
      }),
    ).rejects.toMatchObject({ status: 500 });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(
        device({
          device_id: "inventory-device.other",
          version: 2,
          lifecycle: "retired",
          retired_by: "subject.test",
          retired_at: "2026-08-11T12:10:00Z",
          retirement_reason: "The governed decommissioning workflow has completed.",
        }),
      ),
    );
    await expect(
      retireInventoryDevice({
        device: device(),
        reason: "The governed decommissioning workflow has completed.",
      }),
    ).rejects.toMatchObject({ status: 500 });
  });

  it("fails closed when update or reactivation responses are not request-bound", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(device({ version: 2, display_name: "Unexpected name" })),
    );
    await expect(
      updateInventoryDevice({
        device: device(),
        changes: {
          displayName: "Primary Production VSP",
          deviceType: "storage",
          vendor: "Hitachi Vantara",
          model: "VSP E790",
          serialNumber: "SN-TEST-0001",
          managementAddress: "vsp-01.lab.example",
          purpose: "Register the array for governed inventory and health correlation.",
        },
      }),
    ).rejects.toMatchObject({ status: 500 });

    const retired = device({
      version: 2,
      lifecycle: "retired",
      retired_by: "subject.test",
      retired_at: "2026-08-11T12:10:00Z",
      retirement_reason: "The governed decommissioning workflow has completed.",
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(device({ device_id: "inventory-device.other", version: 3 })),
    );
    await expect(reactivateInventoryDevice({ device: retired })).rejects.toMatchObject({
      status: 500,
    });
  });
});
