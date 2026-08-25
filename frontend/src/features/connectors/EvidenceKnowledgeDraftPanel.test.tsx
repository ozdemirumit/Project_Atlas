import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvidenceKnowledgeDraftPanel } from "./EvidenceKnowledgeDraftPanel";
import {
  evidenceKnowledgeDraftInventoryItem as draft,
  evidenceKnowledgeDraftOption as option,
} from "./testEvidenceDraftFixture";
import { invocationEvidenceInventoryItem as evidence } from "./testInvocationEvidenceFixture";

const meta = {
  correlation_id: "cor_evidence_draft_panel",
  generated_at: "2026-08-25T00:00:08Z",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify({ data, meta }), { status });
}

function renderPanel(onRequestEnterpriseLogin?: () => void) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <EvidenceKnowledgeDraftPanel
        evidence={evidence}
        onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        sessionScopeKey="test-session"
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("EvidenceKnowledgeDraftPanel", () => {
  it("shows loading and empty signed-option states without curation controls", async () => {
    let releaseInventory: ((value: Response) => void) | undefined;
    vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => new Promise((resolve) => { releaseInventory = resolve; }))
      .mockResolvedValueOnce(json([]));
    renderPanel();

    expect(screen.getByText("Loading authoritative knowledge draft inventory...")).toBeVisible();
    releaseInventory?.(json([]));
    expect(await screen.findByText("No signed curation option is available")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Create knowledge draft" })).toBeNull();
  });

  it("creates one draft from a server option and exposes no later authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = input instanceof Request ? input.url : input.toString();
      if (init?.method === "POST") return Promise.resolve(json(draft, 201));
      if (url.includes("/options")) return Promise.resolve(json([option]));
      return Promise.resolve(fetchMock.mock.calls.some((call) => call[1]?.method === "POST")
        ? json([draft])
        : json([]));
    });
    renderPanel();

    expect(await screen.findByText(option.curation_policy_id)).toBeVisible();
    expect(screen.getByText("single factor")).toBeVisible();
    expect(screen.queryByRole("textbox", { name: /policy|digest|classification|acl|retention/i }))
      .toBeNull();
    fireEvent.click(screen.getByLabelText(/result is an unapproved/i));
    fireEvent.click(screen.getByRole("button", { name: "Create knowledge draft" }));

    expect(await screen.findByText(draft.title)).toBeVisible();
    expect(screen.getByText("not published")).toBeVisible();
    for (const authority of [/request review/i, /approve/i, /publish/i, /index/i, /embed/i,
      /retrieve/i, /model context/i, /schedule/i, /workflow/i, /execute/i, /deploy/i, /mutate/i]) {
      expect(screen.queryByRole("button", { name: authority })).toBeNull();
    }
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(post).toBeDefined();
    const body = JSON.parse(
      typeof post?.[1]?.body === "string" ? post[1].body : "{}",
    ) as unknown;
    expect(body).toEqual({
      schema_version: "atlas.operational-evidence-knowledge-draft-input.v1",
      source_ingestion_id: evidence.ingestion_id,
      curation_option_id: option.curation_option_id,
      purpose: "Create a governed unapproved draft from this exact immutable operational evidence.",
      acknowledged_result_is_an_unapproved_non_retrievable_draft: true,
    });
  });

  it.each([409, 422, 503])("permanently locks a failed %s POST and only reloads inventory", async (status) => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = input instanceof Request ? input.url : input.toString();
      if (init?.method === "POST") return Promise.resolve(new Response(null, { status }));
      if (url.includes("/options")) return Promise.resolve(json([option]));
      return Promise.resolve(json([]));
    });
    renderPanel();

    await screen.findByText(option.curation_policy_id);
    fireEvent.click(screen.getByLabelText(/result is an unapproved/i));
    fireEvent.click(screen.getByRole("button", { name: "Create knowledge draft" }));
    expect(await screen.findByText("Draft attempt requires inventory reconciliation")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Create knowledge draft" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reload inventory" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
    });
  });

  it("permanently locks a network-uncertain POST", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = input instanceof Request ? input.url : input.toString();
      if (init?.method === "POST") return Promise.reject(new TypeError("network unavailable"));
      if (url.includes("/options")) return Promise.resolve(json([option]));
      return Promise.resolve(json([]));
    });
    renderPanel();

    await screen.findByText(option.curation_policy_id);
    fireEvent.click(screen.getByLabelText(/result is an unapproved/i));
    fireEvent.click(screen.getByRole("button", { name: "Create knowledge draft" }));
    expect(await screen.findByText("Draft attempt requires inventory reconciliation")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reload inventory" }));
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
  });

  it("uses username-password re-login language for 401", async () => {
    const requestLogin = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(null, { status: 401 }));
    renderPanel(requestLogin);

    expect(await screen.findByText(/username and password/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(requestLogin).toHaveBeenCalledOnce();
  });

  it("shows a fail-closed scope message for 403", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(null, { status: 403 }));
    renderPanel();

    expect(await screen.findByText("Knowledge draft scope is required")).toBeVisible();
    expect(screen.getByText(/cannot read or curate operational evidence drafts/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /reload|create|sign in/i })).toBeNull();
  });
});
