import { ApiRequestError, apiFetch } from "./client";
import type { ConnectorRuntimeActivationInventoryItem } from "./runtimeActivations";

export type ConnectorRuntimeDeactivation = {
  deactivation_id: string;
  activation_id: string;
  activation_version: 1;
  connector_id: string;
  instance_id: string;
  effective_runtime_state: "disabled_runtime";
  deactivated_by: string;
  reason: string;
  deactivated_at: string;
  atlas_runtime_disabled: true;
  target_authority_revoked: true;
  managed_infrastructure_contacted: false;
  infrastructure_mutation_performed: false;
  reused: boolean;
};

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;
const fields = new Set([
  "deactivation_id",
  "activation_id",
  "activation_version",
  "connector_id",
  "instance_id",
  "effective_runtime_state",
  "deactivated_by",
  "reason",
  "deactivated_at",
  "atlas_runtime_disabled",
  "target_authority_revoked",
  "managed_infrastructure_contacted",
  "infrastructure_mutation_performed",
  "reused",
]);

function isDeactivation(value: unknown): value is ConnectorRuntimeDeactivation {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  return keys.length === fields.size && keys.every((key) => fields.has(key)) &&
    ["deactivation_id", "activation_id", "connector_id", "instance_id", "deactivated_by"]
      .every((key) => typeof record[key] === "string" && stableId.test(record[key])) &&
    record.activation_version === 1 &&
    record.effective_runtime_state === "disabled_runtime" &&
    typeof record.reason === "string" && record.reason.trim().length >= 20 &&
    record.reason.length <= 1000 &&
    typeof record.deactivated_at === "string" &&
    !Number.isNaN(Date.parse(record.deactivated_at)) &&
    record.atlas_runtime_disabled === true &&
    record.target_authority_revoked === true &&
    record.managed_infrastructure_contacted === false &&
    record.infrastructure_mutation_performed === false &&
    typeof record.reused === "boolean";
}

export async function getConnectorRuntimeDeactivations(): Promise<
  ConnectorRuntimeDeactivation[]
> {
  const response = await apiFetch("/api/v1/connectors/runtime-activations/deactivations", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiRequestError("Runtime deactivation inventory failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (!Array.isArray(data) || !data.every(isDeactivation)) {
    throw new Error("Runtime deactivation inventory returned unsafe records");
  }
  return data;
}

export async function deactivateConnectorRuntime(input: {
  activation: ConnectorRuntimeActivationInventoryItem;
  reason: string;
}): Promise<ConnectorRuntimeDeactivation> {
  const reason = input.reason.trim();
  if (reason.length < 20 || reason.length > 1000) {
    throw new Error("A bounded runtime deactivation reason is required");
  }
  const response = await apiFetch(
    `/api/v1/connectors/runtime-activations/${encodeURIComponent(input.activation.activation_id)}/deactivations`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `connector-runtime-deactivation.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.connector-runtime-deactivation-input.v1",
        expected_activation_version: 1,
        reason,
        acknowledged_runtime_only_deactivation: true,
      }),
    },
  );
  if (!response.ok) {
    throw new ApiRequestError("Runtime deactivation failed", response.status);
  }
  const payload: unknown = await response.json();
  const data = payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
  if (
    !isDeactivation(data) ||
    data.activation_id !== input.activation.activation_id ||
    data.connector_id !== input.activation.connector_id ||
    data.instance_id !== input.activation.instance_id
  ) {
    throw new Error("Runtime deactivation did not match the selected activation");
  }
  return data;
}
