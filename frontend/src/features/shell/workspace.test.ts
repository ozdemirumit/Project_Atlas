import { describe, expect, it } from "vitest";

import { isKnownWorkspaceHash, workspaceFromHash, workspaceHash } from "./workspace";

describe("workspace navigation", () => {
  it("supports direct links for every active workspace", () => {
    expect(workspaceFromHash("#/workspace")).toBe("Workspace");
    expect(workspaceFromHash("#/health")).toBe("Health");
    expect(workspaceFromHash("#/connectors")).toBe("Connectors");
    expect(workspaceHash("Connectors")).toBe("#/connectors");
  });

  it("fails unknown destinations back to Workspace", () => {
    expect(isKnownWorkspaceHash("#/reports")).toBe(false);
    expect(workspaceFromHash("#/reports")).toBe("Workspace");
    expect(workspaceFromHash("")).toBe("Workspace");
  });
});
