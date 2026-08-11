import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { BootstrapState } from "../../api/bootstrapState";
import BootstrapCheckpointWorkspace from "./BootstrapCheckpointWorkspace";

afterEach(() => cleanup());

const state: BootstrapState = {
  run: {
    run_id: "bootstrap-run.test",
    version: 3,
    state: "active",
    release_id: "release.atlas.lab-0.1.0",
    profile: "linux_lab",
    organization_id: "organization.enterprise",
    environment_id: "environment.test",
    site_id: "site.local",
    plan_digest: "d".repeat(64),
    resume_key: "resume.bootstrap.test",
    configuration_digest: "e".repeat(64),
    phase_ids: ["phase.acquire", "phase.configure", "phase.trust"],
    checkpoints: [
      {
        phase_id: "phase.acquire",
        state: "completed",
        safe_output_references: ["artifact.release"],
        recorded_at: "2026-08-10T16:00:00Z",
      },
    ],
    completed_phase_ids: ["phase.acquire"],
    failed_phase_id: null,
    current_phase_id: "phase.configure",
    lease_expires_at: "2026-08-10T18:30:00Z",
    created_at: "2026-08-10T15:00:00Z",
    updated_at: "2026-08-10T18:00:00Z",
    artifact_acquisition: null,
    configuration_rendering: null,
    trust_provisioning: null,
    data_initialization: null,
    service_deployment: null,
    identity_handoff: null,
    integration_validation: null,
    end_to_end_verification: null,
    operational_handoff: null,
  },
  durable: true,
  lease_available: false,
  lease_held_by_current_actor: true,
  execution_authorized: false,
  infrastructure_mutation_authorized: false,
};

const formatTimestamp = (timestamp: string | undefined) =>
  timestamp ? `formatted:${timestamp}` : "Unknown";

describe("BootstrapCheckpointWorkspace", () => {
  it("presents durable run identity and bounded lease evidence", () => {
    render(<BootstrapCheckpointWorkspace formatTimestamp={formatTimestamp} state={state} />);

    expect(screen.getByRole("heading", { name: "Resume and lease state" })).toBeVisible();
    expect(screen.getByText("durable")).toBeVisible();
    expect(screen.getByText("bootstrap-run.test")).toBeVisible();
    expect(screen.getByText("1/3")).toBeVisible();
    expect(screen.getByText("Held by this session")).toBeVisible();
    expect(screen.getByText(`${"d".repeat(20)}...`)).toBeVisible();
    expect(screen.getByText("formatted:2026-08-10T18:30:00Z")).toBeVisible();
  });

  it("preserves ordered completed, current, and pending checkpoint evidence", () => {
    render(<BootstrapCheckpointWorkspace formatTimestamp={formatTimestamp} state={state} />);

    const progress = screen.getByLabelText("Bootstrap checkpoint progress");
    const checkpoints = within(progress).getAllByText(/phase\./).map((item) => item.textContent);
    expect(checkpoints).toEqual(["phase.acquire", "phase.configure", "phase.trust"]);
    expect(within(progress).getByText("completed")).toBeVisible();
    expect(within(progress).getByText("current")).toBeVisible();
    expect(within(progress).getByText("pending")).toBeVisible();
  });

  it("uses privacy-bounded lease labels without operational controls", () => {
    render(
      <BootstrapCheckpointWorkspace
        formatTimestamp={formatTimestamp}
        state={{ ...state, lease_held_by_current_actor: false }}
      />,
    );

    expect(screen.getByText("Held by another operator")).toBeVisible();
    expect(screen.queryByText(/subject\.|lease-owner|user-id/i)).toBeNull();
    expect(
      screen.queryByRole("button", { name: /claim|lease|run|execute|rollback|deploy/i }),
    ).toBeNull();
  });

  it("presents an empty non-durable checkpoint state without claiming a lease", () => {
    render(
      <BootstrapCheckpointWorkspace
        formatTimestamp={formatTimestamp}
        state={{ ...state, run: null, durable: false, lease_available: true }}
      />,
    );

    expect(screen.getByText("development memory")).toBeVisible();
    expect(screen.getByText("No checkpoint state has been initialized.")).toBeVisible();
    expect(screen.getByText(/approved plan remains read-only and no lease is held/)).toBeVisible();
  });
});
