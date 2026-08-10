import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { BootstrapPlan } from "../../api/bootstrapPlan";
import BootstrapPlanWorkspace from "./BootstrapPlanWorkspace";

afterEach(() => cleanup());

const plan: BootstrapPlan = {
  plan_id: "bootstrap-plan.test",
  schema_version: "atlas.bootstrap-plan.v1",
  release_id: "release.atlas.lab-0.1.0",
  profile: "linux_lab",
  organization_id: "organization.enterprise",
  environment_id: "environment.test",
  site_id: "site.local",
  state: "blocked",
  plan_digest: "c".repeat(64),
  resume_key: "resume.bootstrap.test",
  phases: [
    {
      phase_id: "phase.acquire",
      sequence: 1,
      title: "Acquire and verify artifacts",
      dependencies: [],
      state: "ready",
      resumable: true,
      input_references: ["release.manifest"],
      stop_guidance: "Stop if artifact verification fails.",
    },
    {
      phase_id: "phase.configure",
      sequence: 2,
      title: "Render configuration",
      dependencies: ["phase.acquire"],
      state: "blocked",
      resumable: true,
      input_references: ["configuration.preview"],
      stop_guidance: "Resolve configuration validation before continuing.",
    },
  ],
  generated_at: "2026-08-10T12:00:00Z",
  correlation_id: "correlation.bootstrap-plan.test",
  mutation_authorized: false,
  execution_authorized: false,
};

describe("BootstrapPlanWorkspace", () => {
  it("presents immutable plan identity and readiness", () => {
    const { container } = render(<BootstrapPlanWorkspace plan={plan} />);

    expect(screen.getByRole("heading", { name: "Ordered deployment phases" })).toBeVisible();
    expect(screen.getAllByText("blocked")).toHaveLength(2);
    expect(screen.getByText(`${"c".repeat(20)}...`)).toBeVisible();
    expect(screen.getByText("resume.bootstrap.test")).toBeVisible();
    const identity = container.querySelector(".bootstrap-plan-identity");
    expect(identity).not.toBeNull();
    expect(within(identity!).getByText("2")).toBeVisible();
  });

  it("preserves server phase order, dependencies, and stop guidance", () => {
    render(<BootstrapPlanWorkspace plan={plan} />);

    const phases = screen.getAllByRole("listitem");
    expect(phases).toHaveLength(2);
    expect(within(phases[0]!).getByText("Acquire and verify artifacts")).toBeVisible();
    expect(within(phases[0]!).getByText("No phase dependency")).toBeVisible();
    expect(within(phases[1]!).getByText("Render configuration")).toBeVisible();
    expect(within(phases[1]!).getByText("After phase.acquire")).toBeVisible();
    expect(
      within(phases[1]!).getByText("Resolve configuration validation before continuing."),
    ).toBeVisible();
  });

  it("presents planning evidence without operational authority", () => {
    render(<BootstrapPlanWorkspace plan={plan} />);

    expect(screen.getByText(/No phase, command, rollback, or infrastructure mutation/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /claim|rebase|run|execute|rollback|deploy/i }),
    ).toBeNull();
  });
});
