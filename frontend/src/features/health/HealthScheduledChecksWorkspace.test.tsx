import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  HealthCheckDefinition,
  HealthCheckOverview,
  HealthCheckRun,
} from "../../api/healthChecks";
import HealthScheduledChecksWorkspace from "./HealthScheduledChecksWorkspace";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const definition: HealthCheckDefinition = {
  definition_id: "health.controller",
  version: 1,
  title: "Storage controller status",
  owner: "Storage Operations",
  enabled: true,
  target_id: "storage.test",
  connector_id: "connector.test",
  connector_version: "1.0.0",
  capability_id: "storage.hardware.read",
  capability_class: "C1",
  schedule: { interval_minutes: 15, anchor_at: "2026-08-10T09:00:00Z" },
  thresholds: [],
  limits: {
    timeout_seconds: 5,
    max_steps: 2,
    max_evidence_records: 10,
    max_targets: 1,
  },
  evidence_requirements: ["Current controller state"],
};

const schedule: HealthCheckOverview["schedules"][number] = {
  definition_id: definition.definition_id,
  enabled: true,
  interval_minutes: 15,
  last_due_at: "2026-08-10T09:00:00Z",
  next_due_at: "2026-08-10T09:15:00Z",
};

const run: HealthCheckRun = {
  run_id: "run.test",
  definition_id: definition.definition_id,
  definition_version: 1,
  connector_id: "connector.test",
  connector_version: "1.0.0",
  capability_id: "storage.hardware.read",
  target_id: "storage.test",
  trigger: "scheduled",
  requested_by: "scheduler",
  started_at: "2026-08-10T09:00:00Z",
  completed_at: "2026-08-10T09:00:03Z",
  state: "partial",
  step_count: 2,
  observations: [
    {
      observation_id: "observation.test",
      target_id: "storage.test",
      component: "CTL01",
      metric: "controller.status",
      value: "Warning",
      unit: null,
      state: "warning",
      observed_at: "2026-08-10T09:00:02Z",
      freshness: "current",
      evidence_references: ["evidence.test"],
    },
  ],
  findings: [
    {
      finding_id: "finding.test",
      severity: "warning",
      title: "Controller warning requires correlation",
      summary: "Current event-log evidence is unavailable.",
      observation_ids: ["observation.test"],
      evidence_references: ["evidence.test"],
    },
  ],
  evidence: [
    {
      reference: "evidence.test",
      source: "Synthetic fixture",
      source_version: "1",
      observed_at: "2026-08-10T09:00:02Z",
      freshness: "current",
      trust_basis: "Allowlisted synthetic evidence",
    },
  ],
  partial_reasons: ["Authorized event-log evidence is not configured."],
  unknowns: ["The warning duration is unknown."],
  safety_notice: "Read-only decision support only.",
};

const overview: HealthCheckOverview = {
  generated_at: "2026-08-10T09:00:03Z",
  data_profile: "synthetic_lab",
  definitions: [
    definition,
    {
      ...definition,
      definition_id: "health.capacity",
      title: "Storage capacity utilization",
    },
  ],
  schedules: [schedule],
  latest_runs: [run],
  safety_notice: "Read-only evidence collection does not authorize infrastructure change.",
};

const baseProps = {
  error: false,
  loading: false,
  onRunCheck: vi.fn(),
  onSelectDefinition: vi.fn(),
  runError: false,
  runPending: false,
};

describe("HealthScheduledChecksWorkspace", () => {
  it("presents an explicit fail-closed empty state", () => {
    render(<HealthScheduledChecksWorkspace {...baseProps} />);

    expect(screen.getByRole("heading", { name: "Governed read-only checks" })).toBeVisible();
    expect(screen.getByText("No runnable authorized health checks")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Run check" })).toBeNull();
    expect(screen.queryByRole("button", { name: /execute|restart|deploy/i })).toBeNull();
  });

  it("keeps loading and failure states explicit", () => {
    const { rerender } = render(<HealthScheduledChecksWorkspace {...baseProps} loading />);

    expect(screen.getByText("Loading authorized health checks...")).toBeVisible();

    rerender(<HealthScheduledChecksWorkspace {...baseProps} error />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Authorized health-check context is unavailable.",
    );
  });

  it("delegates definition selection and a bounded read-only run", () => {
    const onRunCheck = vi.fn();
    const onSelectDefinition = vi.fn();
    render(
      <HealthScheduledChecksWorkspace
        {...baseProps}
        onRunCheck={onRunCheck}
        onSelectDefinition={onSelectDefinition}
        overview={overview}
        selectedDefinition={definition}
        selectedRun={run}
        selectedSchedule={schedule}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /Storage capacity utilization/ }));
    fireEvent.click(screen.getByRole("button", { name: "Run check" }));

    expect(onSelectDefinition).toHaveBeenCalledWith("health.capacity");
    expect(onRunCheck).toHaveBeenCalledOnce();
  });

  it("presents observations and limits while enforcing disabled and pending gates", () => {
    const { rerender } = render(
      <HealthScheduledChecksWorkspace
        {...baseProps}
        overview={overview}
        selectedDefinition={{ ...definition, enabled: false }}
        selectedRun={run}
        selectedSchedule={schedule}
      />,
    );

    expect(screen.getByText("controller.status")).toBeVisible();
    expect(screen.getByText("Controller warning requires correlation")).toBeVisible();
    expect(screen.getByText("Authorized event-log evidence is not configured.")).toBeVisible();
    expect(screen.getByText("The warning duration is unknown.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run check" })).toBeDisabled();
    expect(screen.getByText(/does not authorize infrastructure change/)).toBeVisible();

    rerender(
      <HealthScheduledChecksWorkspace
        {...baseProps}
        overview={overview}
        runPending
        selectedDefinition={definition}
        selectedRun={run}
        selectedSchedule={schedule}
      />,
    );
    expect(screen.getByRole("button", { name: "Running" })).toBeDisabled();
  });
});
