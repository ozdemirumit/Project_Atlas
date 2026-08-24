import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorTargetSessionVerification,
  getConnectorTargetSessionVerificationOptions,
  getConnectorTargetSessionVerifications,
} from "../../api/targetSessionVerifications";
import { TargetSessionPanel } from "./TargetSessionPanel";
import { runtimeActivationInventoryItem as activation } from "./testRuntimeActivationFixture";
import {
  targetSessionVerificationInventoryItem as verification,
  targetSessionVerificationOption as option,
} from "./testTargetSessionFixture";

vi.mock("../../api/targetSessionVerifications", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/targetSessionVerifications")>();
  return {
    ...original,
    createConnectorTargetSessionVerification: vi.fn(),
    getConnectorTargetSessionVerificationOptions: vi.fn(),
    getConnectorTargetSessionVerifications: vi.fn(),
  };
});

const sessionScopeKey = JSON.stringify(["subject.operator", "org.atlas", "env.atlas"]);

function renderPanel(existingVerification = undefined as typeof verification | undefined) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendered = render(
    <QueryClientProvider client={client}>
      <TargetSessionPanel
        activation={activation}
        existingVerification={existingVerification}
        sessionScopeKey={sessionScopeKey}
      />
    </QueryClientProvider>,
  );
  return { ...rendered, client };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getConnectorTargetSessionVerifications).mockResolvedValue([]);
  vi.mocked(getConnectorTargetSessionVerificationOptions).mockResolvedValue([option]);
  vi.mocked(createConnectorTargetSessionVerification).mockResolvedValue({ data: verification });
});

afterEach(() => cleanup());

describe("TargetSessionPanel", () => {
  it("uses only server-provided signed evidence and exposes no reusable or operational controls", async () => {
    renderPanel();

    expect(await screen.findByRole("combobox", {
      name: "Signed target session profile and policy",
    })).toBeVisible();
    expect(screen.queryByRole("textbox", {
      name: /profile id|profile digest|policy id|policy digest|target id|address|endpoint|host|port|credential|secret|lease|session handle|certificate|command|parameter/i,
    })).toBeNull();
    expect(screen.queryByRole("button", {
      name: /^(connect|run|invoke|execute|deploy|mutate)/i,
    })).toBeNull();
    fireEvent.click(screen.getByLabelText(/Verification permits one bounded read-only connection/i));
    fireEvent.click(screen.getByRole("button", { name: "Verify target session" }));

    await waitFor(() => expect(createConnectorTargetSessionVerification).toHaveBeenCalledOnce());
    const input = vi.mocked(createConnectorTargetSessionVerification).mock.calls[0]?.[0];
    expect(input?.activation).toBe(activation);
    expect(input?.option).toBe(option);
    expect(await screen.findByText(verification.verification_id)).toBeVisible();
    expect(screen.getAllByText("passed")).toHaveLength(4);
    expect(screen.getByText("read-only")).toBeVisible();
    expect(screen.getByText("closed")).toBeVisible();
  });

  it("restores minimized read-only target session evidence", async () => {
    vi.mocked(getConnectorTargetSessionVerifications).mockResolvedValue([verification]);
    renderPanel(verification);

    expect(await screen.findByText(verification.verification_id)).toBeVisible();
    expect(screen.getByText(verification.session_profile_digest.slice(0, 16))).toBeVisible();
    expect(screen.getByText(verification.connectivity_check_results[0]?.check_id ?? "missing-check"))
      .toBeVisible();
    expect(screen.queryByRole("button", { name: "Verify target session" })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(getConnectorTargetSessionVerificationOptions).not.toHaveBeenCalled();
  });

  it("treats an authoritative empty response as newer than the existing verification prop", async () => {
    renderPanel(verification);

    expect(await screen.findByRole("combobox", {
      name: "Signed target session profile and policy",
    })).toBeVisible();
    expect(screen.queryByText(verification.verification_id)).toBeNull();
    expect(getConnectorTargetSessionVerificationOptions).toHaveBeenCalledOnce();
  });

  it("hides stale target session evidence when a freshness refetch fails", async () => {
    vi.mocked(getConnectorTargetSessionVerifications).mockResolvedValue([verification]);
    const { client } = renderPanel(verification);
    expect(await screen.findByText(verification.verification_id)).toBeVisible();
    vi.mocked(getConnectorTargetSessionVerifications).mockRejectedValue(
      new Error("freshness rejected"),
    );

    await act(async () => {
      await client.refetchQueries({
        queryKey: [
          "connector-target-session-verifications",
          sessionScopeKey,
          activation.activation_id,
        ],
      });
    });

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByText(verification.verification_id)).toBeNull();
  });

  it("suppresses successful mutation evidence after authoritative inventory becomes empty", async () => {
    const { client } = renderPanel();
    await screen.findByRole("combobox", { name: "Signed target session profile and policy" });
    fireEvent.click(screen.getByLabelText(/Verification permits one bounded read-only connection/i));
    fireEvent.click(screen.getByRole("button", { name: "Verify target session" }));
    expect(await screen.findByText(verification.verification_id)).toBeVisible();

    act(() => {
      client.setQueryData(
        ["connector-target-session-verifications", sessionScopeKey, activation.activation_id],
        [],
      );
    });

    expect(await screen.findByRole("combobox", {
      name: "Signed target session profile and policy",
    })).toBeVisible();
    expect(screen.queryByText(verification.verification_id)).toBeNull();
  });

  it("invalidates acknowledgement when refreshed server options change", async () => {
    const { client } = renderPanel();
    const select = await screen.findByRole("combobox", {
      name: "Signed target session profile and policy",
    });
    fireEvent.click(screen.getByLabelText(/Verification permits one bounded read-only connection/i));
    expect(screen.getByRole("button", { name: "Verify target session" })).toBeEnabled();

    const replacement = {
      ...option,
      session_profile_id: "connector-target-session-profile.replacement",
      session_profile_digest: "a".repeat(64),
    };
    act(() => {
      client.setQueryData(
        ["connector-target-session-verification-options", sessionScopeKey, activation.activation_id],
        [replacement],
      );
    });

    await waitFor(() => expect(select).toHaveValue(JSON.stringify([
      replacement.source_runtime_activation_id,
      replacement.source_runtime_activation_digest,
      replacement.session_profile_id,
      replacement.session_profile_digest,
      replacement.session_policy_id,
      replacement.session_policy_digest,
    ])));
    expect(screen.getByRole("button", { name: "Verify target session" })).toBeDisabled();
  });

  it("uses the normal username/password session without global MFA or a second browser", async () => {
    vi.mocked(createConnectorTargetSessionVerification).mockRejectedValue(
      new Error("policy rejected"),
    );
    renderPanel();

    await screen.findByRole("combobox", { name: "Signed target session profile and policy" });
    fireEvent.click(screen.getByLabelText(/Verification permits one bounded read-only connection/i));
    fireEvent.click(screen.getByRole("button", { name: "Verify target session" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      /runtime lineage.*signed session profile and policy.*freshness.*network controls.*TLS.*target identity.*read-only privilege.*scope.*separation/i,
    );
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|second browser|hardware/i);
  });
});
