import { ApiRequestError, apiFetch } from "./client";

export type InventoryDeviceType =
  | "storage"
  | "san_switch"
  | "virtualization"
  | "server"
  | "backup"
  | "network"
  | "other";

export type InventoryDeviceLifecycle = "active" | "retired";

export type InventoryDevice = {
  device_id: string;
  schema_version: "atlas.inventory-device-record.v1";
  version: number;
  organization_id: string;
  environment_id: string;
  site_id: string;
  device_key: string;
  display_name: string;
  device_type: InventoryDeviceType;
  vendor: string;
  model: string;
  serial_number: string | null;
  management_address: string | null;
  source: "manual";
  lifecycle: InventoryDeviceLifecycle;
  purpose: string;
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  retired_by: string | null;
  retired_at: string | null;
  retirement_reason: string | null;
  canonical_digest: string;
  reused: boolean;
};

export type InventoryDeviceInventory = {
  devices: InventoryDevice[];
  durable: boolean;
  truncated: boolean;
};

const deviceTypes = new Set<InventoryDeviceType>([
  "storage",
  "san_switch",
  "virtualization",
  "server",
  "backup",
  "network",
  "other",
]);

function isInventoryDevice(value: unknown): value is InventoryDevice {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    record.schema_version === "atlas.inventory-device-record.v1" &&
    typeof record.device_id === "string" &&
    typeof record.version === "number" &&
    typeof record.device_key === "string" &&
    typeof record.display_name === "string" &&
    deviceTypes.has(record.device_type as InventoryDeviceType) &&
    (record.lifecycle === "active" || record.lifecycle === "retired") &&
    typeof record.canonical_digest === "string" &&
    /^[a-f0-9]{64}$/.test(record.canonical_digest) &&
    !(
      "create_idempotency_key" in record ||
      "retirement_idempotency_key" in record ||
      "request_fingerprint" in record ||
      "credential" in record ||
      "password" in record
    )
  );
}

function readDeviceResponse(value: unknown): InventoryDevice {
  if (!value || typeof value !== "object" || !("data" in value)) {
    throw new ApiRequestError("Inventory device response was malformed", 500);
  }
  const data = value.data;
  if (!isInventoryDevice(data)) {
    throw new ApiRequestError("Inventory device response was unsafe", 500);
  }
  return data;
}

export async function getInventoryDevices(input: {
  lifecycle: InventoryDeviceLifecycle | "all";
  query: string;
}): Promise<InventoryDeviceInventory> {
  const parameters = new URLSearchParams({ limit: "100" });
  if (input.lifecycle !== "all") parameters.set("lifecycle", input.lifecycle);
  if (input.query.trim()) parameters.set("query", input.query.trim());
  const response = await apiFetch(`/api/v1/inventory/devices?${parameters.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Inventory device list failed", response.status);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object" || !("data" in payload)) {
    throw new ApiRequestError("Inventory device list was malformed", response.status);
  }
  const data = payload.data;
  if (!data || typeof data !== "object") {
    throw new ApiRequestError("Inventory device list was malformed", response.status);
  }
  const inventory = data as Record<string, unknown>;
  if (
    !Array.isArray(inventory.devices) ||
    !inventory.devices.every(isInventoryDevice) ||
    typeof inventory.durable !== "boolean" ||
    typeof inventory.truncated !== "boolean"
  ) {
    throw new ApiRequestError("Inventory device list was unsafe", response.status);
  }
  return inventory as InventoryDeviceInventory;
}

export async function createInventoryDevice(input: {
  deviceKey: string;
  displayName: string;
  deviceType: InventoryDeviceType;
  vendor: string;
  model: string;
  serialNumber: string;
  managementAddress: string;
  purpose: string;
}): Promise<InventoryDevice> {
  const response = await apiFetch("/api/v1/inventory/devices", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `inventory-device-create.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.inventory-device-create-input.v1",
      device_key: input.deviceKey.trim().toLowerCase(),
      display_name: input.displayName.trim(),
      device_type: input.deviceType,
      vendor: input.vendor.trim(),
      model: input.model.trim(),
      serial_number: input.serialNumber.trim() || null,
      management_address: input.managementAddress.trim().toLowerCase() || null,
      purpose: input.purpose.trim(),
      acknowledged_no_credentials_or_infrastructure_action: true,
    }),
  });
  if (!response.ok) throw new ApiRequestError("Inventory device creation failed", response.status);
  return readDeviceResponse(await response.json());
}

export async function retireInventoryDevice(input: {
  device: InventoryDevice;
  reason: string;
}): Promise<InventoryDevice> {
  const response = await apiFetch(
    `/api/v1/inventory/devices/${encodeURIComponent(input.device.device_id)}/retirements`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `inventory-device-retire.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.inventory-device-retirement-input.v1",
        expected_version: input.device.version,
        reason: input.reason.trim(),
        acknowledged_retirement_preserves_history_and_stops_active_use: true,
      }),
    },
  );
  if (!response.ok) throw new ApiRequestError("Inventory device retirement failed", response.status);
  return readDeviceResponse(await response.json());
}
