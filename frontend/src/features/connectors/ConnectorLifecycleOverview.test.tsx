import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectorLifecycleOverview } from "./ConnectorLifecycleOverview";

describe("ConnectorLifecycleOverview", () => {
  it("distinguishes platform coverage from instance authority", () => {
    render(<ConnectorLifecycleOverview />);

    expect(screen.getByRole("heading", { name: "Connector lifecycle" })).toBeVisible();
    expect(screen.getByLabelText("Delivery status")).toHaveTextContent(
      "8Available stages1In progressReview findingsLatest available capability",
    );
    expect(screen.getAllByText("Available")).toHaveLength(8);
    expect(screen.getByText("Evidence preservation")).toBeVisible();
    expect(screen.getByText("Knowledge publication")).toBeVisible();
    expect(screen.getAllByText("In progress")).toHaveLength(2);
    expect(screen.queryByText("Not enabled")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Availability is platform capability coverage, not authority for a connector instance.",
      ),
    ).toBeVisible();
    const bounded = screen.getByText("Bounded operations").closest(".connector-lifecycle-row");
    expect(bounded).not.toBeNull();
    expect(within(bounded as HTMLElement).getByText("Available")).toBeVisible();
    const knowledge = screen.getByText("Knowledge publication").closest(".connector-lifecycle-row");
    expect(knowledge).not.toBeNull();
    expect(within(knowledge as HTMLElement).getByText("In progress")).toBeVisible();
    expect(
      within(knowledge as HTMLElement).getByText("Draft curation"),
    ).toHaveAttribute("data-state", "available");
    expect(within(knowledge as HTMLElement).getByText("Review request")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Reviewer assignment")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Inspection lease")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Content presentation")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Review findings")).toHaveAttribute(
      "data-state",
      "available",
    );
  });
});
