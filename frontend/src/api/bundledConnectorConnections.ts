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
}): Promise<BundledConnectionConfiguration> {
  const response = await apiFetch(configurationPath(input.instanceId), {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      hostname: input.hostname.trim().toLowerCase(),
      port: input.port,
      trust_profile_id: HITACHI_SYSTEM_CA_TRUST_PROFILE,
      secret_reference_id: HITACHI_AUTHORIZATION_SECRET_REFERENCE,
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
