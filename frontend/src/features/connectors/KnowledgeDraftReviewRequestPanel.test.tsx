import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { evidenceKnowledgeDraftInventoryItem as draft } from "./testEvidenceDraftFixture";
import {
  knowledgeReviewRequestInventoryItem as reviewRequest,
  knowledgeReviewRequestOption as option,
} from "./testKnowledgeReviewRequestFixture";
import { KnowledgeDraftReviewRequestPanel } from "./KnowledgeDraftReviewRequestPanel";

const meta = {
  correlation_id: "cor_review_panel_test",
  generated_at: "2026-08-25T00:00:10Z",
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
      <KnowledgeDraftReviewRequestPanel
        draft={draft}
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

describe("KnowledgeDraftReviewRequestPanel", () => {
  it("creates one request from a signed option and exposes no downstream controls", async () => {
    let inventory = [] as typeof reviewRequest[];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = requestUrl(input);
      if (init?.method === "POST") {
        inventory = [reviewRequest];
        return Promise.resolve(
          new Response(JSON.stringify({ data: reviewRequest, meta }), { status: 201 }),
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

    expect(await screen.findByText(option.orchestration_policy_id)).toBeVisible();
    expect(screen.getByText("single factor")).toBeVisible();
    expect(screen.queryByRole("textbox", { name: /policy|digest|queue|reviewer/i })).toBeNull();
    fireEvent.click(screen.getByLabelText(/result is only an unassigned review request/i));
    fireEvent.click(screen.getByRole("button", { name: "Request review" }));

    await waitFor(() => expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1));
    expect(await screen.findByText(reviewRequest.review_request_id)).toBeVisible();
    expect(screen.getAllByText("awaiting reviewer")).toHaveLength(3);
    expect(screen.queryByRole("button", {
      name: /assign|inspect|decide|approve|publish|retrieve|model|workflow|execute|deploy/i,
    })).toBeNull();
  });

  it("renders an authoritative existing request without loading options", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [reviewRequest], meta }), { status: 200 }),
    );
    renderPanel();

    expect(await screen.findByText(reviewRequest.review_request_id)).toBeVisible();
    expect(fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("/options"))).toBe(false);
    expect(screen.queryByRole("button", { name: "Request review" })).toBeNull();
  });

  it("permanently locks a failed POST and offers inventory reconciliation only", async () => {
    let inventoryReads = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = requestUrl(input);
      if (init?.method === "POST") return Promise.resolve(new Response(null, { status: 503 }));
      if (url.includes("/options")) {
        return Promise.resolve(
          new Response(JSON.stringify({ data: [option], meta }), { status: 200 }),
        );
      }
      inventoryReads += 1;
      return Promise.resolve(
        new Response(JSON.stringify({ data: [], meta }), { status: 200 }),
      );
    });
    renderPanel();

    await screen.findByText(option.orchestration_policy_id);
    fireEvent.click(screen.getByLabelText(/result is only an unassigned review request/i));
    fireEvent.click(screen.getByRole("button", { name: "Request review" }));
    expect(await screen.findByText(/permanently locked/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Request review" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reload inventory" }));

    await waitFor(() => expect(inventoryReads).toBeGreaterThanOrEqual(3));
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Request review" })).toBeNull();
  });

  it("preserves the permanent attempt lock after the dialog panel is remounted", async () => {
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

    await screen.findByText(option.orchestration_policy_id);
    fireEvent.click(screen.getByLabelText(/result is only an unassigned review request/i));
    fireEvent.click(screen.getByRole("button", { name: "Request review" }));
    expect(await screen.findByText(/permanently locked/i)).toBeVisible();
    firstRender.unmount();
    const secondRender = renderPanel(undefined, queryClient);

    expect(await within(secondRender.container).findByText(/permanently locked/i)).toBeVisible();
    expect(within(secondRender.container).queryByRole(
      "button",
      { name: "Request review" },
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
