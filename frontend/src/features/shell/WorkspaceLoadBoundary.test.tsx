import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceLoadBoundary, WorkspaceRouteLoading } from "./WorkspaceLoadBoundary";

function BrokenWorkspace(): never {
  throw new Error("chunk details must remain private");
}

describe("WorkspaceLoadBoundary", () => {
  it("announces a bounded workspace loading state", () => {
    render(<WorkspaceRouteLoading workspace="Health" />);

    expect(screen.getByRole("main")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("heading", { name: "Loading Health" })).toBeVisible();
  });

  it("fails closed and offers an explicit reload action", () => {
    const reload = vi.fn();
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <WorkspaceLoadBoundary resetKey="health" workspace="Health" onReload={reload}>
        <BrokenWorkspace />
      </WorkspaceLoadBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("No operational state or authority");
    fireEvent.click(screen.getByRole("button", { name: "Reload application" }));
    expect(reload).toHaveBeenCalledOnce();
  });
});
