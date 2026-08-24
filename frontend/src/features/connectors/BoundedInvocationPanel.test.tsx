import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorBoundedInvocation,
  getConnectorBoundedInvocationOptions,
  getConnectorBoundedInvocations,
} from "../../api/boundedInvocations";
import { ApiRequestError } from "../../api/client";
import { BoundedInvocationPanel } from "./BoundedInvocationPanel";
import {
  boundedInvocationInventoryItem as invocation,
  boundedInvocationOption as option,
} from "./testBoundedInvocationFixture";
import { invocationAuthorizationInventoryItem as authorization } from
  "./testInvocationAuthorizationFixture";

vi.mock("../../api/boundedInvocations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/boundedInvocations")>();
  return {
    ...original,
    createConnectorBoundedInvocation: vi.fn(),
    getConnectorBoundedInvocationOptions: vi.fn(),
    getConnectorBoundedInvocations: vi.fn(),
  };
});

function renderPanel(onRequestEnterpriseLogin?: () => void) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <BoundedInvocationPanel
        authorization={authorization}
        onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        sessionScopeKey="subject.test/org.test/env.test"
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getConnectorBoundedInvocations).mockResolvedValue([]);
  vi.mocked(getConnectorBoundedInvocationOptions).mockResolvedValue([option]);
  vi.mocked(createConnectorBoundedInvocation).mockResolvedValue({ data: invocation });
});

afterEach(() => vi.clearAllMocks());

describe("BoundedInvocationPanel", () => {
  it("uses one server option and renders only minimized immutable completion", async () => {
    renderPanel();

    expect(await screen.findByRole("combobox", {
      name: "Signed bounded invocation option",
    })).toBeVisible();
    expect(screen.getByText("username and password")).toBeVisible();
    expect(screen.queryByRole("textbox", {
      name: /policy id|policy digest|profile|target|command|handler|input|timeout|output/i,
    })).toBeNull();
    fireEvent.click(screen.getByLabelText(/authorization is consumed before the call/i));
    fireEvent.click(screen.getByRole("button", { name: "Invoke once" }));

    await waitFor(() => expect(createConnectorBoundedInvocation).toHaveBeenCalledOnce());
    expect(vi.mocked(createConnectorBoundedInvocation).mock.calls[0]?.[0]).toMatchObject({
      authorization,
      option,
    });
    expect(await screen.findByText(invocation.invocation_id)).toBeVisible();
    expect(screen.getByText("validated and redacted")).toBeVisible();
    expect(screen.getByText("disconnected")).toBeVisible();
    expect(screen.getByText("not ingested")).toBeVisible();
    expect(screen.queryByRole("button", {
      name: /ingest|schedule|execute|deploy|mutate|invoke once/i,
    })).toBeNull();
  });

  it("never offers retry after an uncertain consumed outcome", async () => {
    vi.mocked(createConnectorBoundedInvocation).mockRejectedValue(
      new ApiRequestError("Outcome uncertain", 503),
    );
    renderPanel();

    await screen.findByRole("combobox", { name: "Signed bounded invocation option" });
    fireEvent.click(screen.getByLabelText(/authorization is consumed before the call/i));
    fireEvent.click(screen.getByRole("button", { name: "Invoke once" }));

    expect(await screen.findByText("Invocation outcome is uncertain")).toBeVisible();
    expect(screen.queryByRole("button", { name: /retry|invoke once/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reload authoritative inventory" }));
    await waitFor(() => expect(getConnectorBoundedInvocations).toHaveBeenCalledTimes(2));
    expect(createConnectorBoundedInvocation).toHaveBeenCalledOnce();
    expect(getConnectorBoundedInvocationOptions).toHaveBeenCalledOnce();
  });

  it("uses normal username and password re-login without a global MFA prompt", async () => {
    const requestLogin = vi.fn();
    vi.mocked(getConnectorBoundedInvocations).mockRejectedValue(
      new ApiRequestError("Session expired", 401),
    );
    renderPanel(requestLogin);

    expect(await screen.findByText("Your signed-in session has expired")).toBeVisible();
    expect(screen.getByText(/username and password/i)).toBeVisible();
    expect(screen.queryByText(/MFA|authorized browser session/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(requestLogin).toHaveBeenCalledOnce();
  });
});
