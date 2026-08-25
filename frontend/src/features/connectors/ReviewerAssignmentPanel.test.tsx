import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { knowledgeReviewRequestInventoryItem as reviewRequest } from
  "./testKnowledgeReviewRequestFixture";
import {
  reviewerAssignmentClaimStatus as claimStatus,
  reviewerAssignmentInventoryItem as assignment,
  reviewerAssignmentOption as option,
} from "./testReviewerAssignmentFixture";
import { ReviewerAssignmentPanel } from "./ReviewerAssignmentPanel";

const meta = {
  correlation_id: "cor_reviewer_assignment_panel_test",
  generated_at: "2026-08-25T00:10:10Z",
};

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPanel(
  onRequestEnterpriseLogin?: () => void,
  queryClient = createQueryClient(),
) {
  return render(
    <QueryClientProvider client={queryClient}>
      <ReviewerAssignmentPanel
        reviewRequest={reviewRequest}
        onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        sessionScopeKey="test-session"
      />
    </QueryClientProvider>,
  );
}

function requestUrl(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : input.toString();
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ReviewerAssignmentPanel", () => {
  it("assigns from a signed option and exposes only minimized lifecycle state", async () => {
    let inventory = [] as typeof assignment[];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = requestUrl(input);
      if (init?.method === "POST") {
        inventory = [assignment];
        return Promise.resolve(
          new Response(JSON.stringify({ data: assignment, meta }), { status: 201 }),
        );
      }
      if (url.includes("/options")) {
        return Promise.resolve(
          new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ data: inventory, meta }), { status: 200 }),
      );
    });
    renderPanel();

    expect(await screen.findByText(option.assignment_policy_id)).toBeVisible();
    expect(screen.getByText("single factor")).toBeVisible();
    expect(screen.queryByRole("textbox", {
      name: /policy|digest|reviewer|group|directory|queue|routing|result/i,
    })).toBeNull();
    fireEvent.click(screen.getByLabelText(/assigns distinct eligible domain and security/i));
    fireEvent.click(screen.getByRole("button", { name: "Assign reviewers" }));

    await waitFor(() => expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1));
    expect(await screen.findByText("reviewers assigned")).toBeVisible();
    expect(screen.getAllByText("assigned")).toHaveLength(2);
    expect(screen.getByText(new Date(assignment.expires_at).toLocaleString())).toBeVisible();
    for (const secret of [
      "reviewer@example.invalid", "hidden.reviewer", "group.reviewers", "subject.requester",
      "c".repeat(64),
    ]) expect(screen.queryByText(secret)).toBeNull();
    expect(screen.queryByRole("button", {
      name: /inspect|finding|decide|approve|publish|retrieve|model|workflow|execute|deploy|mutate/i,
    })).toBeNull();
  });

  it("renders an authoritative existing assignment without loading options", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [assignment], meta }), { status: 200 }),
    );
    renderPanel();

    expect(await screen.findByText("reviewers assigned")).toBeVisible();
    expect(fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("/options"))).toBe(false);
    expect(screen.queryByRole("button", { name: "Assign reviewers" })).toBeNull();
  });

  it("renders an authoritative consumed claim and never offers retry", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [claimStatus], meta }), { status: 200 }),
    );
    renderPanel();

    expect(await screen.findByText("Reviewer assignment claim consumed")).toBeVisible();
    expect(screen.getByText(/Automatic retry remains permanently disabled/i)).toBeVisible();
    expect(fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("/options"))).toBe(false);
    expect(screen.queryByRole("button", { name: "Assign reviewers" })).toBeNull();
  });

  it("permanently locks a failed POST across panel remount", async () => {
    const queryClient = createQueryClient();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (init?.method === "POST") return Promise.resolve(new Response(null, { status: 503 }));
      if (requestUrl(input).includes("/options")) {
        return Promise.resolve(
          new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ data: [], meta }), { status: 200 }),
      );
    });
    const firstRender = renderPanel(undefined, queryClient);

    await screen.findByText(option.assignment_policy_id);
    fireEvent.click(screen.getByLabelText(/assigns distinct eligible domain and security/i));
    fireEvent.click(screen.getByRole("button", { name: "Assign reviewers" }));
    expect(await screen.findByText(/permanently locked/i)).toBeVisible();
    firstRender.unmount();
    const secondRender = renderPanel(undefined, queryClient);

    expect(await within(secondRender.container).findByText(/permanently locked/i)).toBeVisible();
    expect(within(secondRender.container).queryByRole(
      "button",
      { name: "Assign reviewers" },
    )).toBeNull();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  });

  it("uses normal username and password recovery for a verified 401", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 401 }));
    renderPanel(onRequestEnterpriseLogin);

    expect(await screen.findByText(/username and password/i)).toBeVisible();
    expect(screen.queryByText(/MFA|authorized browser session/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledOnce();
  });
});
