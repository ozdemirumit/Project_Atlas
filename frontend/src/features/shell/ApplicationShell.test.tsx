import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApplicationSidebar, ApplicationTopbar } from "./ApplicationShell";

describe("ApplicationShell", () => {
  it("exposes only distinct workspaces and reports the active destination", () => {
    const onNavigate = vi.fn();
    render(
      <ApplicationSidebar
        activeWorkspace="Workspace"
        authenticationMethod="development"
        credentialKind="browser_session"
        displayName="Atlas Operator"
        onClose={vi.fn()}
        onNavigate={onNavigate}
        open={false}
        platformState="healthy"
      />,
    );

    expect(screen.getByRole("button", { name: "Workspace" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("navigation").querySelectorAll("button")).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "Infrastructure" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Governance" })).not.toBeInTheDocument();
    expect(screen.getByText("Signed in")).toBeVisible();
    expect(screen.queryByText("development identity")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Health" }));
    expect(onNavigate).toHaveBeenCalledWith("Health");
  });

  it("does not expose placeholder topbar controls", () => {
    render(
      <ApplicationTopbar
        inspectorOpen={false}
        logoutPending={false}
        onLogout={vi.fn()}
        onOpenNavigation={vi.fn()}
        onToggleInspector={vi.fn()}
        showInspector={false}
        showLogout={false}
      />,
    );

    expect(screen.getByLabelText("Current scope")).toHaveTextContent("Enterprise estate");
    expect(screen.queryByRole("button", { name: "Notifications" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Search infrastructure" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open context panel" })).not.toBeInTheDocument();
  });
});
