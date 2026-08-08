import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectorLifecycleOverview } from "./ConnectorLifecycleOverview";

describe("ConnectorLifecycleOverview", () => {
  it("distinguishes platform coverage from instance authority", () => {
    render(<ConnectorLifecycleOverview />);

    expect(screen.getByRole("heading", { name: "Connector lifecycle" })).toBeVisible();
    expect(screen.getByLabelText("Delivery status")).toHaveTextContent(
      "10Available stages0In progressRecommendation adjudicationLatest available capability",
    );
    expect(screen.getAllByText("Available")).toHaveLength(10);
    expect(screen.getByText("Evidence preservation")).toBeVisible();
    expect(screen.getByText("Knowledge publication")).toBeVisible();
    expect(screen.getByText("Retrieval publication")).toBeVisible();
    expect(screen.getByText("Governed retrieval")).toBeVisible();
    expect(screen.getByText("Context assembly")).toBeVisible();
    expect(screen.getByText("Model invocation")).toBeVisible();
    expect(screen.getByText("Draft adjudication")).toBeVisible();
    expect(screen.getByText("Answer presentation")).toBeVisible();
    expect(screen.getByText("Recommendation candidates")).toBeVisible();
    expect(screen.getByText("Service-impact enrichment")).toBeVisible();
    expect(screen.getByText("Risk/recovery completion")).toBeVisible();
    expect(screen.getAllByText("Recommendation adjudication")).toHaveLength(2);
    expect(screen.getByText("AI context")).toBeVisible();
    expect(screen.getByText("In progress")).toBeVisible();
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
    expect(within(knowledge as HTMLElement).getByText("Available")).toBeVisible();
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
    expect(within(knowledge as HTMLElement).getByText("Finding presentation")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Review decisions")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(
      within(knowledge as HTMLElement).getByText("Correction resubmission"),
    ).toHaveAttribute("data-state", "available");
    expect(within(knowledge as HTMLElement).getByText("Final resolution")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Publication preparation")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Source materialization")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Deterministic chunking")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Embedding generation")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Index staging")).toHaveAttribute(
      "data-state",
      "available",
    );
    expect(within(knowledge as HTMLElement).getByText("Governed retrieval")).toHaveAttribute(
      "data-state",
      "available",
    );
  });
});
