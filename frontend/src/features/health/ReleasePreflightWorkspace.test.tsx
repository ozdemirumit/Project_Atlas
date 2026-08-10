import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReleasePreflight } from "../../api/releasePreflight";
import ReleasePreflightWorkspace from "./ReleasePreflightWorkspace";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const preflight: ReleasePreflight = {
  report_id: "preflight.test",
  release_id: "release.atlas.lab-0.1.0",
  release_version: "0.1.0",
  build_id: "build.synthetic.main",
  manifest_digest: "a".repeat(64),
  mode: "offline",
  profile: "linux_lab",
  state: "warning",
  checks: [
    {
      code: "release.signature.valid",
      category: "release",
      state: "passed",
      mandatory: true,
      summary: "Release manifest signature is valid.",
      evidence: "Verified against the approved release trust reference.",
      remediation: null,
    },
    {
      code: "host.capacity.review",
      category: "host",
      state: "warning",
      mandatory: true,
      summary: "Host capacity needs operator review.",
      evidence: "Available memory is near the recommended threshold.",
      remediation: "Review capacity before installation.",
    },
  ],
  generated_at: "2026-08-10T09:00:00Z",
  correlation_id: "correlation.preflight.test",
  mutation_authorized: false,
  execution_authorized: false,
};

const baseProps = {
  mode: "offline" as const,
  onModeChange: vi.fn(),
  onProfileChange: vi.fn(),
  preflight,
  profile: "linux_lab" as const,
};

describe("ReleasePreflightWorkspace", () => {
  it("presents immutable release identity and bounded check evidence", () => {
    render(<ReleasePreflightWorkspace {...baseProps} />);

    expect(screen.getByRole("heading", { name: "Read-only deployment preflight" })).toBeVisible();
    expect(screen.getByText("0.1.0")).toBeVisible();
    expect(screen.getByText("build.synthetic.main")).toBeVisible();
    expect(screen.getByText("2 checks")).toBeVisible();
    expect(screen.getByText("Release manifest signature is valid.")).toBeVisible();
    expect(screen.getByText("Host capacity needs operator review.")).toBeVisible();
  });

  it("delegates acquisition mode and deployment profile selection", () => {
    const onModeChange = vi.fn();
    const onProfileChange = vi.fn();
    render(
      <ReleasePreflightWorkspace
        {...baseProps}
        onModeChange={onModeChange}
        onProfileChange={onProfileChange}
      />,
    );

    fireEvent.change(screen.getByLabelText("Release acquisition mode"), {
      target: { value: "mirrored" },
    });
    fireEvent.change(screen.getByLabelText("Release deployment profile"), {
      target: { value: "developer" },
    });

    expect(onModeChange).toHaveBeenCalledWith("mirrored");
    expect(onProfileChange).toHaveBeenCalledWith("developer");
  });

  it("keeps remediation and no-authority language explicit", () => {
    render(<ReleasePreflightWorkspace {...baseProps} />);

    expect(screen.getByText("Review capacity before installation.")).toBeVisible();
    expect(
      screen.getByText(/No installation, mutation, deployment, or execution is authorized/),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /install|deploy|execute|approve/i })).toBeNull();
  });
});

