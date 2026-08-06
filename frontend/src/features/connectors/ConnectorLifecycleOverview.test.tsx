import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectorLifecycleOverview } from "./ConnectorLifecycleOverview";

describe("ConnectorLifecycleOverview", () => {
  it("distinguishes platform coverage from instance authority", () => {
    render(<ConnectorLifecycleOverview />);

    expect(screen.getByRole("heading", { name: "Connector lifecycle" })).toBeVisible();
    expect(screen.getAllByText("Available")).toHaveLength(8);
    expect(screen.getByText("Evidence preservation")).toBeVisible();
    expect(screen.queryByText("In progress")).not.toBeInTheDocument();
    expect(screen.getByText("Knowledge publication")).toBeVisible();
    expect(screen.getByText("Not enabled")).toBeVisible();
    expect(
      screen.getByText(
        "Availability is platform capability coverage, not authority for a connector instance.",
      ),
    ).toBeVisible();
    const bounded = screen.getByText("Bounded operations").closest(".connector-lifecycle-row");
    expect(bounded).not.toBeNull();
    expect(within(bounded as HTMLElement).getByText("Available")).toBeVisible();
  });
});
