import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceOverview } from "./WorkspaceOverview";

describe("WorkspaceOverview", () => {
  it("groups implemented capabilities and navigates to their owning workspace", () => {
    const onNavigate = vi.fn();
    render(<WorkspaceOverview onNavigate={onNavigate} />);

    expect(screen.getByLabelText("Workspace coverage")).toHaveTextContent("13");
    expect(screen.getAllByRole("button")).toHaveLength(13);
    expect(screen.getByRole("heading", { name: "Infrastructure operations" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Connector lifecycle" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "AI decision support" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Enterprise controls" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: /MCP Builder/ }));
    expect(onNavigate).toHaveBeenCalledWith("Connectors");
    fireEvent.click(screen.getByRole("button", { name: /Inventory and health/ }));
    expect(onNavigate).toHaveBeenCalledWith("Health");
  });
});
