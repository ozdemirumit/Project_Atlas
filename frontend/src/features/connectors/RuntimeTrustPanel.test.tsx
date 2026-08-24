import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorRuntimeTrustGrant,
  getConnectorRuntimeTrustGrantOptions,
  getConnectorRuntimeTrustGrants,
} from "../../api/runtimeTrustGrants";
import { RuntimeTrustPanel } from "./RuntimeTrustPanel";
import { capabilityEnablementInventoryItem as enablement } from "./testCapabilityEnablementFixture";
import {
  runtimeTrustGrantInventoryItem as grant,
  runtimeTrustGrantOption as option,
} from "./testRuntimeTrustFixture";

vi.mock("../../api/runtimeTrustGrants", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/runtimeTrustGrants")>();
  return {
    ...original,
    createConnectorRuntimeTrustGrant: vi.fn(),
    getConnectorRuntimeTrustGrantOptions: vi.fn(),
    getConnectorRuntimeTrustGrants: vi.fn(),
  };
});

function renderPanel(existingGrant = undefined as typeof grant | undefined) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <RuntimeTrustPanel
        enablement={enablement}
        existingGrant={existingGrant}
        sessionScopeKey={JSON.stringify(["subject.operator", "org.atlas", "env.atlas"])}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getConnectorRuntimeTrustGrants).mockResolvedValue([]);
  vi.mocked(getConnectorRuntimeTrustGrantOptions).mockResolvedValue([option]);
  vi.mocked(createConnectorRuntimeTrustGrant).mockResolvedValue({ data: grant });
});

afterEach(() => cleanup());

describe("RuntimeTrustPanel", () => {
  it("uses only a server-provided exact runtime option and grants no operational authority", async () => {
    renderPanel();

    expect(await screen.findByRole("combobox", { name: "Signed runtime profile and trust policy" }))
      .toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: /profile id|profile digest|policy id|policy digest/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /^(connect|run|invoke|execute|deploy|resolve secret)/i }))
      .toBeNull();
    fireEvent.click(screen.getByLabelText(/Trust binds only this signed isolated boundary/i));
    fireEvent.click(screen.getByRole("button", { name: "Establish runtime trust" }));

    await waitFor(() => expect(createConnectorRuntimeTrustGrant).toHaveBeenCalledOnce());
    const input = vi.mocked(createConnectorRuntimeTrustGrant).mock.calls[0]?.[0];
    expect(input?.enablement).toBe(enablement);
    expect(input?.option).toBe(option);
    expect(input?.purpose).toMatch(/signed isolated runtime boundary/i);
    expect(await screen.findByText(grant.grant_id)).toBeVisible();
    expect(screen.getByText("not started")).toBeVisible();
    expect(screen.getByText("not resolved")).toBeVisible();
    expect(screen.getByText("not connected")).toBeVisible();
    expect(screen.queryByRole("heading", { name: /secret brokerage/i })).toBeNull();
  });

  it("restores an existing grant as a read-only boundary", async () => {
    vi.mocked(getConnectorRuntimeTrustGrants).mockResolvedValue([grant]);
    renderPanel(grant);

    expect(await screen.findByText(grant.grant_id)).toBeVisible();
    expect(screen.getByText(grant.runtime_profile_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Establish runtime trust" })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(getConnectorRuntimeTrustGrantOptions).not.toHaveBeenCalled();
  });

  it("blocks submission while current runtime evidence is being refreshed", async () => {
    let resolveInventory: ((value: []) => void) | undefined;
    vi.mocked(getConnectorRuntimeTrustGrants).mockImplementation(
      () => new Promise((resolve) => { resolveInventory = resolve; }),
    );
    renderPanel();

    expect(screen.queryByRole("button", { name: "Establish runtime trust" })).toBeNull();
    resolveInventory?.([]);
    expect(await screen.findByRole("button", { name: "Establish runtime trust" })).toBeDisabled();
  });

  it("reports policy failures without requiring MFA or a second browser session", async () => {
    vi.mocked(createConnectorRuntimeTrustGrant).mockRejectedValue(new Error("policy rejected"));
    renderPanel();

    await screen.findByRole("combobox", { name: "Signed runtime profile and trust policy" });
    fireEvent.click(screen.getByLabelText(/Trust binds only this signed isolated boundary/i));
    fireEvent.click(screen.getByRole("button", { name: "Establish runtime trust" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/runtime profile.*trust policy.*freshness.*scope.*separation/i);
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|second browser|hardware/i);
  });
});
