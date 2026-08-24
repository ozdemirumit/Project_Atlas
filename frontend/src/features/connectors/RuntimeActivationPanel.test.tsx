import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorRuntimeActivation,
  getConnectorRuntimeActivationOptions,
  getConnectorRuntimeActivations,
} from "../../api/runtimeActivations";
import { RuntimeActivationPanel } from "./RuntimeActivationPanel";
import { secretBrokerageAuthorizationInventoryItem as brokerage } from "./testSecretBrokerageFixture";
import {
  runtimeActivationInventoryItem as activation,
  runtimeActivationOption as option,
} from "./testRuntimeActivationFixture";

vi.mock("../../api/runtimeActivations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/runtimeActivations")>();
  return {
    ...original,
    createConnectorRuntimeActivation: vi.fn(),
    getConnectorRuntimeActivationOptions: vi.fn(),
    getConnectorRuntimeActivations: vi.fn(),
  };
});

const sessionScopeKey = JSON.stringify(["subject.operator", "org.atlas", "env.atlas"]);

function renderPanel(existingActivation = undefined as typeof activation | undefined) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendered = render(
    <QueryClientProvider client={client}>
      <RuntimeActivationPanel
        brokerage={brokerage}
        existingActivation={existingActivation}
        sessionScopeKey={sessionScopeKey}
      />
    </QueryClientProvider>,
  );
  return { ...rendered, client };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getConnectorRuntimeActivations).mockResolvedValue([]);
  vi.mocked(getConnectorRuntimeActivationOptions).mockResolvedValue([option]);
  vi.mocked(createConnectorRuntimeActivation).mockResolvedValue({ data: activation });
});

afterEach(() => cleanup());

describe("RuntimeActivationPanel", () => {
  it("uses only server-provided evidence and exposes no later operational controls", async () => {
    renderPanel();

    expect(await screen.findByRole("combobox", { name: "Signed activation profile and policy" }))
      .toBeVisible();
    expect(screen.queryByRole("textbox", {
      name: /profile id|profile digest|policy id|policy digest|runner|image|workload|delivery|lease|health command|target|command/i,
    })).toBeNull();
    expect(screen.queryByRole("button", {
      name: /^(connect|run|invoke|execute|deploy|mutate)/i,
    })).toBeNull();
    fireEvent.click(screen.getByLabelText(/Activation starts only the exact isolated runtime/i));
    fireEvent.click(screen.getByRole("button", { name: "Activate runtime" }));

    await waitFor(() => expect(createConnectorRuntimeActivation).toHaveBeenCalledOnce());
    const input = vi.mocked(createConnectorRuntimeActivation).mock.calls[0]?.[0];
    expect(input?.brokerage).toBe(brokerage);
    expect(input?.option).toBe(option);
    expect(await screen.findByText(activation.activation_id)).toBeVisible();
    expect(screen.getAllByText("passed")).toHaveLength(2);
    expect(screen.getByText("not connected")).toBeVisible();
    expect(screen.queryByText(/target session authorization/i)).toBeNull();
  });

  it("restores minimized read-only activation evidence", async () => {
    vi.mocked(getConnectorRuntimeActivations).mockResolvedValue([activation]);
    renderPanel(activation);

    expect(await screen.findByText(activation.activation_id)).toBeVisible();
    expect(screen.getByText(activation.activation_profile_id)).toBeVisible();
    expect(screen.getByText(activation.health_probe_results[0]?.probe_id ?? "missing-probe"))
      .toBeVisible();
    expect(screen.queryByRole("button", { name: "Activate runtime" })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(getConnectorRuntimeActivationOptions).not.toHaveBeenCalled();
  });

  it("treats an authoritative empty response as newer than the existing activation prop", async () => {
    renderPanel(activation);

    expect(await screen.findByRole("combobox", { name: "Signed activation profile and policy" }))
      .toBeVisible();
    expect(screen.queryByText(activation.activation_id)).toBeNull();
    expect(getConnectorRuntimeActivationOptions).toHaveBeenCalledOnce();
  });

  it("hides stale activation evidence when a freshness refetch fails", async () => {
    vi.mocked(getConnectorRuntimeActivations).mockResolvedValue([activation]);
    const { client } = renderPanel(activation);
    expect(await screen.findByText(activation.activation_id)).toBeVisible();
    vi.mocked(getConnectorRuntimeActivations).mockRejectedValue(new Error("freshness rejected"));

    await act(async () => {
      await client.refetchQueries({
        queryKey: [
          "connector-runtime-activations",
          sessionScopeKey,
          brokerage.authorization_id,
        ],
      });
    });

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByText(activation.activation_id)).toBeNull();
  });

  it("suppresses a mutation success after the authoritative inventory becomes empty", async () => {
    const { client } = renderPanel();
    await screen.findByRole("combobox", { name: "Signed activation profile and policy" });
    fireEvent.click(screen.getByLabelText(/Activation starts only the exact isolated runtime/i));
    fireEvent.click(screen.getByRole("button", { name: "Activate runtime" }));
    expect(await screen.findByText(activation.activation_id)).toBeVisible();

    act(() => {
      client.setQueryData(
        ["connector-runtime-activations", sessionScopeKey, brokerage.authorization_id],
        [],
      );
    });

    expect(await screen.findByRole("combobox", { name: "Signed activation profile and policy" }))
      .toBeVisible();
    expect(screen.queryByText(activation.activation_id)).toBeNull();
  });

  it("suppresses a mutation success after authoritative freshness refetch fails", async () => {
    const { client } = renderPanel();
    await screen.findByRole("combobox", { name: "Signed activation profile and policy" });
    fireEvent.click(screen.getByLabelText(/Activation starts only the exact isolated runtime/i));
    fireEvent.click(screen.getByRole("button", { name: "Activate runtime" }));
    expect(await screen.findByText(activation.activation_id)).toBeVisible();
    vi.mocked(getConnectorRuntimeActivations).mockRejectedValue(new Error("freshness rejected"));

    await act(async () => {
      await client.refetchQueries({
        queryKey: [
          "connector-runtime-activations",
          sessionScopeKey,
          brokerage.authorization_id,
        ],
      });
    });

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByText(activation.activation_id)).toBeNull();
  });

  it("invalidates acknowledgement when refreshed server options change", async () => {
    const { client } = renderPanel();
    const select = await screen.findByRole("combobox", { name: "Signed activation profile and policy" });
    fireEvent.click(screen.getByLabelText(/Activation starts only the exact isolated runtime/i));
    expect(screen.getByRole("button", { name: "Activate runtime" })).toBeEnabled();

    const replacement = {
      ...option,
      activation_profile_id: "connector-runtime-activation-profile.replacement",
      activation_profile_digest: "a".repeat(64),
    };
    act(() => {
      client.setQueryData(
        ["connector-runtime-activation-options", sessionScopeKey, brokerage.authorization_id],
        [replacement],
      );
    });

    await waitFor(() => expect(select).toHaveValue(JSON.stringify([
      replacement.source_brokerage_authorization_id,
      replacement.source_brokerage_authorization_digest,
      replacement.activation_profile_id,
      replacement.activation_profile_digest,
      replacement.activation_policy_id,
      replacement.activation_policy_digest,
    ])));
    expect(screen.getByRole("button", { name: "Activate runtime" })).toBeDisabled();
  });

  it("uses the signed-in username/password session without MFA or a second session", async () => {
    vi.mocked(createConnectorRuntimeActivation).mockRejectedValue(new Error("policy rejected"));
    renderPanel();

    await screen.findByRole("combobox", { name: "Signed activation profile and policy" });
    fireEvent.click(screen.getByLabelText(/Activation starts only the exact isolated runtime/i));
    fireEvent.click(screen.getByRole("button", { name: "Activate runtime" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/brokerage lineage.*signed activation profile and policy.*freshness.*scope.*separation.*local health/i);
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|second browser|hardware/i);
  });
});
