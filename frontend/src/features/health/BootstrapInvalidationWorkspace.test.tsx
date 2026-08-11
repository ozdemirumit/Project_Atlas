import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { BootstrapInvalidationPreview } from "../../api/bootstrapInvalidation";
import BootstrapInvalidationWorkspace from "./BootstrapInvalidationWorkspace";

afterEach(() => cleanup());

const preview: BootstrapInvalidationPreview = {
  preview_id: "bootstrap-invalidation.test",
  schema_version: "atlas.bootstrap-invalidation.v1",
  state: "drifted",
  source_run_id: "bootstrap-run.test",
  source_run_version: 4,
  changes: [
    {
      field: "configuration_digest",
      reason_code: "bootstrap.configuration.changed",
      old_reference: "old-sensitive-reference",
      new_reference: "new-sensitive-reference",
      earliest_affected_phase_id: "phase.configure",
    },
  ],
  earliest_affected_phase_id: "phase.configure",
  reusable_checkpoint_phase_ids: ["phase.acquire"],
  invalidated_checkpoint_phase_ids: ["phase.configure", "phase.trust"],
  downstream_phase_ids: ["phase.data", "phase.services"],
  remediation: "Review the configuration drift before rebasing.",
  generated_at: "2026-08-11T06:00:00Z",
  correlation_id: "correlation.bootstrap-invalidation.test",
  execution_authorized: false,
  lease_mutation_authorized: false,
  checkpoint_mutation_authorized: false,
  infrastructure_mutation_authorized: false,
};

describe("BootstrapInvalidationWorkspace", () => {
  it("presents drift identity, counts, and bounded change reasons", () => {
    render(<BootstrapInvalidationWorkspace preview={preview} />);

    expect(screen.getByRole("heading", { name: "Checkpoint invalidation preview" })).toBeVisible();
    expect(screen.getByText("drifted")).toBeVisible();
    expect(screen.getByText("bootstrap.configuration.changed")).toBeVisible();
    expect(screen.getByText("configuration digest")).toBeVisible();
    expect(screen.getByText("from phase.configure")).toBeVisible();
  });

  it("preserves reusable, invalidated, and downstream phase classifications", () => {
    render(<BootstrapInvalidationWorkspace preview={preview} />);

    const columns = document.querySelector<HTMLElement>(".bootstrap-invalidation-columns");
    expect(columns).not.toBeNull();
    expect(within(columns!).getByText("phase.acquire")).toBeVisible();
    expect(within(columns!).getByText("phase.configure, phase.trust")).toBeVisible();
    expect(within(columns!).getByText("phase.data, phase.services")).toBeVisible();
  });

  it("does not disclose references or expose operational controls", () => {
    render(<BootstrapInvalidationWorkspace preview={preview} />);

    expect(screen.queryByText("old-sensitive-reference")).toBeNull();
    expect(screen.queryByText("new-sensitive-reference")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /review|confirm|rebase|run|execute|rollback/i }),
    ).toBeNull();
  });

  it("presents empty and unchanged evidence without inferring drift", () => {
    const { rerender } = render(
      <BootstrapInvalidationWorkspace
        preview={{
          ...preview,
          state: "empty",
          source_run_id: null,
          source_run_version: null,
          changes: [],
          earliest_affected_phase_id: null,
          reusable_checkpoint_phase_ids: [],
          invalidated_checkpoint_phase_ids: [],
          downstream_phase_ids: [],
        }}
      />,
    );

    expect(screen.getByText("No current run is available for drift comparison.")).toBeVisible();

    rerender(
      <BootstrapInvalidationWorkspace
        preview={{
          ...preview,
          state: "unchanged",
          changes: [],
          earliest_affected_phase_id: null,
          invalidated_checkpoint_phase_ids: [],
          downstream_phase_ids: [],
        }}
      />,
    );
    expect(screen.getByText("unchanged")).toBeVisible();
    expect(screen.getByText("none")).toBeVisible();
    expect(screen.queryByText(/configuration changed/i)).toBeNull();
  });
});
