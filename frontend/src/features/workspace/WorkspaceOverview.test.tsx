import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceOverview } from "./WorkspaceOverview";

describe("WorkspaceOverview", () => {
  it("groups implemented capabilities and navigates to their exact task views", () => {
    const onNavigate = vi.fn();
    render(<WorkspaceOverview onNavigate={onNavigate} />);

    expect(screen.getByLabelText("Workspace coverage")).toHaveTextContent("13");
    expect(screen.getAllByRole("button")).toHaveLength(13);
    expect(screen.getByRole("heading", { name: "Infrastructure operations" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Connector lifecycle" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "AI decision support" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Enterprise controls" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: /MCP Builder/ }));
    expect(onNavigate).toHaveBeenCalledWith({ workspace: "Connectors", view: "builder" });
    fireEvent.click(screen.getByRole("button", { name: /Inventory and health/ }));
    expect(onNavigate).toHaveBeenCalledWith({ workspace: "Health", view: "overview" });
    fireEvent.click(screen.getByRole("button", { name: /Identity and access/ }));
    expect(onNavigate).toHaveBeenCalledWith({ workspace: "Health", view: "governance" });
    expect(screen.getByRole("button", { name: /Runtime governance/ })).toHaveTextContent(
      "Connectors / Runtime",
    );
  });
});
