import { describe, expect, it } from "vitest";

import {
  capabilityDestinationHash,
  connectorViewFromHash,
  connectorViewHash,
  healthViewFromHash,
  healthViewHash,
  isKnownWorkspaceHash,
  workspaceFromHash,
  workspaceHash,
} from "./workspace";

describe("workspace navigation", () => {
  it("supports direct links for every active workspace", () => {
    expect(workspaceFromHash("#/workspace")).toBe("Workspace");
    expect(workspaceFromHash("#/health")).toBe("Health");
    expect(workspaceFromHash("#/health/deployments")).toBe("Health");
    expect(workspaceFromHash("#/connectors")).toBe("Connectors");
    expect(workspaceHash("Connectors")).toBe("#/connectors/inventory");
    expect(workspaceHash("Health")).toBe("#/health/overview");
  });

  it("supports URL-backed Connector task views and typed capability destinations", () => {
    expect(connectorViewFromHash("#/connectors/runtime")).toBe("runtime");
    expect(connectorViewFromHash("#/connectors")).toBe("inventory");
    expect(connectorViewHash("knowledge")).toBe("#/connectors/knowledge");
    expect(isKnownWorkspaceHash("#/connectors/builder")).toBe(true);
    expect(
      capabilityDestinationHash({ workspace: "Health", view: "governance" }),
    ).toBe("#/health/governance");
    expect(
      capabilityDestinationHash({ workspace: "Connectors", view: "runtime" }),
    ).toBe("#/connectors/runtime");
  });

  it("supports URL-backed Health task views", () => {
    expect(healthViewFromHash("#/health/investigate")).toBe("investigate");
    expect(healthViewFromHash("#/health/unknown")).toBe("overview");
    expect(healthViewHash("governance")).toBe("#/health/governance");
    expect(isKnownWorkspaceHash("#/health/deployments")).toBe(true);
  });

  it("fails unknown destinations back to Workspace", () => {
    expect(isKnownWorkspaceHash("#/reports")).toBe(false);
    expect(isKnownWorkspaceHash("#/health/unknown")).toBe(false);
    expect(isKnownWorkspaceHash("#/connectors/unknown")).toBe(false);
    expect(workspaceFromHash("#/reports")).toBe("Workspace");
    expect(workspaceFromHash("")).toBe("Workspace");
  });
});
