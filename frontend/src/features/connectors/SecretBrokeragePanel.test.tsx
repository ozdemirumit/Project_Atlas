import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorSecretBrokerageAuthorization,
  getConnectorSecretBrokerageAuthorizationOptions,
  getConnectorSecretBrokerageAuthorizations,
} from "../../api/secretBrokerageAuthorizations";
import { SecretBrokeragePanel } from "./SecretBrokeragePanel";
import { runtimeTrustGrantInventoryItem as runtimeTrust } from "./testRuntimeTrustFixture";
import {
  secretBrokerageAuthorizationInventoryItem as authorization,
  secretBrokerageAuthorizationOption as option,
} from "./testSecretBrokerageFixture";

vi.mock("../../api/secretBrokerageAuthorizations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/secretBrokerageAuthorizations")>();
  return {
    ...original,
    createConnectorSecretBrokerageAuthorization: vi.fn(),
    getConnectorSecretBrokerageAuthorizationOptions: vi.fn(),
    getConnectorSecretBrokerageAuthorizations: vi.fn(),
  };
});

const sessionScopeKey = JSON.stringify(["subject.operator", "org.atlas", "env.atlas"]);

function renderPanel(existingAuthorization = undefined as typeof authorization | undefined) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendered = render(
    <QueryClientProvider client={client}>
      <SecretBrokeragePanel
        runtimeTrust={runtimeTrust}
        existingAuthorization={existingAuthorization}
        sessionScopeKey={sessionScopeKey}
      />
    </QueryClientProvider>,
  );
  return { ...rendered, client };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getConnectorSecretBrokerageAuthorizations).mockResolvedValue([]);
  vi.mocked(getConnectorSecretBrokerageAuthorizationOptions).mockResolvedValue([option]);
  vi.mocked(createConnectorSecretBrokerageAuthorization).mockResolvedValue({ data: authorization });
});

afterEach(() => cleanup());

describe("SecretBrokeragePanel", () => {
  it("uses only server-provided exact brokerage evidence and grants no operational authority", async () => {
    renderPanel();

    expect(await screen.findByRole("combobox", { name: "Signed brokerage profile and policy" }))
      .toBeVisible();
    expect(screen.queryByRole("textbox", {
      name: /profile id|profile digest|policy id|policy digest|broker|store|secret|delivery|lease|workload/i,
    })).toBeNull();
    expect(screen.queryByRole("button", {
      name: /^(resolve|lease|connect|run|invoke|execute|deploy)/i,
    })).toBeNull();
    fireEvent.click(screen.getByLabelText(/Authorization governs only a future memory-only/i));
    fireEvent.click(screen.getByRole("button", { name: "Authorize secret brokerage" }));

    await waitFor(() => expect(createConnectorSecretBrokerageAuthorization).toHaveBeenCalledOnce());
    const input = vi.mocked(createConnectorSecretBrokerageAuthorization).mock.calls[0]?.[0];
    expect(input?.runtimeTrust).toBe(runtimeTrust);
    expect(input?.option).toBe(option);
    expect(input?.purpose).toMatch(/memory-only secret brokerage boundary/i);
    expect(await screen.findByText(authorization.authorization_id)).toBeVisible();
    expect(screen.getByText("not issued")).toBeVisible();
    expect(screen.getByText("not resolved")).toBeVisible();
  });

  it("restores an existing authorization as minimized read-only evidence", async () => {
    vi.mocked(getConnectorSecretBrokerageAuthorizations).mockResolvedValue([authorization]);
    renderPanel(authorization);

    expect(await screen.findByText(authorization.authorization_id)).toBeVisible();
    expect(screen.getByText(authorization.brokerage_profile_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Authorize secret brokerage" })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(getConnectorSecretBrokerageAuthorizationOptions).not.toHaveBeenCalled();
  });

  it("treats an authoritative empty response as newer than an existing authorization prop", async () => {
    renderPanel(authorization);

    expect(await screen.findByRole("combobox", { name: "Signed brokerage profile and policy" }))
      .toBeVisible();
    expect(screen.queryByText(authorization.authorization_id)).toBeNull();
    expect(getConnectorSecretBrokerageAuthorizationOptions).toHaveBeenCalledOnce();
  });

  it("hides previously valid authorization evidence when freshness refetch fails", async () => {
    vi.mocked(getConnectorSecretBrokerageAuthorizations).mockResolvedValue([authorization]);
    const { client } = renderPanel(authorization);
    expect(await screen.findByText(authorization.authorization_id)).toBeVisible();
    vi.mocked(getConnectorSecretBrokerageAuthorizations).mockRejectedValue(
      new Error("freshness rejected"),
    );

    await act(async () => {
      await client.refetchQueries({
        queryKey: [
          "connector-secret-brokerage-authorizations",
          sessionScopeKey,
          runtimeTrust.grant_id,
        ],
      });
    });

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByText(authorization.authorization_id)).toBeNull();
  });

  it("invalidates acknowledgement when refreshed server options change", async () => {
    const { client } = renderPanel();
    const select = await screen.findByRole("combobox", {
      name: "Signed brokerage profile and policy",
    });
    fireEvent.click(screen.getByLabelText(/Authorization governs only a future memory-only/i));
    expect(screen.getByRole("button", { name: "Authorize secret brokerage" })).toBeEnabled();

    const replacement = {
      ...option,
      brokerage_profile_id: "connector-secret-brokerage-profile.memory-only-replacement",
      brokerage_profile_digest: "6".repeat(64),
    };
    act(() => {
      client.setQueryData(
        ["connector-secret-brokerage-authorization-options", sessionScopeKey, runtimeTrust.grant_id],
        [replacement],
      );
    });

    await waitFor(() => expect(select).toHaveValue(JSON.stringify([
      replacement.source_runtime_trust_grant_id,
      replacement.source_runtime_trust_digest,
      replacement.brokerage_profile_id,
      replacement.brokerage_profile_digest,
      replacement.brokerage_policy_id,
      replacement.brokerage_policy_digest,
    ])));
    expect(screen.getByRole("button", { name: "Authorize secret brokerage" })).toBeDisabled();
  });

  it("reports policy failure without requiring MFA or a second browser session", async () => {
    vi.mocked(createConnectorSecretBrokerageAuthorization).mockRejectedValue(
      new Error("policy rejected"),
    );
    renderPanel();

    await screen.findByRole("combobox", { name: "Signed brokerage profile and policy" });
    fireEvent.click(screen.getByLabelText(/Authorization governs only a future memory-only/i));
    fireEvent.click(screen.getByRole("button", { name: "Authorize secret brokerage" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/runtime lineage.*credential posture.*signed profile and policy.*freshness.*scope.*separation/i);
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|second browser|hardware/i);
  });
});
