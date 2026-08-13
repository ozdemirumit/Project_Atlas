import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listOperationalConversations } from "../../api/conversations";
import {
  cancelWorkflowPlan,
  createWorkflowPlan,
  listWorkflowDefinitions,
  listWorkflowPlans,
  WORKFLOW_PLAN_SAFETY_NOTICE,
  type WorkflowDefinition,
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
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
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
});
