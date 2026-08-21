const configuredCsrfCookieName: unknown = import.meta.env.VITE_ATLAS_CSRF_COOKIE_NAME;
const configuredCsrfHeaderName: unknown = import.meta.env.VITE_ATLAS_CSRF_HEADER_NAME;
const CSRF_COOKIE_NAME =
  typeof configuredCsrfCookieName === "string" ? configuredCsrfCookieName : "atlas_csrf";
const CSRF_HEADER_NAME =
  typeof configuredCsrfHeaderName === "string" ? configuredCsrfHeaderName : "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function readCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const item of document.cookie.split(";")) {
    const candidate = item.trim();
    if (candidate.startsWith(prefix)) {
      return decodeURIComponent(candidate.slice(prefix.length));
    }
  }
  return null;
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const requestUrl = input instanceof Request ? input.url : input.toString();
  const resolvedUrl = new URL(requestUrl, window.location.origin);
  if (resolvedUrl.origin !== window.location.origin) {
    throw new ApiRequestError("Cross-origin API requests are not allowed", 0);
  }
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
  }
  return fetch(input, { ...init, credentials: "same-origin", headers });
}

const processSchedulingAuthorityFields = [
  "protected_runtime_process_scheduling_authority_granted",
  "protected_runtime_process_creation_authority_granted",
  "protected_runtime_readiness_authority_granted",
  "protected_runtime_start_authority_granted",
  "protected_runtime_context_use_authority_granted",
  "runtime_use_authorized",
  "runtime_start_authorized",
  "runtime_resume_authorized",
  "connector_activity_authorized",
  "protected_runtime_context_injection_authority_granted",
  "protected_resident_context_access_authority_granted",
  "target_context_capsule_opening_authorized",
  "target_context_capsule_handoff_authorized",
  "endpoint_resolution_authorized",
  "route_selection_authorized",
  "route_binding_authorized",
  "credential_selection_authorized",
  "credential_assignment_binding_authorized",
  "credential_access_authorized",
  "credential_brokerage_authorized",
  "credential_resolution_authorized",
  "protected_artifact_access_authorized",
  "credential_delivery_authorized",
  "network_access_authorized",
  "readiness_probe_authorized",
  "publication_authorized",
  "delivery_authorized",
  "dispatch_authorized",
  "execution_authorized",
  "infrastructure_mutation_authorized",
] as const;

type ProcessSchedulingAuthorityField = (typeof processSchedulingAuthorityFields)[number];

export type WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority = Record<
  ProcessSchedulingAuthorityField,
  boolean
>;

export type WorkflowProtectedRuntimeProcessSchedulingAuthorization = {
  authorization_lease_id: string;
  process_creation_result_reference: string;
  state: "authorized_unconsumed";
  effective_state: "active" | "expired";
  issued_at: string;
  valid_until: string;
  effective_until: string;
  consumer_contract_id: "contract.workflow-protected-transport-target-context-capsule-consumer";
  consumer_contract_version: "1.0";
  purpose_id: "purpose.workflow-protected-runtime-process-scheduling-request";
  policy_id: "policy.workflow-protected-runtime-process-scheduling-authorization";
  policy_version: "1.0";
  authority: WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority;
  integrity_reference: string;
};

export type WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventory = {
  authorizations: WorkflowProtectedRuntimeProcessSchedulingAuthorization[];
  server_time: string;
  durable: true;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === keys.length && actual.every((key) => keys.includes(key));
}

function isStableIdentifier(value: unknown): value is string {
  return typeof value === "string" && /^[a-z][a-z0-9_.:-]{2,239}$/.test(value);
}

function isAwareTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isSchedulingRequestOnlyAuthority(
  value: unknown,
  granted: boolean,
): value is WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority {
  return (
    isRecord(value) &&
    hasOnlyKeys(value, processSchedulingAuthorityFields) &&
    processSchedulingAuthorityFields.every((field) =>
      field === "protected_runtime_process_scheduling_authority_granted"
        ? value[field] === granted
        : value[field] === false,
    )
  );
}

function isSchedulingAuthorization(
  value: unknown,
  serverTime: string,
): value is WorkflowProtectedRuntimeProcessSchedulingAuthorization {
  const fields = [
    "authorization_lease_id",
    "process_creation_result_reference",
    "state",
    "effective_state",
    "issued_at",
    "valid_until",
    "effective_until",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
    "authority",
    "integrity_reference",
  ] as const;
  if (
    !isRecord(value) ||
    !hasOnlyKeys(value, fields) ||
    !isAwareTimestamp(value.issued_at) ||
    !isAwareTimestamp(value.valid_until) ||
    !isAwareTimestamp(value.effective_until)
  ) {
    return false;
  }
  const issuedAt = Date.parse(value.issued_at);
  const validUntil = Date.parse(value.valid_until);
  const effectiveUntil = Date.parse(value.effective_until);
  const evaluatedAt = Date.parse(serverTime);
  const effectiveState = evaluatedAt >= effectiveUntil ? "expired" : "active";
  return (
    isStableIdentifier(value.authorization_lease_id) &&
    value.authorization_lease_id.startsWith(
      "workflow-protected-runtime-process-scheduling-authorization-lease.",
    ) &&
    isStableIdentifier(value.process_creation_result_reference) &&
    value.process_creation_result_reference.startsWith(
      "integrity.workflow-protected-runtime-process-creation-result.",
    ) &&
    value.state === "authorized_unconsumed" &&
    value.effective_state === effectiveState &&
    issuedAt <= evaluatedAt &&
    issuedAt < validUntil &&
    validUntil - issuedAt <= 1_000 &&
    effectiveUntil === validUntil &&
    value.consumer_contract_id ===
      "contract.workflow-protected-transport-target-context-capsule-consumer" &&
    value.consumer_contract_version === "1.0" &&
    value.purpose_id === "purpose.workflow-protected-runtime-process-scheduling-request" &&
    value.policy_id ===
      "policy.workflow-protected-runtime-process-scheduling-authorization" &&
    value.policy_version === "1.0" &&
    isSchedulingRequestOnlyAuthority(value.authority, effectiveState === "active") &&
    isStableIdentifier(value.integrity_reference) &&
    value.integrity_reference.startsWith(
      "integrity.workflow-protected-runtime-process-scheduling-authorization.",
    )
  );
}

export async function listWorkflowProtectedRuntimeProcessSchedulingAuthorizations(): Promise<WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventory> {
  const response = await apiFetch(
    "/api/v1/workflows/protected-runtime-process-scheduling-authorizations",
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw new ApiRequestError(
      "Workflow protected runtime process-scheduling authorization retrieval failed",
      response.status,
    );
  }
  const envelope: unknown = await response.json();
  if (!isRecord(envelope) || !isRecord(envelope.data)) {
    throw new ApiRequestError(
      "Workflow protected runtime process-scheduling authorization response was unsafe",
      response.status,
    );
  }
  const data = envelope.data;
  if (
    !hasOnlyKeys(data, ["authorizations", "server_time", "durable"]) ||
    !Array.isArray(data.authorizations) ||
    data.authorizations.length > 256 ||
    !isAwareTimestamp(data.server_time) ||
    data.durable !== true ||
    !data.authorizations.every((authorization) =>
      isSchedulingAuthorization(authorization, data.server_time as string),
    )
  ) {
    throw new ApiRequestError(
      "Workflow protected runtime process-scheduling authorization response was unsafe",
      response.status,
    );
  }
  const ids = new Set<string>();
  for (const authorization of data.authorizations) {
    if (
      !isRecord(authorization) ||
      typeof authorization.authorization_lease_id !== "string" ||
      ids.has(authorization.authorization_lease_id)
    ) {
      throw new ApiRequestError(
        "Workflow protected runtime process-scheduling authorization response was unsafe",
        response.status,
      );
    }
    ids.add(authorization.authorization_lease_id);
  }
  return data as WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventory;
}
