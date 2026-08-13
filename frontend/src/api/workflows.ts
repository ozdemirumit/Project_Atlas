import { ApiRequestError, apiFetch } from "./client";

export const WORKFLOW_PLAN_SAFETY_NOTICE =
  "Planning only. This record cannot dispatch workers, invoke connectors, create approvals, mutate ITSM, execute runbooks, or change infrastructure.";

export type WorkflowCapabilityClass = "C0" | "C1" | "C2";
export type WorkflowStepKind =
  | "evidence_query"
  | "health_assessment"
  | "report_generation";

export type WorkflowScope = {
  organizationId: string;
  environmentId: string;
  siteId: string;
};

export type WorkflowStepDefinition = {
  step_id: string;
  ordinal: number;
  title: string;
  kind: WorkflowStepKind;
  capability_class: WorkflowCapabilityClass;
  timeout_seconds: number;
  depends_on: string[];
};

export type WorkflowDefinition = {
  definition_id: string;
  version: number;
  title: string;
  purpose: string;
  input_schema_version: string;
  definition_digest: string;
  steps: WorkflowStepDefinition[];
};

export type WorkflowPlanAuthority = {
  worker_dispatch_authorized: false;
  connector_invocation_authorized: false;
  approval_creation_authorized: false;
  signal_delivery_authorized: false;
  retry_authorized: false;
  itsm_mutation_authorized: false;
  runbook_execution_authorized: false;
  infrastructure_change_authorized: false;
};

export type WorkflowPlanStep = {
  step_id: string;
  ordinal: number;
  kind: WorkflowStepKind;
  capability_class: WorkflowCapabilityClass;
  state: "not_started";
};

export type WorkflowPlanTransition = {
  transition_id: string;
  prior_state: "planned";
  new_state: "cancelled";
  actor_subject_id: string;
  scope: {
    organization_id: string;
    environment_id: string;
    site_id: string;
  };
  target_id: string;
  target_type: "storage";
  reason: string;
  reason_digest: string;
  correlation_id: string;
  occurred_at: string;
  canonical_digest: string;
};

export type WorkflowRunPlan = {
  plan_id: string;
  definition_id: string;
  definition_version: number;
  definition_digest: string;
  scope: {
    organization_id: string;
    environment_id: string;
    site_id: string;
  };
  target_id: string;
  target_type: "storage";
  canonical_input_digest: string;
  creator_subject_id: string;
  created_at: string;
  state: "planned" | "cancelled";
  steps: WorkflowPlanStep[];
  durable: boolean;
  authority: WorkflowPlanAuthority;
  safety_notice: typeof WORKFLOW_PLAN_SAFETY_NOTICE;
  canonical_digest: string;
  transition_history: WorkflowPlanTransition[];
};

export type WorkflowDefinitionInventory = {
  definitions: WorkflowDefinition[];
};

export type WorkflowPlanInventory = {
  plans: WorkflowRunPlan[];
  durable: boolean;
  truncated: boolean;
};

export type WorkflowOrchestrationLeaseEffectiveState = "active" | "expired" | "released";

export type WorkflowOrchestrationLease = {
  lease_id: string;
  plan_id: string;
  plan_digest: string;
  scope: WorkflowRunPlan["scope"];
  target_id: string;
  target_type: "storage";
  worker_subject_id: string;
  acquired_at: string;
  last_heartbeat_at: string;
  expires_at: string;
  fencing_token: number;
  state: "active" | "released";
  effective_state: WorkflowOrchestrationLeaseEffectiveState;
  canonical_digest: string;
  grants_execution_authority: false;
};

export type WorkflowOrchestrationLeaseStatus = {
  plan_id: string;
  server_time: string;
  durable: boolean;
  lease: WorkflowOrchestrationLease | null;
};

const digest = /^[a-f0-9]{64}$/;
const capabilityClasses = new Set<WorkflowCapabilityClass>(["C0", "C1", "C2"]);
const stepKinds = new Set<WorkflowStepKind>([
  "evidence_query",
  "health_assessment",
  "report_generation",
]);
const authorityFields = [
  "worker_dispatch_authorized",
  "connector_invocation_authorized",
  "approval_creation_authorized",
  "signal_delivery_authorized",
  "retry_authorized",
  "itsm_mutation_authorized",
  "runbook_execution_authorized",
  "infrastructure_change_authorized",
] as const;

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 240 && !/\s/.test(value);
}

function isText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= maximum;
}

function isDigest(value: unknown): value is string {
  return typeof value === "string" && digest.test(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isScope(value: unknown): value is WorkflowRunPlan["scope"] {
  return (
    isObject(value) &&
    isIdentifier(value.organization_id) &&
    isIdentifier(value.environment_id) &&
    isIdentifier(value.site_id)
  );
}

function isCapabilityClass(value: unknown): value is WorkflowCapabilityClass {
  return capabilityClasses.has(value as WorkflowCapabilityClass);
}

function isStepKind(value: unknown): value is WorkflowStepKind {
  return stepKinds.has(value as WorkflowStepKind);
}

function isDefinitionStep(value: unknown, index: number): value is WorkflowStepDefinition {
  if (!isObject(value)) return false;
  return (
    isIdentifier(value.step_id) &&
    value.ordinal === index + 1 &&
    isText(value.title, 120) &&
    isStepKind(value.kind) &&
    isCapabilityClass(value.capability_class) &&
    Number.isInteger(value.timeout_seconds) &&
    Number(value.timeout_seconds) >= 1 &&
    Number(value.timeout_seconds) <= 3_600 &&
    Array.isArray(value.depends_on) &&
    value.depends_on.every(isIdentifier)
  );
}

function isDefinition(value: unknown): value is WorkflowDefinition {
  if (!isObject(value) || !Array.isArray(value.steps) || value.steps.length < 1) return false;
  const stepsValid = value.steps.every(isDefinitionStep);
  const seen = new Set(value.steps.map((step) => (isObject(step) ? step.step_id : undefined)));
  return (
    isIdentifier(value.definition_id) &&
    Number.isInteger(value.version) &&
    Number(value.version) >= 1 &&
    isText(value.title, 120) &&
    isText(value.purpose, 500) &&
    isIdentifier(value.input_schema_version) &&
    isDigest(value.definition_digest) &&
    stepsValid &&
    seen.size === value.steps.length
  );
}

function hasSafeAuthority(value: unknown): value is WorkflowPlanAuthority {
  if (!isObject(value)) return false;
  return (
    Object.keys(value).length === authorityFields.length &&
    authorityFields.every((field) => value[field] === false)
  );
}

function isPlanStep(value: unknown, index: number): value is WorkflowPlanStep {
  return (
    isObject(value) &&
    isIdentifier(value.step_id) &&
    value.ordinal === index + 1 &&
    isStepKind(value.kind) &&
    isCapabilityClass(value.capability_class) &&
    value.state === "not_started"
  );
}

function isTransition(
  value: unknown,
  planScope: WorkflowRunPlan["scope"],
  targetId: string,
): value is WorkflowPlanTransition {
  if (!isObject(value) || !isObject(value.scope)) return false;
  return (
    isIdentifier(value.transition_id) &&
    value.prior_state === "planned" &&
    value.new_state === "cancelled" &&
    isIdentifier(value.actor_subject_id) &&
    value.scope.organization_id === planScope.organization_id &&
    value.scope.environment_id === planScope.environment_id &&
    value.scope.site_id === planScope.site_id &&
    value.target_id === targetId &&
    value.target_type === "storage" &&
    isText(value.reason, 500) &&
    value.reason === value.reason.trim().replace(/\s+/g, " ") &&
    isDigest(value.reason_digest) &&
    isIdentifier(value.correlation_id) &&
    typeof value.occurred_at === "string" &&
    !Number.isNaN(Date.parse(value.occurred_at)) &&
    isDigest(value.canonical_digest)
  );
}

function isBoundToScope(value: WorkflowRunPlan, scope: WorkflowScope): boolean {
  return (
    value.scope.organization_id === scope.organizationId &&
    value.scope.environment_id === scope.environmentId &&
    value.scope.site_id === scope.siteId
  );
}

function isLeaseBoundToPlan(
  value: unknown,
  plan: WorkflowRunPlan,
): value is WorkflowOrchestrationLease {
  if (!isObject(value) || !isScope(value.scope)) return false;
  const effectiveState = value.effective_state;
  const stateIsConsistent =
    (value.state === "active" && (effectiveState === "active" || effectiveState === "expired")) ||
    (value.state === "released" && effectiveState === "released");
  return (
    isIdentifier(value.lease_id) &&
    value.plan_id === plan.plan_id &&
    value.plan_digest === plan.canonical_digest &&
    value.scope.organization_id === plan.scope.organization_id &&
    value.scope.environment_id === plan.scope.environment_id &&
    value.scope.site_id === plan.scope.site_id &&
    value.target_id === plan.target_id &&
    value.target_type === plan.target_type &&
    isIdentifier(value.worker_subject_id) &&
    isTimestamp(value.acquired_at) &&
    isTimestamp(value.last_heartbeat_at) &&
    isTimestamp(value.expires_at) &&
    Date.parse(value.acquired_at) <= Date.parse(value.last_heartbeat_at) &&
    Date.parse(value.last_heartbeat_at) < Date.parse(value.expires_at) &&
    Number.isSafeInteger(value.fencing_token) &&
    Number(value.fencing_token) >= 1 &&
    stateIsConsistent &&
    isDigest(value.canonical_digest) &&
    value.grants_execution_authority === false &&
    !("token" in value) &&
    !("credential" in value) &&
    !("secret" in value)
  );
}

function isRunPlan(value: unknown): value is WorkflowRunPlan {
  if (
    !isObject(value) ||
    !isObject(value.scope) ||
    !Array.isArray(value.steps) ||
    !Array.isArray(value.transition_history)
  ) {
    return false;
  }
  const baseValid =
    isIdentifier(value.plan_id) &&
    isIdentifier(value.definition_id) &&
    Number.isInteger(value.definition_version) &&
    Number(value.definition_version) >= 1 &&
    isDigest(value.definition_digest) &&
    isIdentifier(value.scope.organization_id) &&
    isIdentifier(value.scope.environment_id) &&
    isIdentifier(value.scope.site_id) &&
    isIdentifier(value.target_id) &&
    value.target_type === "storage" &&
    isDigest(value.canonical_input_digest) &&
    isIdentifier(value.creator_subject_id) &&
    typeof value.created_at === "string" &&
    !Number.isNaN(Date.parse(value.created_at)) &&
    (value.state === "planned" || value.state === "cancelled") &&
    value.steps.length >= 1 &&
    value.steps.every(isPlanStep) &&
    typeof value.durable === "boolean" &&
    hasSafeAuthority(value.authority) &&
    value.safety_notice === WORKFLOW_PLAN_SAFETY_NOTICE &&
    isDigest(value.canonical_digest);
  if (!baseValid) return false;
  const transitionsValid = value.transition_history.every((transition) =>
    isTransition(
      transition,
      value.scope as WorkflowRunPlan["scope"],
      value.target_id as string,
    ),
  );
  return (
    transitionsValid &&
    ((value.state === "planned" && value.transition_history.length === 0) ||
      (value.state === "cancelled" && value.transition_history.length === 1))
  );
}

async function readData(response: Response, failure: string): Promise<unknown> {
  if (!response.ok) throw new ApiRequestError(failure, response.status);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiRequestError(`${failure}: malformed JSON`, response.status);
  }
  if (!isObject(payload) || !("data" in payload)) {
    throw new ApiRequestError(`${failure}: malformed envelope`, response.status);
  }
  return payload.data;
}

export async function listWorkflowDefinitions(): Promise<WorkflowDefinitionInventory> {
  const response = await apiFetch("/api/v1/workflows/definitions", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow definition list failed");
  if (!isObject(data) || !Array.isArray(data.definitions) || !data.definitions.every(isDefinition)) {
    throw new ApiRequestError("Workflow definition list was unsafe", response.status);
  }
  return { definitions: data.definitions };
}

export async function listWorkflowPlans(input: {
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowPlanInventory> {
  const response = await apiFetch("/api/v1/workflows/plans?limit=50", {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow plan list failed");
  if (!isObject(data) || !Array.isArray(data.plans) || !data.plans.every(isRunPlan)) {
    throw new ApiRequestError("Workflow plan list was unsafe", response.status);
  }
  if (
    typeof data.durable !== "boolean" ||
    typeof data.truncated !== "boolean" ||
    !data.plans.every(
      (plan) =>
        isBoundToScope(plan, input.scope) &&
        input.authorizedTargetIds.includes(plan.target_id) &&
        plan.durable === data.durable,
    )
  ) {
    throw new ApiRequestError("Workflow plan list was outside the authorized scope", response.status);
  }
  return data as WorkflowPlanInventory;
}

export async function getWorkflowPlan(input: {
  planId: string;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowRunPlan> {
  const response = await apiFetch(`/api/v1/workflows/plans/${encodeURIComponent(input.planId)}`, {
    headers: { Accept: "application/json" },
  });
  const data = await readData(response, "Workflow plan retrieval failed");
  if (
    !isRunPlan(data) ||
    data.plan_id !== input.planId ||
    !isBoundToScope(data, input.scope) ||
    !input.authorizedTargetIds.includes(data.target_id)
  ) {
    throw new ApiRequestError("Workflow plan response was unsafe", response.status);
  }
  return data;
}

export async function getWorkflowOrchestrationLease(input: {
  plan: WorkflowRunPlan;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowOrchestrationLeaseStatus> {
  if (
    !isBoundToScope(input.plan, input.scope) ||
    !input.authorizedTargetIds.includes(input.plan.target_id)
  ) {
    throw new ApiRequestError("Workflow plan is outside the authorized lease scope", 403);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.plan.plan_id)}/orchestration-lease`,
    { headers: { Accept: "application/json" } },
  );
  const data = await readData(response, "Workflow orchestration lease retrieval failed");
  if (
    !isObject(data) ||
    data.plan_id !== input.plan.plan_id ||
    !isTimestamp(data.server_time) ||
    typeof data.durable !== "boolean" ||
    !(data.lease === null || isLeaseBoundToPlan(data.lease, input.plan))
  ) {
    throw new ApiRequestError("Workflow orchestration lease response was unsafe", response.status);
  }
  return data as WorkflowOrchestrationLeaseStatus;
}

export async function createWorkflowPlan(input: {
  definition: WorkflowDefinition;
  targetId: string;
  purpose: string;
  inputSummary: string;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowRunPlan> {
  if (!input.authorizedTargetIds.includes(input.targetId)) {
    throw new ApiRequestError("Storage target is outside the authorized workflow scope", 403);
  }
  const response = await apiFetch("/api/v1/workflows/plans", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": `workflow-plan-create.${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      schema_version: "atlas.workflow-run-plan-create-input.v1",
      definition_id: input.definition.definition_id,
      definition_version: input.definition.version,
      target_id: input.targetId,
      target_type: "storage",
      inputs: {
        purpose: input.purpose.trim(),
        input_summary: input.inputSummary.trim(),
      },
      acknowledged_planning_only_no_execution_authority: true,
    }),
  });
  const data = await readData(response, "Workflow plan creation failed");
  if (
    !isRunPlan(data) ||
    data.definition_id !== input.definition.definition_id ||
    data.definition_version !== input.definition.version ||
    data.definition_digest !== input.definition.definition_digest ||
    data.target_id !== input.targetId ||
    !isBoundToScope(data, input.scope)
  ) {
    throw new ApiRequestError("Workflow plan creation response was not request-bound", response.status);
  }
  return data;
}

export async function cancelWorkflowPlan(input: {
  plan: WorkflowRunPlan;
  reason: string;
  acknowledgeNoExternalUndo: boolean;
  scope: WorkflowScope;
  authorizedTargetIds: readonly string[];
}): Promise<WorkflowRunPlan> {
  if (
    input.plan.state !== "planned" ||
    !isBoundToScope(input.plan, input.scope) ||
    !input.authorizedTargetIds.includes(input.plan.target_id)
  ) {
    throw new ApiRequestError("Workflow plan is not cancellable in this scope", 409);
  }
  const reason = input.reason.trim().replace(/\s+/g, " ");
  if (!reason || reason.length > 500 || input.acknowledgeNoExternalUndo !== true) {
    throw new ApiRequestError("Workflow cancellation requires a reason and acknowledgement", 422);
  }
  const response = await apiFetch(
    `/api/v1/workflows/plans/${encodeURIComponent(input.plan.plan_id)}/cancellation`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": `workflow-plan-cancel.${crypto.randomUUID()}`,
      },
      body: JSON.stringify({
        schema_version: "atlas.workflow-run-plan-cancellation-input.v1",
        reason,
        acknowledge_no_external_undo: true,
      }),
    },
  );
  const data = await readData(response, "Workflow plan cancellation failed");
  if (
    !isRunPlan(data) ||
    data.plan_id !== input.plan.plan_id ||
    data.state !== "cancelled" ||
    data.target_id !== input.plan.target_id ||
    !isBoundToScope(data, input.scope) ||
    !input.authorizedTargetIds.includes(data.target_id) ||
    data.transition_history.length !== 1 ||
    data.transition_history.at(0)?.reason !== reason
  ) {
    throw new ApiRequestError(
      "Workflow plan cancellation response was not request-bound",
      response.status,
    );
  }
  return data;
}
