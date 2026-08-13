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

export type InventoryDeviceScope = {
  organizationId: string;
  environmentId: string;
  siteId: string;
};

export type InventoryDeviceCreateInput = {
  deviceKey: string;
  displayName: string;
  deviceType: InventoryDeviceType;
  vendor: string;
  model: string;
  serialNumber: string;
  managementAddress: string;
  purpose: string;
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

const stableIdentifier = /^[a-z][a-z0-9_.:-]{2,127}$/;
const canonicalDigest = /^[a-f0-9]{64}$/;
const inventoryDeviceFields = new Set([
  "device_id",
  "schema_version",
  "version",
  "organization_id",
  "environment_id",
  "site_id",
  "device_key",
  "display_name",
  "device_type",
  "vendor",
  "model",
  "serial_number",
  "management_address",
  "source",
  "lifecycle",
  "purpose",
  "created_by",
  "created_at",
  "updated_by",
  "updated_at",
  "retired_by",
  "retired_at",
  "retirement_reason",
  "canonical_digest",
  "reused",
]);

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isNonEmptyString(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isInventoryDevice(value: unknown): value is InventoryDevice {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  const active = record.lifecycle === "active";
  const retired = record.lifecycle === "retired";
  return (
    record.schema_version === "atlas.inventory-device-record.v1" &&
    typeof record.device_id === "string" &&
    stableIdentifier.test(record.device_id) &&
    Number.isInteger(record.version) &&
    Number(record.version) >= 1 &&
    typeof record.organization_id === "string" &&
    stableIdentifier.test(record.organization_id) &&
    typeof record.environment_id === "string" &&
    stableIdentifier.test(record.environment_id) &&
    typeof record.site_id === "string" &&
    stableIdentifier.test(record.site_id) &&
    typeof record.device_key === "string" &&
    stableIdentifier.test(record.device_key) &&
    isNonEmptyString(record.display_name) &&
    deviceTypes.has(record.device_type as InventoryDeviceType) &&
    isNonEmptyString(record.vendor) &&
    isNonEmptyString(record.model) &&
    isNullableString(record.serial_number) &&
    isNullableString(record.management_address) &&
    record.source === "manual" &&
    (active || retired) &&
    isNonEmptyString(record.purpose) &&
    typeof record.created_by === "string" &&
    stableIdentifier.test(record.created_by) &&
    isTimestamp(record.created_at) &&
    typeof record.updated_by === "string" &&
    stableIdentifier.test(record.updated_by) &&
    isTimestamp(record.updated_at) &&
    (active
      ? record.retired_by === null &&
        record.retired_at === null &&
        record.retirement_reason === null
      : typeof record.retired_by === "string" &&
        stableIdentifier.test(record.retired_by) &&
        isTimestamp(record.retired_at) &&
        isNonEmptyString(record.retirement_reason)) &&
    typeof record.canonical_digest === "string" &&
    canonicalDigest.test(record.canonical_digest) &&
    typeof record.reused === "boolean" &&
    Object.keys(record).every((field) => inventoryDeviceFields.has(field))
  );
}

function hasScope(device: InventoryDevice, scope: InventoryDeviceScope): boolean {
  return (
    device.organization_id === scope.organizationId &&
    device.environment_id === scope.environmentId &&
    device.site_id === scope.siteId
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
  scope: InventoryDeviceScope;
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
    !inventory.devices.every(
      (device) =>
        hasScope(device, input.scope) &&
        (input.lifecycle === "all" || device.lifecycle === input.lifecycle),
    ) ||
    typeof inventory.durable !== "boolean" ||
    typeof inventory.truncated !== "boolean" ||
    !Object.keys(inventory).every((field) =>
      ["devices", "durable", "truncated"].includes(field),
    )
  ) {
    throw new ApiRequestError("Inventory device list was unsafe", response.status);
  }
  return inventory as InventoryDeviceInventory;
}

export async function createInventoryDevice(
  input: InventoryDeviceCreateInput & { scope: InventoryDeviceScope },
): Promise<InventoryDevice> {
  const expectedDeviceKey = input.deviceKey.trim().toLowerCase();
  const response = await apiFetch("/api/v1/inventory/devices", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `inventory-device-create.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.inventory-device-create-input.v1",
      device_key: expectedDeviceKey,
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
  const device = readDeviceResponse(await response.json());
  if (
    !hasScope(device, input.scope) ||
    device.device_key !== expectedDeviceKey ||
    device.lifecycle !== "active"
  ) {
    throw new ApiRequestError("Inventory device creation response was not bound", 500);
  }
  return device;
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
  const retired = readDeviceResponse(await response.json());
  if (
    retired.device_id !== input.device.device_id ||
    retired.device_key !== input.device.device_key ||
    retired.organization_id !== input.device.organization_id ||
    retired.environment_id !== input.device.environment_id ||
    retired.site_id !== input.device.site_id ||
    retired.version !== input.device.version + 1 ||
    retired.lifecycle !== "retired"
  ) {
    throw new ApiRequestError("Inventory device retirement response was not bound", 500);
  }
  return retired;
}
