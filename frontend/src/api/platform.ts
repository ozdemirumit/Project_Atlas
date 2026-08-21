import { apiFetch } from "./client";

export const ADVISORY_ONLY_CONTRACT_DIGEST =
  "edfde9fc024bab918b587740e23d96e95f8dc3329e8e34f28897dad590c212c1";

export class PlatformPostureViolationError extends Error {
  constructor() {
    super("Platform status response violated the advisory-only contract");
    this.name = "PlatformPostureViolationError";
  }
}

export type ComponentStatus = {
  name: string;
  status: "healthy" | "degraded" | "unavailable" | "disabled";
  required: boolean;
  code: string;
};

export type PlatformStatus = {
  service: string;
  version: string;
  environment: string;
  status: "healthy" | "degraded" | "unavailable";
  components: ComponentStatus[];
  warnings: string[];
  operational_posture: AdvisoryOnlyPosture;
};

export type AdvisoryOnlyPosture = {
  contract_id: "platform-posture.advisory-only";
  contract_version: "1.0.0";
  platform_mode: "advisory_only";
  operational_execution_enabled: false;
  process_resume_consumption_enabled: false;
  dispatch_enabled: false;
  infrastructure_mutation_enabled: false;
  ai_execution_authorized: false;
  contract_digest: string;
};

type PlatformStatusResponse = {
  data: PlatformStatus;
  meta: {
    correlation_id: string;
    generated_at: string;
  };
};

export async function getPlatformStatus(): Promise<PlatformStatusResponse> {
  const response = await apiFetch("/api/v1/platform/status", {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Platform status request failed with ${response.status}`);
  }

  const payload: unknown = await response.json();
  if (!isPlatformStatusResponse(payload)) {
    throw new PlatformPostureViolationError();
  }
  return payload;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isAdvisoryOnlyPosture(value: unknown): value is AdvisoryOnlyPosture {
  return (
    isObject(value) &&
    value.contract_id === "platform-posture.advisory-only" &&
    value.contract_version === "1.0.0" &&
    value.platform_mode === "advisory_only" &&
    value.operational_execution_enabled === false &&
    value.process_resume_consumption_enabled === false &&
    value.dispatch_enabled === false &&
    value.infrastructure_mutation_enabled === false &&
    value.ai_execution_authorized === false &&
    value.contract_digest === ADVISORY_ONLY_CONTRACT_DIGEST
  );
}

function isComponentStatus(value: unknown): value is ComponentStatus {
  return (
    isObject(value) &&
    typeof value.name === "string" &&
    ["healthy", "degraded", "unavailable", "disabled"].includes(String(value.status)) &&
    typeof value.required === "boolean" &&
    typeof value.code === "string"
  );
}

function isPlatformStatusResponse(value: unknown): value is PlatformStatusResponse {
  if (!isObject(value) || !isObject(value.data) || !isObject(value.meta)) return false;
  const { data, meta } = value;
  return (
    typeof data.service === "string" &&
    typeof data.version === "string" &&
    typeof data.environment === "string" &&
    ["healthy", "degraded", "unavailable"].includes(String(data.status)) &&
    Array.isArray(data.components) &&
    data.components.every(isComponentStatus) &&
    Array.isArray(data.warnings) &&
    data.warnings.every((warning) => typeof warning === "string") &&
    isAdvisoryOnlyPosture(data.operational_posture) &&
    typeof meta.correlation_id === "string" &&
    typeof meta.generated_at === "string"
  );
}
