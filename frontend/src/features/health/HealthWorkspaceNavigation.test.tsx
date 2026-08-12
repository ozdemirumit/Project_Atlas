import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthWorkspaceNavigation } from "./HealthWorkspaceNavigation";
import { healthViewDescriptor } from "./healthWorkspace";

afterEach(() => cleanup());

describe("HealthWorkspaceNavigation", () => {
  it("presents the active task view and emits an explicit destination", () => {
    const onNavigate = vi.fn();
    render(<HealthWorkspaceNavigation activeView="overview" onNavigate={onNavigate} />);

    expect(screen.getByRole("tab", { name: "Inventory" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Governance" })).toHaveAttribute("tabindex", "-1");

    fireEvent.click(screen.getByRole("tab", { name: "Deployments" }));
    expect(onNavigate).toHaveBeenCalledWith("deployments");
  });

  it("provides stable heading copy for each view", () => {
    expect(healthViewDescriptor("overview").title).toBe(
      "Infrastructure inventory and health",
    );
    expect(healthViewDescriptor("investigate").title).toBe("Investigate infrastructure");
    expect(healthViewDescriptor("governance").description).toContain("Human review");
  });

  it("supports horizontal and boundary keyboard navigation", () => {
    const onNavigate = vi.fn();
    render(<HealthWorkspaceNavigation activeView="overview" onNavigate={onNavigate} />);

    const overview = screen.getByRole("tab", { name: "Inventory" });
    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(onNavigate).toHaveBeenLastCalledWith("investigate");
    expect(screen.getByRole("tab", { name: "Investigate" })).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("tab", { name: "Investigate" }), { key: "End" });
    expect(onNavigate).toHaveBeenLastCalledWith("governance");
    expect(screen.getByRole("tab", { name: "Governance" })).toHaveFocus();
  });
});
