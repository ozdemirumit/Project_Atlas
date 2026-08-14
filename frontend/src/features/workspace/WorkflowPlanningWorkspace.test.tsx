import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listOperationalConversations } from "../../api/conversations";
import {
  cancelWorkflowPlan,
  createWorkflowPlan,
  listWorkflowDefinitions,
  listWorkflowPlans,
  WORKFLOW_PLAN_SAFETY_NOTICE,
  type WorkflowDefinition,
  type WorkflowDispatchIntent,
  type WorkflowDispatchEventEnvelope,
  type WorkflowDispatchOutboxEntry,
  type WorkflowDispatchOutboxPublicationLease,
  type WorkflowExecutionAttempt,
  type WorkflowExecutionRun,
  type WorkflowOrchestrationLease,
  type WorkflowRunPlan,
} from "../../api/workflows";
import WorkflowPlanningWorkspace from "./WorkflowPlanningWorkspace";

vi.mock("../../api/conversations", () => ({ listOperationalConversations: vi.fn() }));
vi.mock("../../api/workflows", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/workflows")>();
  return {
    ...original,
    cancelWorkflowPlan: vi.fn(),
    createWorkflowPlan: vi.fn(),
    listWorkflowDefinitions: vi.fn(),
    listWorkflowPlans: vi.fn(),
  };
});

const definition: WorkflowDefinition = {
  definition_id: "workflow.evidence-grounded-query",
  version: 1,
  title: "Evidence-grounded query",
  purpose: "Plan bounded evidence retrieval.",
  input_schema_version: "workflow-input.v1",
  definition_digest: "a".repeat(64),
  steps: [
    {
      step_id: "query-authorized-evidence",
      ordinal: 1,
      title: "Query authorized evidence",
      kind: "evidence_query",
      capability_class: "C1",
      timeout_seconds: 60,
      depends_on: [],
    },
  ],
};

const plan: WorkflowRunPlan = {
  plan_id: "workflow_plan_1234567890abcdef",
  definition_id: definition.definition_id,
  definition_version: 1,
  definition_digest: definition.definition_digest,
  scope: {
    organization_id: "organization.test",
    environment_id: "environment.test",
    site_id: "site.test",
  },
  target_id: "asset.storage.test",
  target_type: "storage",
  canonical_input_digest: "b".repeat(64),
  creator_subject_id: "subject.operator",
  created_at: "2026-08-13T10:00:00Z",
  state: "planned",
  steps: [
    {
      step_id: "query-authorized-evidence",
      ordinal: 1,
      kind: "evidence_query",
      capability_class: "C1",
      state: "not_started",
    },
  ],
  durable: false,
  authority: {
    worker_dispatch_authorized: false,
    connector_invocation_authorized: false,
    approval_creation_authorized: false,
    signal_delivery_authorized: false,
    retry_authorized: false,
    itsm_mutation_authorized: false,
    runbook_execution_authorized: false,
    infrastructure_change_authorized: false,
  },
  safety_notice: WORKFLOW_PLAN_SAFETY_NOTICE,
  canonical_digest: "c".repeat(64),
  transition_history: [],
};

const cancelledPlan: WorkflowRunPlan = {
  ...plan,
  state: "cancelled",
  canonical_digest: "d".repeat(64),
  transition_history: [
    {
      transition_id: "workflow-transition.1234567890abcdef",
      prior_state: "planned",
      new_state: "cancelled",
      actor_subject_id: "subject.operator",
      scope: plan.scope,
      target_id: plan.target_id,
      target_type: "storage",
      reason: "The assessment is no longer required.",
      reason_digest: "e".repeat(64),
      correlation_id: "correlation.workflow.cancel",
      occurred_at: "2026-08-13T10:05:00Z",
      canonical_digest: "f".repeat(64),
    },
  ],
};

const activeLease: WorkflowOrchestrationLease = {
  lease_id: "workflow-lease.1234567890abcdef",
  plan_id: plan.plan_id,
  plan_digest: plan.canonical_digest,
  scope: plan.scope,
  target_id: plan.target_id,
  target_type: "storage",
  worker_subject_id: "workload.worker",
  acquired_at: "2026-08-13T10:01:00Z",
  last_heartbeat_at: "2026-08-13T10:02:00Z",
  expires_at: "2026-08-13T10:07:00Z",
  fencing_token: 7,
  state: "active",
  effective_state: "active",
  canonical_digest: "8".repeat(64),
  grants_execution_authority: false,
};

const materializedRun: WorkflowExecutionRun = {
  run_id: "workflow-run.1234567890abcdef",
  plan_id: plan.plan_id,
  plan_digest: plan.canonical_digest,
  definition_id: plan.definition_id,
  definition_version: plan.definition_version,
  definition_digest: plan.definition_digest,
  scope: plan.scope,
  target_id: plan.target_id,
  target_type: "storage",
  lease_id: activeLease.lease_id,
  lease_digest: activeLease.canonical_digest,
  fencing_token: activeLease.fencing_token,
  materialized_by_subject_id: "workload.workflow.materializer",
  created_at: "2026-08-13T10:03:00Z",
  state: "created",
  step_runs: [
    {
      step_run_id: "workflow-step-run.1234567890abcdef",
      run_id: "workflow-run.1234567890abcdef",
      step_id: plan.steps[0]!.step_id,
      ordinal: 1,
      kind: plan.steps[0]!.kind,
      capability_class: plan.steps[0]!.capability_class,
      timeout_seconds: 60,
      depends_on: [],
      state: "not_started",
      canonical_digest: "9".repeat(64),
    },
  ],
  authority: { ...plan.authority },
  grants_execution_authority: false,
  canonical_digest: "1".repeat(64),
};

const materializedAttempt: WorkflowExecutionAttempt = {
  attempt_id: "workflow-attempt.1234567890abcdef",
  run_id: materializedRun.run_id,
  run_digest: materializedRun.canonical_digest,
  step_run_id: materializedRun.step_runs[0]!.step_run_id,
  step_run_digest: materializedRun.step_runs[0]!.canonical_digest,
  step_id: materializedRun.step_runs[0]!.step_id,
  attempt_number: 1,
  plan_id: materializedRun.plan_id,
  plan_digest: materializedRun.plan_digest,
  definition_id: materializedRun.definition_id,
  definition_version: materializedRun.definition_version,
  definition_digest: materializedRun.definition_digest,
  scope: materializedRun.scope,
  target_id: materializedRun.target_id,
  target_type: "storage",
  lease_id: materializedRun.lease_id,
  lease_digest: materializedRun.lease_digest,
  fencing_token: materializedRun.fencing_token,
  materialized_by_subject_id: materializedRun.materialized_by_subject_id,
  created_at: "2026-08-13T10:05:00Z",
  state: "created",
  authority: { ...materializedRun.authority },
  grants_execution_authority: false,
  canonical_digest: "2".repeat(64),
};

const stagedDispatchIntent: WorkflowDispatchIntent = {
  dispatch_intent_id: "workflow-dispatch-intent.1234567890abcdef",
  plan_id: materializedAttempt.plan_id,
  plan_digest: materializedAttempt.plan_digest,
  run_id: materializedAttempt.run_id,
  run_digest: materializedAttempt.run_digest,
  step_run_id: materializedAttempt.step_run_id,
  step_run_digest: materializedAttempt.step_run_digest,
  step_id: materializedAttempt.step_id,
  attempt_id: materializedAttempt.attempt_id,
  attempt_digest: materializedAttempt.canonical_digest,
  attempt_number: 1,
  scope: materializedAttempt.scope,
  target_id: materializedAttempt.target_id,
  target_type: "storage",
  lease_id: materializedAttempt.lease_id,
  lease_digest: "3".repeat(64),
  fencing_token: materializedAttempt.fencing_token,
  worker_subject_id: "workload.workflow.worker",
  staged_at: "2026-08-13T10:07:00Z",
  state: "staged",
  authority: { ...materializedAttempt.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "4".repeat(64),
};

const pendingOutboxEntry: WorkflowDispatchOutboxEntry = {
  outbox_entry_id: "workflow-dispatch-outbox.1234567890abcdef",
  dispatch_intent_id: stagedDispatchIntent.dispatch_intent_id,
  dispatch_intent_digest: stagedDispatchIntent.canonical_digest,
  plan_id: stagedDispatchIntent.plan_id,
  plan_digest: stagedDispatchIntent.plan_digest,
  run_id: stagedDispatchIntent.run_id,
  run_digest: stagedDispatchIntent.run_digest,
  step_run_id: stagedDispatchIntent.step_run_id,
  step_run_digest: stagedDispatchIntent.step_run_digest,
  step_id: stagedDispatchIntent.step_id,
  attempt_id: stagedDispatchIntent.attempt_id,
  attempt_digest: stagedDispatchIntent.attempt_digest,
  attempt_number: 1,
  scope: stagedDispatchIntent.scope,
  target_id: stagedDispatchIntent.target_id,
  target_type: "storage",
  lease_id: stagedDispatchIntent.lease_id,
  lease_digest: stagedDispatchIntent.lease_digest,
  fencing_token: stagedDispatchIntent.fencing_token,
  worker_subject_id: stagedDispatchIntent.worker_subject_id,
  admitted_at: stagedDispatchIntent.staged_at,
  state: "pending_publication",
  authority: { ...stagedDispatchIntent.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "6".repeat(64),
};

const activePublicationLease: WorkflowDispatchOutboxPublicationLease = {
  publication_lease_id: "workflow-publication-lease.1234567890abcdef",
  outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
  outbox_entry_digest: pendingOutboxEntry.canonical_digest,
  dispatch_intent_id: pendingOutboxEntry.dispatch_intent_id,
  dispatch_intent_digest: pendingOutboxEntry.dispatch_intent_digest,
  plan_id: pendingOutboxEntry.plan_id,
  plan_digest: pendingOutboxEntry.plan_digest,
  run_id: pendingOutboxEntry.run_id,
  run_digest: pendingOutboxEntry.run_digest,
  step_run_id: pendingOutboxEntry.step_run_id,
  step_run_digest: pendingOutboxEntry.step_run_digest,
  step_id: pendingOutboxEntry.step_id,
  attempt_id: pendingOutboxEntry.attempt_id,
  attempt_digest: pendingOutboxEntry.attempt_digest,
  attempt_number: 1,
  scope: pendingOutboxEntry.scope,
  target_id: pendingOutboxEntry.target_id,
  target_type: "storage",
  orchestration_lease_id: pendingOutboxEntry.lease_id,
  orchestration_lease_digest: pendingOutboxEntry.lease_digest,
  orchestration_fencing_token: pendingOutboxEntry.fencing_token,
  publisher_subject_id: "workload.workflow.publisher",
  acquired_at: "2026-08-13T10:11:00Z",
  last_heartbeat_at: "2026-08-13T10:12:00Z",
  expires_at: "2026-08-13T10:20:00Z",
  publication_fencing_token: 1,
  state: "active",
  authority: { ...pendingOutboxEntry.authority },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "7".repeat(64),
  effective_state: "active",
};

const preparedEventEnvelope: WorkflowDispatchEventEnvelope = {
  event_id: "workflow-event.1234567890abcdef",
  event_type: "WorkflowStepDispatchRequested",
  event_version: "1.0",
  producer: "atlas.workflow",
  producer_version: "1.0.0",
  occurred_at: pendingOutboxEntry.admitted_at,
  recorded_at: "2026-08-13T10:14:00Z",
  subject_type: "workflow-execution-attempt",
  subject_id: pendingOutboxEntry.attempt_id,
  organization_id: pendingOutboxEntry.scope.organization_id,
  environment_id: pendingOutboxEntry.scope.environment_id,
  correlation_id: pendingOutboxEntry.run_id,
  causation_id: pendingOutboxEntry.dispatch_intent_id,
  workflow_id: pendingOutboxEntry.run_id,
  data_classification: "internal",
  schema_uri: "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
  payload: {
    plan_id: pendingOutboxEntry.plan_id,
    plan_digest: pendingOutboxEntry.plan_digest,
    run_id: pendingOutboxEntry.run_id,
    run_digest: pendingOutboxEntry.run_digest,
    step_run_id: pendingOutboxEntry.step_run_id,
    step_run_digest: pendingOutboxEntry.step_run_digest,
    step_id: pendingOutboxEntry.step_id,
    attempt_id: pendingOutboxEntry.attempt_id,
    attempt_digest: pendingOutboxEntry.attempt_digest,
    attempt_number: pendingOutboxEntry.attempt_number,
    scope: pendingOutboxEntry.scope,
    target_id: pendingOutboxEntry.target_id,
    target_type: pendingOutboxEntry.target_type,
    dispatch_intent_id: pendingOutboxEntry.dispatch_intent_id,
    dispatch_intent_digest: pendingOutboxEntry.dispatch_intent_digest,
    outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
    outbox_entry_digest: pendingOutboxEntry.canonical_digest,
  },
  extensions: {},
  orchestration_lease_id: activePublicationLease.orchestration_lease_id,
  orchestration_lease_digest: activePublicationLease.orchestration_lease_digest,
  orchestration_fencing_token: activePublicationLease.orchestration_fencing_token,
  publication_lease_id: activePublicationLease.publication_lease_id,
  publication_lease_digest: activePublicationLease.canonical_digest,
  publication_fencing_token: activePublicationLease.publication_fencing_token,
  publisher_subject_id: activePublicationLease.publisher_subject_id,
  prepared_at: "2026-08-13T10:14:00Z",
  state: "prepared",
  authority: {
    publication_authorized: false,
    delivery_authorized: false,
    dispatch_authorized: false,
    execution_authorized: false,
  },
  grants_publication_authority: false,
  grants_delivery_authority: false,
  grants_dispatch_authority: false,
  grants_execution_authority: false,
  canonical_digest: "9".repeat(64),
};

function leaseResponse(lease: WorkflowOrchestrationLease | null, status = 200): Response {
  return new Response(
    JSON.stringify({
      data: {
        plan_id: plan.plan_id,
        server_time: "2026-08-13T10:03:00Z",
        durable: false,
        lease,
      },
      meta: {
        correlation_id: "correlation.workflow.lease",
        generated_at: "2026-08-13T10:03:00Z",
      },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function materializedRunResponse(run: WorkflowExecutionRun | null, status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            plan_id: plan.plan_id,
            run,
            server_time: "2026-08-13T10:04:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.run",
            generated_at: "2026-08-13T10:04:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function attemptResponse(attempts: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            run_id: materializedRun.run_id,
            attempts,
            server_time: "2026-08-13T10:06:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.attempt",
            generated_at: "2026-08-13T10:06:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function dispatchIntentResponse(dispatchIntents: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            attempt_id: materializedAttempt.attempt_id,
            dispatch_intents: dispatchIntents,
            server_time: "2026-08-13T10:08:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.dispatch-intent",
            generated_at: "2026-08-13T10:08:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function outboxResponse(outboxEntries: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            dispatch_intent_id: stagedDispatchIntent.dispatch_intent_id,
            outbox_entries: outboxEntries,
            server_time: "2026-08-13T10:10:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.dispatch-outbox",
            generated_at: "2026-08-13T10:10:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function publicationLeaseResponse(publicationLeases: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
            publication_leases: publicationLeases,
            server_time: "2026-08-13T10:13:00Z",
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.publication-lease",
            generated_at: "2026-08-13T10:13:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function eventEnvelopeResponse(eventEnvelopes: unknown[], status = 200): Response {
  return new Response(
    status === 200
      ? JSON.stringify({
          data: {
            outbox_entry_id: pendingOutboxEntry.outbox_entry_id,
            event_envelopes: eventEnvelopes,
            durable: false,
          },
          meta: {
            correlation_id: "correlation.workflow.event-envelope",
            generated_at: "2026-08-13T10:15:00Z",
          },
        })
      : null,
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function mockReadResponses(input: {
  lease?: WorkflowOrchestrationLease | null;
  run?: WorkflowExecutionRun | null;
  attempts?: unknown[];
  dispatchIntents?: unknown[];
  outboxEntries?: unknown[];
  publicationLeases?: unknown[];
  eventEnvelopes?: unknown[];
  leaseStatus?: number;
  runStatus?: number;
  attemptStatus?: number;
  dispatchIntentStatus?: number;
  outboxStatus?: number;
  publicationLeaseStatus?: number;
  eventEnvelopeStatus?: number;
}) {
  vi.mocked(fetch).mockImplementation((request) => {
    const url = request instanceof Request ? request.url : request.toString();
    if (url.endsWith("/event-envelope")) {
      return Promise.resolve(
        eventEnvelopeResponse(input.eventEnvelopes ?? [], input.eventEnvelopeStatus ?? 200),
      );
    }
    if (url.endsWith("/publication-lease")) {
      return Promise.resolve(
        publicationLeaseResponse(
          input.publicationLeases ?? [activePublicationLease],
          input.publicationLeaseStatus ?? 200,
        ),
      );
    }
    if (url.endsWith("/outbox")) {
      return Promise.resolve(outboxResponse(input.outboxEntries ?? [], input.outboxStatus ?? 200));
    }
    if (url.endsWith("/dispatch-intents")) {
      return Promise.resolve(
        dispatchIntentResponse(
          input.dispatchIntents ?? [],
          input.dispatchIntentStatus ?? 200,
        ),
      );
    }
    if (url.endsWith("/attempts")) {
      return Promise.resolve(attemptResponse(input.attempts ?? [], input.attemptStatus ?? 200));
    }
    return Promise.resolve(
      url.endsWith("/materialized-run")
        ? materializedRunResponse(input.run ?? null, input.runStatus ?? 200)
        : leaseResponse(input.lease ?? null, input.leaseStatus ?? 200),
    );
  });
}

function renderWorkspace() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <WorkflowPlanningWorkspace
        environmentId="environment.test"
        organizationId="organization.test"
        ownerSubjectId="subject.operator"
        siteId="site.test"
        onBack={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("WorkflowPlanningWorkspace", () => {
  beforeEach(() => {
    vi.mocked(listOperationalConversations).mockResolvedValue({
      conversations: [],
      authorizedTargets: [{ targetId: "asset.storage.test", displayName: "Primary storage" }],
      durable: false,
      truncated: false,
    });
    vi.mocked(listWorkflowDefinitions).mockResolvedValue({ definitions: [definition] });
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [], durable: false, truncated: false });
    vi.mocked(createWorkflowPlan).mockResolvedValue(plan);
    vi.mocked(cancelWorkflowPlan).mockResolvedValue(cancelledPlan);
    vi.stubGlobal("fetch", vi.fn());
    mockReadResponses({});
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("creates and presents a planned-only workflow without requesting another login", async () => {
    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Available definitions" })).toBeVisible();
    expect(screen.getByText("No execution authority")).toBeVisible();
    expect(screen.queryByText(/authorized browser session/i)).toBeNull();
    fireEvent.change(screen.getByLabelText("Definition"), {
      target: { value: definition.definition_id },
    });
    fireEvent.change(screen.getByLabelText("Authorized storage target"), {
      target: { value: "asset.storage.test" },
    });
    fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Review evidence" } });
    fireEvent.change(screen.getByLabelText("Input summary"), {
      target: { value: "Use current observations" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create plan" }));

    await waitFor(() => expect(createWorkflowPlan).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("heading", { name: plan.plan_id })).toBeVisible();
    expect(screen.getByText(/No connector, approval, ITSM, runbook, worker/i)).toBeVisible();
    expect(screen.getAllByText("planned").length).toBeGreaterThan(0);
  });

  it("cancels a selected planned plan and preserves its immutable history", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    const confirm = screen.getByRole("button", { name: "Confirm cancellation" });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Cancellation reason"), {
      target: { value: "  The assessment is no longer required.  " },
    });
    fireEvent.click(
      screen.getByLabelText(
        "I acknowledge that cancellation preserves history and cannot undo external work.",
      ),
    );
    fireEvent.click(confirm);

    await waitFor(() => expect(cancelWorkflowPlan).toHaveBeenCalledTimes(1));
    expect(cancelWorkflowPlan).toHaveBeenCalledWith(
      expect.objectContaining({
        plan,
        reason: "  The assessment is no longer required.  ",
        acknowledgeNoExternalUndo: true,
      }),
    );
    expect(await screen.findByRole("heading", { name: "State transitions" })).toBeVisible();
    expect(screen.getByText("planned to cancelled")).toBeVisible();
    expect(screen.getByText(/The assessment is no longer required/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Cancel this plan" })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it.each([
    ["active", activeLease],
    [
      "expired",
      { ...activeLease, effective_state: "expired" } satisfies WorkflowOrchestrationLease,
    ],
    [
      "released",
      {
        ...activeLease,
        state: "released",
        effective_state: "released",
      } satisfies WorkflowOrchestrationLease,
    ],
  ] as const)("presents %s lease evidence without human mutation controls", async (state, lease) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ lease });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(state)).toBeVisible();
    expect(screen.getByText("7")).toBeVisible();
    expect(screen.getByText("workload.worker")).toBeVisible();
    expect(screen.getByText(/coordinates ownership only/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /acquire|heartbeat|release/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
    expect(screen.getAllByText(/not_started/).length).toBeGreaterThan(0);
  });

  it("presents an empty lease result without inferring ownership", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(
      await screen.findByText("No orchestration lease is recorded for this plan."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /acquire|heartbeat|release/i })).toBeNull();
  });

  it("fails closed when lease evidence is not bound to the selected plan digest", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ lease: { ...activeLease, plan_digest: "0".repeat(64) } });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Lease status is unavailable")).toBeVisible();
    expect(screen.getByText(/No lease state is inferred/i)).toBeVisible();
    expect(screen.queryByText("workload.worker")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Lease status permission is missing", "current role cannot inspect"],
    [503, "Lease status is unavailable", "No lease state is inferred"],
  ])("handles lease read status %s without inventing another authentication step", async (
    status,
    title,
    detail,
  ) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ leaseStatus: status });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
    if (status === 503) {
      expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
    } else {
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    }
  });

  it("presents an empty materialized run result without implying execution", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(
      await screen.findByText("No materialized run is recorded for this plan."),
    ).toBeVisible();
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith("/attempts"),
      ),
    ).toBe(false);
    expect(screen.queryByRole("button", { name: /materialize|start|execute|dispatch/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("presents a request-bound created run and its ordered not-started steps read-only", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ lease: activeLease, run: materializedRun });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByRole("heading", { name: "Materialized run record" })).toBeVisible();
    expect(await screen.findByTitle("workload.workflow.materializer")).toBeVisible();
    expect(screen.getByText("created")).toBeVisible();
    expect(screen.getAllByText("7")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "Materialized step records" })).toHaveTextContent(
      "query-authorized-evidence",
    );
    expect(screen.getByRole("list", { name: "Materialized step records" })).toHaveTextContent(
      "not_started",
    );
    expect(screen.getByText(/freezes run and step identities/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /materialize|start|execute|dispatch/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("fails closed on an unsafe materialized run response", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: {
        ...materializedRun,
        plan_digest: "0".repeat(64),
        materialized_by_subject_id: "unsafe.subject",
      },
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Run record is unavailable")).toBeVisible();
    expect(screen.getByText(/No run state is inferred/i)).toBeVisible();
    expect(screen.queryByText("unsafe.subject")).toBeNull();
  });

  it("retries a failed read-only run request without exposing mutation controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    let runReads = 0;
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (!url.endsWith("/materialized-run")) return Promise.resolve(leaseResponse(null));
      runReads += 1;
      return Promise.resolve(
        runReads === 1 ? materializedRunResponse(null, 503) : materializedRunResponse(null),
      );
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry run record" }));

    expect(
      await screen.findByText("No materialized run is recorded for this plan."),
    ).toBeVisible();
    expect(runReads).toBe(2);
    expect(screen.queryByRole("button", { name: /materialize|start|execute|dispatch/i })).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Run record permission is missing", "current role cannot inspect materialized"],
  ])("handles run read status %s with the existing sign-in and permission model", async (
    status,
    title,
    detail,
  ) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ runStatus: status });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry run record" })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("presents an empty attempt inventory only after a materialized run exists", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(
      await screen.findByRole("heading", { name: "Materialized attempt records" }),
    ).toBeVisible();
    expect(
      await screen.findByText("No materialized attempts are recorded for this run."),
    ).toBeVisible();
    expect(screen.getAllByText("No human controls").length).toBeGreaterThan(0);
    expect(screen.getByText(/No action ran, and no execution authority/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
  });

  it("shows read-only loading state while authoritative attempt evidence is pending", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/attempts")) return new Promise<Response>(() => undefined);
      if (url.endsWith("/materialized-run")) {
        return Promise.resolve(materializedRunResponse(materializedRun));
      }
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Loading authoritative attempt records...")).toBeVisible();
    expect(screen.getAllByText("No human controls").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
  });

  it("renders an exact run-bound root-step attempt as read-only evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [materializedAttempt] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const records = await screen.findByRole("list", { name: "Materialized attempt records" });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/api/v1/workflows/plans/${plan.plan_id}/runs/${materializedRun.run_id}/attempts`,
        ),
      ),
    ).toBe(true);
    expect(await screen.findByTitle(materializedAttempt.attempt_id)).toBeVisible();
    expect(records).toHaveTextContent("root step query-authorized-evidence");
    expect(records).toHaveTextContent("created");
    expect(records).toHaveTextContent("fence 7");
    expect(records).toHaveTextContent("run 111111111111...11111111");
    expect(records).toHaveTextContent("step 999999999999...99999999");
    expect(records).toHaveTextContent("attempt 222222222222...22222222");
    expect(screen.getByText(/No action ran, and no execution authority/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
  });

  it("fails closed on unsafe or unbound attempt evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [{ ...materializedAttempt, step_run_digest: "0".repeat(64), password: "unsafe" }],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Attempt evidence is unavailable")).toBeVisible();
    expect(screen.getByText(/No attempt state is inferred/i)).toBeVisible();
    expect(screen.queryByText(/workflow-attempt.1234567890abcdef/i)).toBeNull();
    expect(screen.queryByText(/unsafe/i)).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Attempt evidence permission is missing", "current role cannot inspect materialized"],
    [503, "Attempt evidence is unavailable", "No attempt state is inferred"],
  ])("handles attempt read status %s without exposing an action", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attemptStatus: status });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /materialize|dispatch|execute/i })).toBeNull();
    if (status === 503) {
      expect(screen.getByRole("button", { name: "Retry attempt evidence" })).toBeVisible();
    } else {
      expect(screen.queryByRole("button", { name: "Retry attempt evidence" })).toBeNull();
    }
  });

  it("retries a generic attempt read failure and keeps the panel control-free", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    let attemptReads = 0;
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/attempts")) {
        attemptReads += 1;
        return Promise.resolve(attemptResponse([], attemptReads === 1 ? 503 : 200));
      }
      if (url.endsWith("/materialized-run")) {
        return Promise.resolve(materializedRunResponse(materializedRun));
      }
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry attempt evidence" }));

    expect(
      await screen.findByText("No materialized attempts are recorded for this run."),
    ).toBeVisible();
    expect(attemptReads).toBe(2);
    expect(screen.queryByRole("button", { name: /attempt|materialize|dispatch|execute/i })).toBeNull();
    expect(screen.getByText(/No action ran, and no execution authority/i)).toBeVisible();
  });

  it("shows dispatch-intent evidence only after a materialized attempt exists", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("No materialized attempts are recorded for this run.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Staged dispatch-intent records" })).toBeNull();
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith("/dispatch-intents"),
      ),
    ).toBe(false);
  });

  it("presents an empty read-only dispatch-intent inventory", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({ run: materializedRun, attempts: [materializedAttempt], dispatchIntents: [] });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByRole("heading", { name: "Staged dispatch-intent records" })).toBeVisible();
    expect(await screen.findByText("No dispatch intents are staged for these attempts.")).toBeVisible();
    expect(screen.getByText(/No message was published, no worker or action ran/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
  });

  it("shows a control-free loading state for dispatch-intent evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/dispatch-intents")) return new Promise<Response>(() => undefined);
      if (url.endsWith("/attempts")) return Promise.resolve(attemptResponse([materializedAttempt]));
      if (url.endsWith("/materialized-run")) return Promise.resolve(materializedRunResponse(materializedRun));
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Loading authoritative dispatch-intent records...")).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
  });

  it("renders an exact attempt-bound dispatch intent as read-only evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const records = await screen.findByRole("list", { name: "Staged dispatch-intent records" });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/api/v1/workflows/plans/${plan.plan_id}/runs/${materializedRun.run_id}/attempts/${materializedAttempt.attempt_id}/dispatch-intents`,
        ),
      ),
    ).toBe(true);
    expect(await screen.findByTitle(stagedDispatchIntent.dispatch_intent_id)).toBeVisible();
    expect(records).toHaveTextContent("step query-authorized-evidence");
    expect(records).toHaveTextContent("staged");
    expect(records).toHaveTextContent("worker workload.workflow.worker");
    expect(records).toHaveTextContent("attempt 222222222222...22222222");
    expect(records).toHaveTextContent("intent 444444444444...44444444");
    expect(screen.getByText(/No message was published, no worker or action ran/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
    expect(screen.queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("fails closed on unsafe or unbound dispatch-intent evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [
        { ...stagedDispatchIntent, attempt_digest: "0".repeat(64), password: "unsafe" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText("Dispatch-intent evidence is unavailable")).toBeVisible();
    expect(screen.getByText(/No dispatch state is inferred/i)).toBeVisible();
    expect(screen.queryByText(/workflow-dispatch-intent.1234567890abcdef/i)).toBeNull();
    expect(screen.queryByText(/unsafe/i)).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Dispatch-intent evidence permission is missing", "current role cannot inspect staged"],
    [503, "Dispatch-intent evidence is unavailable", "No dispatch state is inferred"],
  ])("handles dispatch-intent read status %s without exposing an action", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntentStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
    if (status === 503) {
      expect(screen.getByRole("button", { name: "Retry intent evidence" })).toBeVisible();
    } else {
      expect(screen.queryByRole("button", { name: "Retry intent evidence" })).toBeNull();
    }
  });

  it("retries a generic dispatch-intent read failure without adding authority controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({
      plans: [plan],
      durable: false,
      truncated: false,
    });
    let dispatchIntentReads = 0;
    vi.mocked(fetch).mockImplementation((request) => {
      const url = request instanceof Request ? request.url : request.toString();
      if (url.endsWith("/dispatch-intents")) {
        dispatchIntentReads += 1;
        return Promise.resolve(
          dispatchIntentResponse([], dispatchIntentReads === 1 ? 503 : 200),
        );
      }
      if (url.endsWith("/attempts")) return Promise.resolve(attemptResponse([materializedAttempt]));
      if (url.endsWith("/materialized-run")) return Promise.resolve(materializedRunResponse(materializedRun));
      return Promise.resolve(leaseResponse(null));
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry intent evidence" }));

    expect(await screen.findByText("No dispatch intents are staged for these attempts.")).toBeVisible();
    expect(dispatchIntentReads).toBe(2);
    expect(screen.getByText(/No message was published, no worker or action ran/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /stage|publish|dispatch|execute/i })).toBeNull();
  });

  it("renders pending publication as authoritative, control-free database evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Pending publication outbox records",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Pending publication outbox records",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/dispatch-intents/${stagedDispatchIntent.dispatch_intent_id}/outbox`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(pendingOutboxEntry.outbox_entry_id)).toBeVisible();
    expect(records).toHaveTextContent("pending publication");
    expect(records).toHaveTextContent("fence 7");
    expect(records).toHaveTextContent("intent 444444444444...44444444");
    expect(section).toHaveTextContent("durable database evidence only");
    expect(section).toHaveTextContent("No broker is selected");
    expect(section).toHaveTextContent("no broker address, topic, or routing key");
    expect(section).toHaveTextContent("No publication, delivery, dispatch, or execution occurred or is authorized");
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("fails closed when a staged intent has no atomic outbox record", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Pending publication outbox records",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Outbox evidence is unavailable")).toBeVisible();
    expect(within(section).getByText(/No publication state is inferred/i)).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Outbox evidence permission is missing", "current role cannot inspect pending publication"],
  ])("handles outbox read status %s without another login or an authority control", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Pending publication outbox records",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByRole("button")).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders the current publication lease as read-only evidence", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Publication lease evidence",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/dispatch-intents/${stagedDispatchIntent.dispatch_intent_id}/outbox/${pendingOutboxEntry.outbox_entry_id}/publication-lease`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(activePublicationLease.publication_lease_id)).toBeVisible();
    expect(within(section).getByTitle(activePublicationLease.publisher_subject_id)).toBeVisible();
    expect(records).toHaveTextContent("active");
    expect(records).toHaveTextContent("publication fence 1");
    expect(records).toHaveTextContent("orchestration fence 7");
    expect(records).toHaveTextContent("outbox 666666666666...66666666");
    expect(section).toHaveTextContent("grants no publication, delivery, dispatch, or execution authority");
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders an empty publication lease state without treating it as an integrity failure", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("No publication lease has been acquired.")).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("fails closed when more than one current publication lease is returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [
        activePublicationLease,
        { ...activePublicationLease, publication_lease_id: "workflow-publication-lease.other" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Publication lease evidence is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Publication lease evidence" })).toBeNull();
  });

  it.each([
    ["an extra key", { ...activePublicationLease, unexpected: "unsafe" }],
    ["a broken lineage", { ...activePublicationLease, attempt_id: "workflow-attempt.other" }],
    ["a broken digest", { ...activePublicationLease, outbox_entry_digest: "0".repeat(64) }],
    [
      "a different scope",
      {
        ...activePublicationLease,
        scope: { ...activePublicationLease.scope, site_id: "site.other" },
      },
    ],
    [
      "unsafe embedded authority",
      {
        ...activePublicationLease,
        authority: { ...activePublicationLease.authority, worker_dispatch_authorized: true },
      },
    ],
    ["publication authority", { ...activePublicationLease, grants_publication_authority: true }],
  ])("fails closed when publication lease evidence contains %s", async (_case, unsafeLease) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [unsafeLease],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Publication lease evidence is unavailable")).toBeVisible();
    expect(within(section).getByText(/No lease or publication state is inferred/i)).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Publication lease evidence" })).toBeNull();
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it.each([
    [
      "expired",
      {
        ...activePublicationLease,
        expires_at: "2026-08-13T10:12:30Z",
        effective_state: "expired",
      },
    ],
    [
      "released",
      {
        ...activePublicationLease,
        state: "released",
        effective_state: "released",
      },
    ],
  ])("renders %s publication lease state from validated server evidence", async (state, lease) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [lease],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(state)).toBeVisible();
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Publication lease evidence permission is missing", "current role cannot inspect publication lease"],
  ])("handles publication lease read status %s without another login or action controls", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeaseStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Publication lease evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(within(section).queryByRole("button", { name: /acquire|heartbeat|release|publish|deliver|dispatch|execute/i })).toBeNull();
  });

  it("renders one canonical event envelope with exact preparation lineage and no authority controls", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [preparedEventEnvelope],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Canonical event-envelope evidence",
    });
    expect(
      vi.mocked(fetch).mock.calls.some(([request]) =>
        (request instanceof Request ? request.url : request.toString()).endsWith(
          `/outbox/${pendingOutboxEntry.outbox_entry_id}/event-envelope`,
        ),
      ),
    ).toBe(true);
    expect(within(section).getByTitle(preparedEventEnvelope.event_id)).toBeVisible();
    expect(records).toHaveTextContent("WorkflowStepDispatchRequested v1.0");
    expect(records).toHaveTextContent("atlas.workflow v1.0.0");
    expect(records).toHaveTextContent("workflow-execution-attempt");
    expect(records).toHaveTextContent("organization.test");
    expect(records).toHaveTextContent("environment.test");
    expect(records).toHaveTextContent("correlation");
    expect(records).toHaveTextContent("causation");
    expect(records).toHaveTextContent("internal");
    expect(within(section).getByTitle(preparedEventEnvelope.schema_uri)).toBeVisible();
    expect(records).toHaveTextContent("publication fence 1");
    expect(records).toHaveTextContent("source fence 7");
    expect(records).toHaveTextContent("payload/outbox 666666666666...66666666");
    expect(records).toHaveTextContent("envelope 999999999999...99999999");
    expect(section).toHaveTextContent("Prepared canonical data only");
    expect(section).toHaveTextContent("no bytes were serialized");
    expect(section).toHaveTextContent("no message was published or delivered");
    expect(section).toHaveTextContent("no worker was dispatched");
    expect(section).toHaveTextContent("no action was executed");
    expect(
      within(section).queryByRole("button", {
        name: /prepare|serialize|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
  });

  it("renders zero event envelopes as a healthy read-only state", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("No event envelope has been prepared.")).toBeVisible();
    expect(within(section).queryByRole("alert")).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("fails closed when duplicate event envelopes are returned", async () => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [
        preparedEventEnvelope,
        { ...preparedEventEnvelope, event_id: "workflow-event.other" },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Event-envelope evidence is unavailable")).toBeVisible();
    expect(within(section).queryByRole("list", { name: "Canonical event-envelope evidence" })).toBeNull();
  });

  it.each([
    ["an extra key", { ...preparedEventEnvelope, unexpected: "unsafe" }],
    [
      "a mismatched payload lineage",
      {
        ...preparedEventEnvelope,
        payload: { ...preparedEventEnvelope.payload, attempt_digest: "0".repeat(64) },
      },
    ],
    [
      "a different scope",
      {
        ...preparedEventEnvelope,
        payload: {
          ...preparedEventEnvelope.payload,
          scope: { ...preparedEventEnvelope.payload.scope, site_id: "site.other" },
        },
      },
    ],
    [
      "a different target",
      {
        ...preparedEventEnvelope,
        payload: { ...preparedEventEnvelope.payload, target_id: "asset.storage.other" },
      },
    ],
    ["a stale publication fence", { ...preparedEventEnvelope, publication_fencing_token: 2 }],
    ["a stale source fence", { ...preparedEventEnvelope, orchestration_fencing_token: 8 }],
    ["a broken envelope digest", { ...preparedEventEnvelope, canonical_digest: "not-a-digest" }],
    [
      "unsafe embedded authority",
      {
        ...preparedEventEnvelope,
        authority: { ...preparedEventEnvelope.authority, worker_dispatch_authorized: true },
      },
    ],
    ["publication authority", { ...preparedEventEnvelope, grants_publication_authority: true }],
  ])("fails closed when event-envelope evidence contains %s", async (_case, unsafeEnvelope) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [unsafeEnvelope],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText("Event-envelope evidence is unavailable")).toBeVisible();
    expect(section).toHaveTextContent(
      "No preparation, publication, delivery, dispatch, or execution state is inferred",
    );
    expect(within(section).queryByRole("list", { name: "Canonical event-envelope evidence" })).toBeNull();
    expect(
      within(section).queryByRole("button", {
        name: /prepare|serialize|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });

  it.each([
    [401, "Your session has expired", "Sign in again to continue."],
    [403, "Event-envelope evidence permission is missing", "current role or scope cannot inspect"],
  ])("handles event-envelope read status %s with the normal session boundary", async (status, title, detail) => {
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopeStatus: status,
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    expect(await within(section).findByText(title)).toBeVisible();
    expect(within(section).getByText(new RegExp(detail, "i"))).toBeVisible();
    expect(within(section).queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(within(section).queryByRole("button")).toBeNull();
  });

  it("keeps long envelope evidence responsive and control-free at a narrow viewport", async () => {
    vi.stubGlobal("innerWidth", 390);
    vi.mocked(listWorkflowPlans).mockResolvedValue({ plans: [plan], durable: false, truncated: false });
    mockReadResponses({
      run: materializedRun,
      attempts: [materializedAttempt],
      dispatchIntents: [stagedDispatchIntent],
      outboxEntries: [pendingOutboxEntry],
      publicationLeases: [activePublicationLease],
      eventEnvelopes: [
        {
          ...preparedEventEnvelope,
          event_id: `workflow-event.${"longsegment".repeat(15)}`,
        },
      ],
    });
    renderWorkspace();

    fireEvent.click(await screen.findByRole("button", { name: /asset.storage.test/i }));

    const section = (await screen.findByRole("heading", {
      name: "Canonical event-envelope evidence",
    })).closest("div[aria-labelledby]") as HTMLElement;
    const records = await within(section).findByRole("list", {
      name: "Canonical event-envelope evidence",
    });
    expect(records).toHaveClass("workflow-event-envelope-list");
    expect(within(section).getByTitle(/workflow-event\.longsegment/)).toBeVisible();
    expect(
      within(section).queryByRole("button", {
        name: /prepare|serialize|publish|deliver|dispatch|execute/i,
      }),
    ).toBeNull();
  });
});
