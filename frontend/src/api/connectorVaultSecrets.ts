import { ApiRequestError, apiFetch } from "./client";

export type ConnectorVaultSecretReference = {
  secret_reference_id: string;
  updated_at: string;
  set_by_subject_digest: string;
  secret_material_disclosed: false;
};

function responseData(payload: unknown): unknown {
  return payload && typeof payload === "object" && "data" in payload
    ? (payload as { data?: unknown }).data
    : undefined;
}

const stableId = /^[a-z][a-z0-9_.:-]{2,127}$/;

function isReference(value: unknown): value is ConnectorVaultSecretReference {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.secret_reference_id === "string" &&
    stableId.test(record.secret_reference_id) &&
    typeof record.updated_at === "string" &&
    !Number.isNaN(Date.parse(record.updated_at)) &&
    typeof record.set_by_subject_digest === "string" &&
    record.secret_material_disclosed === false
  );
}

/**
 * Sets or rotates one connector vendor's credential in the self-built connector-credential
 * vault (see README.md's "Going to production"). The value is never echoed back -- only vault
 * metadata (when it was last set, never the value itself) is returned.
 */
export async function setConnectorVaultSecret(input: {
  secretReferenceId: string;
  value: string;
}): Promise<ConnectorVaultSecretReference> {
  const response = await apiFetch(
    `/api/v1/connectors/vault-secrets/${encodeURIComponent(input.secretReferenceId)}`,
    {
      method: "PUT",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ value: input.value }),
    },
  );
  if (!response.ok) throw new ApiRequestError("Connector vault secret update failed", response.status);
  const data = responseData(await response.json());
  if (!isReference(data) || data.secret_reference_id !== input.secretReferenceId) {
    throw new Error("Connector vault secret response returned unsafe data");
  }
  return data;
}

export async function listConnectorVaultSecrets(): Promise<ConnectorVaultSecretReference[]> {
  const response = await apiFetch("/api/v1/connectors/vault-secrets", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiRequestError("Connector vault secret list failed", response.status);
  const data = responseData(await response.json());
  if (!Array.isArray(data) || !data.every(isReference)) {
    throw new Error("Connector vault secret list returned unsafe data");
  }
  return data;
}
