import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorWorkspaceNavigation } from "./ConnectorWorkspaceNavigation";

describe("ConnectorWorkspaceNavigation", () => {
  afterEach(() => cleanup());

  it("exposes the four connector task views and selects the requested view", () => {
    const onNavigate = vi.fn();
    render(<ConnectorWorkspaceNavigation activeView="runtime" onNavigate={onNavigate} />);

    expect(screen.getAllByRole("tab")).toHaveLength(4);
    expect(screen.getByRole("tab", { name: "Runtime" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("tab", { name: "Knowledge" }));
    expect(onNavigate).toHaveBeenCalledWith("knowledge");
  });

  it("supports roving keyboard navigation", () => {
    const onNavigate = vi.fn();
    render(<ConnectorWorkspaceNavigation activeView="inventory" onNavigate={onNavigate} />);

    const inventory = screen.getByRole("tab", { name: "Inventory" });
    inventory.focus();
    fireEvent.keyDown(inventory, { key: "ArrowLeft" });
    expect(onNavigate).toHaveBeenLastCalledWith("knowledge");

    fireEvent.keyDown(inventory, { key: "End" });
    expect(onNavigate).toHaveBeenLastCalledWith("knowledge");
    fireEvent.keyDown(inventory, { key: "ArrowRight" });
    expect(onNavigate).toHaveBeenLastCalledWith("builder");
  });
});
