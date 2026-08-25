import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorInvocationEvidence,
  getConnectorInvocationEvidence,
  getConnectorInvocationEvidenceOptions,
} from "../../api/invocationEvidence";
import { InvocationEvidencePanel } from "./InvocationEvidencePanel";
import { boundedInvocationInventoryItem as invocation } from
  "./testBoundedInvocationFixture";
import {
  invocationEvidenceInventoryItem as evidence,
  invocationEvidenceOption as option,
} from "./testInvocationEvidenceFixture";

vi.mock("../../api/invocationEvidence", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/invocationEvidence")>();
  return {
    ...original,
    createConnectorInvocationEvidence: vi.fn(),
    getConnectorInvocationEvidence: vi.fn(),
    getConnectorInvocationEvidenceOptions: vi.fn(),
  };
});

function renderPanel(onRequestEnterpriseLogin?: () => void) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <InvocationEvidencePanel
        invocation={invocation}
        onRequestEnterpriseLogin={onRequestEnterpriseLogin}
        sessionScopeKey="subject.test/org.test/env.test"
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(getConnectorInvocationEvidence).mockResolvedValue([]);
  vi.mocked(getConnectorInvocationEvidenceOptions).mockResolvedValue([option]);
  vi.mocked(createConnectorInvocationEvidence).mockResolvedValue({ data: evidence });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InvocationEvidencePanel", () => {
  it("uses one signed server option and renders only immutable evidence metadata", async () => {
    renderPanel();

    expect(await screen.findByRole("combobox", {
      name: "Signed evidence-preservation option",
    })).toBeVisible();
    expect(screen.getByText("username and password")).toBeVisible();
    expect(screen.queryByRole("textbox", {
      name: /policy id|policy digest|classification|retention|access|acl|encryption|storage/i,
    })).toBeNull();
    fireEvent.click(screen.getByLabelText(/invocation is claimed before preservation/i));
    fireEvent.click(screen.getByRole("button", { name: "Preserve evidence" }));

    await waitFor(() => expect(createConnectorInvocationEvidence).toHaveBeenCalledOnce());
    expect(vi.mocked(createConnectorInvocationEvidence).mock.calls[0]?.[0]).toMatchObject({
      invocation,
      option,
    });
    expect(await screen.findByText(evidence.evidence_package_id)).toBeVisible();
    expect(screen.getByText("internal")).toBeVisible();
    expect(screen.getByText("at rest")).toBeVisible();
    expect(screen.queryByRole("button", {
      name: /preserve|retry|knowledge|publish|index|embed|schedule|execute|deploy|mutate/i,
    })).toBeNull();
  });

  it.each([
    ["HTTP 503", new ApiRequestError("Outcome uncertain", 503)],
    ["HTTP 409", new ApiRequestError("Claim conflict", 409)],
    ["HTTP 422", new ApiRequestError("Lineage changed", 422)],
    ["network failure", new Error("Connection closed")],
  ])("never offers retry after an irreversible claim attempt with %s", async (_case, error) => {
    vi.mocked(createConnectorInvocationEvidence).mockRejectedValue(error);
    renderPanel();

    await screen.findByRole("combobox", { name: "Signed evidence-preservation option" });
    fireEvent.click(screen.getByLabelText(/invocation is claimed before preservation/i));
    fireEvent.click(screen.getByRole("button", { name: "Preserve evidence" }));

    expect(await screen.findByText("Evidence-preservation outcome is uncertain")).toBeVisible();
    expect(screen.queryByRole("button", { name: /retry|preserve evidence/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reload authoritative inventory" }));
    await waitFor(() => expect(getConnectorInvocationEvidence).toHaveBeenCalledTimes(2));
    expect(createConnectorInvocationEvidence).toHaveBeenCalledOnce();
    expect(getConnectorInvocationEvidenceOptions).toHaveBeenCalledOnce();
  });

  it("uses normal username and password re-login without a global MFA prompt", async () => {
    const requestLogin = vi.fn();
    vi.mocked(getConnectorInvocationEvidence).mockRejectedValue(
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
