import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";
import DeploymentConfigurationWorkspace from "./DeploymentConfigurationWorkspace";

afterEach(() => cleanup());

const preview: DeploymentConfigurationPreview = {
  preview_id: "configuration-preview.test",
  schema_version: "atlas.deployment-configuration.v1",
  release_id: "release.atlas.lab-0.1.0",
  profile: "linux_lab",
  organization_id: "organization.enterprise",
  environment_id: "environment.test",
  site_id: "site.local",
  state: "failed",
  configuration_digest: "b".repeat(64),
  fields: [
    {
      path: "runtime.bind_address",
      display_value: "127.0.0.1",
      source: "release_default",
      sensitive: false,
    },
    {
      path: "database.password",
      display_value: "secret-reference:redacted",
      source: "overlay",
      sensitive: true,
    },
  ],
  validations: [
    {
      code: "configuration.network.private_bind",
      state: "passed",
      summary: "Administrative services remain privately bound.",
      evidence: "bind_address=127.0.0.1",
      remediation: null,
    },
    {
      code: "configuration.capacity.minimum",
      state: "failed",
      summary: "Minimum capacity is not satisfied.",
      evidence: "available_memory_mb=2048",
      remediation: "Increase memory before bootstrap.",
    },
  ],
  generated_at: "2026-08-10T09:00:00Z",
  correlation_id: "correlation.configuration.test",
  mutation_authorized: false,
  execution_authorized: false,
};

describe("DeploymentConfigurationWorkspace", () => {
  it("presents immutable configuration identity and effective fields", () => {
    render(<DeploymentConfigurationWorkspace preview={preview} />);

    expect(screen.getByRole("heading", { name: "Versioned deployment preview" })).toBeVisible();
    expect(screen.getByText("linux lab")).toBeVisible();
    expect(screen.getByText("environment.test")).toBeVisible();
    expect(screen.getByText("atlas.deployment-configuration.v1")).toBeVisible();
    expect(screen.getByText("runtime.bind_address")).toBeVisible();
    expect(screen.getByText("127.0.0.1")).toBeVisible();
  });

  it("shows only the server-provided redacted sensitive display value", () => {
    render(<DeploymentConfigurationWorkspace preview={preview} />);

    expect(screen.getByText("database.password")).toBeVisible();
    expect(screen.getByText("secret-reference:redacted")).toBeVisible();
    expect(screen.queryByText(/private-key-value|plaintext-password/i)).toBeNull();
  });

  it("presents validation remediation without mutation authority", () => {
    render(<DeploymentConfigurationWorkspace preview={preview} />);

    expect(screen.getByText("Minimum capacity is not satisfied.")).toBeVisible();
    expect(screen.getByText("Increase memory before bootstrap.")).toBeVisible();
    expect(
      screen.getByText(/No file write, secret provisioning, port change, installation/),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /write|provision|install|execute|deploy/i })).toBeNull();
  });
});
