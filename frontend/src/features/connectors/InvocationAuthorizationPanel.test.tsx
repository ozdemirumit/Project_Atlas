import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorInvocationAuthorization,
  getConnectorInvocationAuthorizationOptions,
  getConnectorInvocationAuthorizations,
  type ConnectorInvocationAuthorizationInventoryItem,
} from "../../api/invocationAuthorizations";
import { InvocationAuthorizationPanel } from "./InvocationAuthorizationPanel";
import {
  invocationAuthorizationInventoryItem as authorization,
  invocationAuthorizationOption as option,
} from "./testInvocationAuthorizationFixture";
import { targetSessionVerificationInventoryItem as targetSession } from "./testTargetSessionFixture";

vi.mock("../../api/invocationAuthorizations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/invocationAuthorizations")>();
  return {
    ...original,
    createConnectorInvocationAuthorization: vi.fn(),
    getConnectorInvocationAuthorizationOptions: vi.fn(),
    getConnectorInvocationAuthorizations: vi.fn(),
  };
});

function renderPanel(input?: {
  existingAuthorization?: typeof authorization;
  onAuthorizationCreated?: (value: ConnectorInvocationAuthorizationInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <InvocationAuthorizationPanel
        targetSession={targetSession}
        existingAuthorization={input?.existingAuthorization}
        onAuthorizationCreated={input?.onAuthorizationCreated}
        onRequestEnterpriseLogin={input?.onRequestEnterpriseLogin}
        sessionScopeKey="subject.test/organization.test/environment.test"
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InvocationAuthorizationPanel", () => {
  it("selects only a server-provided exact scope and does not expose bounded invocation", async () => {
    vi.mocked(getConnectorInvocationAuthorizations).mockResolvedValue([]);
    vi.mocked(getConnectorInvocationAuthorizationOptions).mockResolvedValue([option]);
    vi.mocked(createConnectorInvocationAuthorization).mockResolvedValue({ data: authorization });
    const onAuthorizationCreated = vi.fn();
    renderPanel({ onAuthorizationCreated });

    const selector = await screen.findByRole("combobox", {
      name: "Signed capability, profile, envelope and policy",
    });
    expect((selector as HTMLSelectElement).value).toContain(option.capability_id);
    expect(screen.getByText(option.required_permission)).toBeVisible();
    expect(screen.getByText("username and password")).toBeVisible();
    expect(
      screen.queryByRole("textbox", {
        name: /capability id|profile id|profile digest|envelope id|envelope digest|policy id|policy digest/i,
      }),
    ).toBeNull();
    const submit = screen.getByRole("button", { name: "Authorize invocation" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Authorization is short-lived, single-use/i));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(createConnectorInvocationAuthorization).toHaveBeenCalledWith({
      targetSession,
      option,
      purpose:
        "Authorize one bounded read-only capability invocation without invoking or scheduling it.",
    }));
    expect(onAuthorizationCreated).toHaveBeenCalledWith(authorization);
    expect(await screen.findByText(authorization.authorization_id)).toBeVisible();
    expect(screen.getByText("unconsumed")).toBeVisible();
    expect(screen.queryByRole("button", { name: /invoke once|schedule|execute|deploy/i }))
      .toBeNull();
    expect(screen.queryByText("Bounded invocation")).toBeNull();
  });

  it("clears stale authorization evidence when authoritative inventory reload fails", async () => {
    vi.mocked(getConnectorInvocationAuthorizations).mockRejectedValue(
      new ApiRequestError("inventory unavailable", 422),
    );
    renderPanel({ existingAuthorization: authorization });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invocation authorization evidence changed",
    );
    expect(screen.queryByText(authorization.authorization_id)).toBeNull();
    expect(screen.getByRole("button", { name: "Refresh evidence" })).toBeVisible();
  });

  it("uses normal re-login for a 401 and never presents MFA or browser-session prerequisites", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(getConnectorInvocationAuthorizations).mockRejectedValue(
      new ApiRequestError("expired", 401),
    );
    renderPanel({ onRequestEnterpriseLogin });

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Your signed-in session has expired")).toBeVisible();
    expect(within(alert).getByText(/Sign in again with your username and password/i)).toBeVisible();
    expect(within(alert).queryByText(
      /MFA|multi-factor|hardware-backed|authorized browser session/i,
    ))
      .toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledOnce();
  });
});
