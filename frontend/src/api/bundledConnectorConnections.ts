import { ApiRequestError, apiFetch } from "./client";

export const HITACHI_BUNDLED_CONNECTOR_ID =
  "connector.hitachi.opscenter.configuration-manager";
export const HITACHI_SYSTEM_CA_TRUST_PROFILE = "trust.system-ca";
export const HITACHI_AUTHORIZATION_SECRET_REFERENCE =
  "secret.hitachi.readonly";

export type BundledConnectionConfiguration = {
  configuration_id: string;
  connector_id: string;
  instance_id: string;
  hostname: string;
  port: number;
  trust_profile_id: string;
  secret_reference_id: string;
  configured_at: string;
  protocol: "https";
  development_only: true;
  secret_material_stored: false;
  infrastructure_mutation_performed: false;
};

export type ConnectorConnectionTestResult = {
  test_id: string;
  connector_id: string;
  instance_id: string;
  outcome: "passed" | "failed";
  result_code: string;
  retryable: boolean;
  checked_at: string;
  duration_ms: number;
  read_only_request_performed: boolean;
  target_details_disclosed: false;
  secret_material_disclosed: false;
  managed_infrastructure_contacted: boolean;
  infrastructure_mutation_performed: false;
};

export type BundledConnectorRuntimeState = {
  instance_id: string;
  state: "disabled" | "enabled_read_only";
  version: number;
  changed_at: string | null;
  changed_by: string | null;
  reason: string | null;
  managed_infrastructure_contacted: false;
  infrastructure_mutation_performed: false;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;

function responseData(payload: unknown): unknown {
  return payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
}

function isConfiguration(value: unknown): value is BundledConnectionConfiguration {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return ["configuration_id", "connector_id", "instance_id", "trust_profile_id", "secret_reference_id"]
    .every((key) => typeof record[key] === "string" && stableId.test(record[key])) &&
    typeof record.hostname === "string" && record.hostname.length > 0 &&
    typeof record.port === "number" && record.port >= 1 && record.port <= 65_535 &&
    typeof record.configured_at === "string" && !Number.isNaN(Date.parse(record.configured_at)) &&
    record.protocol === "https" && record.development_only === true &&
    record.secret_material_stored === false && record.infrastructure_mutation_performed === false;
}

function isConnectionTest(value: unknown): value is ConnectorConnectionTestResult {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return ["test_id", "connector_id", "instance_id", "result_code"]
    .every((key) => typeof record[key] === "string" && stableId.test(record[key])) &&
    (record.outcome === "passed" || record.outcome === "failed") &&
    typeof record.retryable === "boolean" &&
    typeof record.checked_at === "string" && !Number.isNaN(Date.parse(record.checked_at)) &&
    typeof record.duration_ms === "number" && record.duration_ms >= 0 &&
    typeof record.read_only_request_performed === "boolean" &&
    record.target_details_disclosed === false && record.secret_material_disclosed === false &&
    typeof record.managed_infrastructure_contacted === "boolean" &&
    record.infrastructure_mutation_performed === false;
}

function isRuntimeState(value: unknown): value is BundledConnectorRuntimeState {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.instance_id === "string" && stableId.test(record.instance_id) &&
    (record.state === "disabled" || record.state === "enabled_read_only") &&
    typeof record.version === "number" && Number.isInteger(record.version) && record.version >= 0 &&
    (record.changed_at === null ||
      (typeof record.changed_at === "string" && !Number.isNaN(Date.parse(record.changed_at)))) &&
    (record.changed_by === null || typeof record.changed_by === "string") &&
    (record.reason === null || typeof record.reason === "string") &&
    record.managed_infrastructure_contacted === false &&
    record.infrastructure_mutation_performed === false;
}

function configurationPath(instanceId: string): string {
  return `/api/v1/connectors/bundled-instances/${encodeURIComponent(instanceId)}/connection-configuration`;
}

export async function getBundledConnectionConfiguration(
  instanceId: string,
): Promise<BundledConnectionConfiguration | null> {
  const response = await apiFetch(configurationPath(instanceId), {
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new ApiRequestError("Connection configuration failed", response.status);
  const data = responseData(await response.json());
  if (!isConfiguration(data) || data.instance_id !== instanceId) {
    throw new Error("Connection configuration returned unsafe data");
  }
  return data;
}

export async function saveBundledConnectionConfiguration(input: {
  instanceId: string;
  hostname: string;
  port: number;
  secretReferenceId: string;
}): Promise<BundledConnectionConfiguration> {
  const response = await apiFetch(configurationPath(input.instanceId), {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      hostname: input.hostname.trim().toLowerCase(),
      port: input.port,
      trust_profile_id: HITACHI_SYSTEM_CA_TRUST_PROFILE,
      secret_reference_id: input.secretReferenceId.trim().toLowerCase(),
    }),
  });
  if (!response.ok) throw new ApiRequestError("Connection configuration failed", response.status);
  const data = responseData(await response.json());
  if (!isConfiguration(data) || data.instance_id !== input.instanceId) {
    throw new Error("Connection configuration returned unsafe data");
  }
  return data;
}

export async function testBundledConnectorConnection(
  instanceId: string,
): Promise<ConnectorConnectionTestResult> {
  const response = await apiFetch(
    `/api/v1/connectors/bundled-instances/${encodeURIComponent(instanceId)}/connection-tests`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new ApiRequestError("Connection test failed", response.status);
  const data = responseData(await response.json());
  if (!isConnectionTest(data) || data.instance_id !== instanceId) {
    throw new Error("Connection test returned unsafe data");
  }
  return data;
}

export async function getLatestBundledConnectorConnectionTest(
  instanceId: string,
): Promise<ConnectorConnectionTestResult | null> {
  const response = await apiFetch(
    `/api/v1/connectors/bundled-instances/${encodeURIComponent(instanceId)}/connection-tests/latest`,
    { headers: { Accept: "application/json" } },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new ApiRequestError("Latest connection test failed", response.status);
  const data = responseData(await response.json());
  if (!isConnectionTest(data) || data.instance_id !== instanceId) {
    throw new Error("Latest connection test returned unsafe data");
  }
  return data;
}

function runtimePath(instanceId: string, operation?: "enable" | "disable"): string {
  const base = `/api/v1/connectors/bundled-instances/${encodeURIComponent(instanceId)}`;
  return operation ? `${base}/${operation}` : `${base}/runtime-state`;
}

async function runtimeStateResponse(
  response: Response,
  instanceId: string,
  errorMessage: string,
): Promise<BundledConnectorRuntimeState> {
  if (!response.ok) throw new ApiRequestError(errorMessage, response.status);
  const data = responseData(await response.json());
  if (!isRuntimeState(data) || data.instance_id !== instanceId) {
    throw new Error("Bundled MCP runtime state returned unsafe data");
  }
  return data;
}

export async function getBundledConnectorRuntimeState(
  instanceId: string,
): Promise<BundledConnectorRuntimeState> {
  const response = await apiFetch(runtimePath(instanceId), {
    headers: { Accept: "application/json" },
  });
  return runtimeStateResponse(response, instanceId, "Bundled MCP runtime state failed");
}

export async function enableBundledConnectorRuntime(
  instanceId: string,
): Promise<BundledConnectorRuntimeState> {
  const response = await apiFetch(runtimePath(instanceId, "enable"), {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ acknowledged_read_only_operation: true }),
  });
  return runtimeStateResponse(response, instanceId, "Bundled MCP enable failed");
}

export async function disableBundledConnectorRuntime(input: {
  instanceId: string;
  reason: string;
}): Promise<BundledConnectorRuntimeState> {
  const response = await apiFetch(runtimePath(input.instanceId, "disable"), {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      reason: input.reason.trim(),
      acknowledged_runtime_stop: true,
    }),
  });
  return runtimeStateResponse(response, input.instanceId, "Bundled MCP disable failed");
}
