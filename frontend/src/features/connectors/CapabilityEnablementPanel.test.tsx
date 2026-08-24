import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorCapabilityEnablementOption } from "../../api/capabilityEnablements";
import { CapabilityEnablementPanel } from "./CapabilityEnablementPanel";
import {
  capabilityEnablement,
  capabilityEnablementInventoryItem,
  capabilityEnablementOption,
} from "./testCapabilityEnablementFixture";
import { configurationValidation as validation } from "./testConfigurationValidationFixture";

const sessionScopeKey = "subject.operator:organization.test:environment.development";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

function renderPanel(client: QueryClient, existing = false) {
  return render(
    <QueryClientProvider client={client}>
      <CapabilityEnablementPanel
        validation={validation}
        existingEnablement={existing ? capabilityEnablementInventoryItem : undefined}
        sessionScopeKey={sessionScopeKey}
      />
    </QueryClientProvider>,
  );
}

describe("CapabilityEnablementPanel", () => {
  it("uses only a server-provided option and caches a minimized read-only result", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = requestUrl(input);
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ data: capabilityEnablementInventoryItem }), { status: 201 }));
      }
      if (url.includes("/options?")) {
        return Promise.resolve(new Response(JSON.stringify({ data: [capabilityEnablementOption] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ data: [] }), { status: 200 }));
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    renderPanel(client);

    expect(await screen.findByRole("combobox", {
      name: "Governed capability profile and policy",
    })).toBeVisible();
    expect(
      screen.queryByRole("textbox", {
        name: /profile id|profile digest|policy id|policy digest|endpoint|target ip|host|port|username|password|token|secret|command|parameter|runtime/i,
      }),
    ).toBeNull();
    expect(screen.getByText("health.read")).toBeVisible();
    expect(screen.getByText("connector.health.read")).toBeVisible();

    fireEvent.click(screen.getByLabelText(/Enablement selects only the exact signed C0\/C1/i));
    fireEvent.click(screen.getByRole("button", { name: "Enable governed capabilities" }));

    expect(await screen.findByText(capabilityEnablement.enablement_id)).toBeVisible();
    expect(screen.getByText("not granted")).toBeVisible();
    expect(screen.getByText("not authorized")).toBeVisible();
    expect(screen.getByText("not approved")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Runtime trust" })).toBeNull();

    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(typeof post?.[1]?.body === "string" ? post[1].body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      capability_profile_id: capabilityEnablementOption.capability_profile_id,
      capability_profile_digest: capabilityEnablementOption.capability_profile_digest,
      enablement_policy_id: capabilityEnablementOption.enablement_policy_id,
      enablement_policy_digest: capabilityEnablementOption.enablement_policy_digest,
    });

    const cached = client.getQueryData([
      "connector-capability-enablements",
      sessionScopeKey,
      validation.validation_id,
    ]);
    expect(cached).toEqual([capabilityEnablementInventoryItem]);
    expect(JSON.stringify(cached)).not.toContain(capabilityEnablement.capability_profile_digest);
  });

  it("renders restored enablement as read-only without options or runtime controls", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [capabilityEnablementInventoryItem] }), { status: 200 }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderPanel(client, true);

    expect(await screen.findByText(capabilityEnablement.enablement_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Enable governed capabilities" })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("button", { name: /connect|run|execute|deploy|runtime/i })).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(requestUrl(fetchMock.mock.calls[0]?.[0] ?? "")).not.toContain("/options");
  });

  it("does not submit a removed selection after option refetch", async () => {
    const secondOption: ConnectorCapabilityEnablementOption = {
      ...capabilityEnablementOption,
      capability_profile_id: "connector-capability-profile.alternate-read-only",
      capability_profile_digest: "a".repeat(64),
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = requestUrl(input);
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ data: capabilityEnablementInventoryItem }), { status: 201 }));
      }
      if (url.includes("/options?")) {
        return Promise.resolve(new Response(
          JSON.stringify({ data: [capabilityEnablementOption, secondOption] }),
          { status: 200 },
        ));
      }
      return Promise.resolve(new Response(JSON.stringify({ data: [] }), { status: 200 }));
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    renderPanel(client);

    const select = await screen.findByRole("combobox", {
      name: "Governed capability profile and policy",
    });
    fireEvent.change(select, {
      target: {
        value: JSON.stringify([
          secondOption.source_validation_id,
          secondOption.source_validation_digest,
          secondOption.capability_profile_id,
          secondOption.capability_profile_digest,
          secondOption.enablement_policy_id,
          secondOption.enablement_policy_digest,
        ]),
      },
    });
    expect(select).toHaveDisplayValue(/alternate-read-only/);

    client.setQueryData(
      ["connector-capability-enablement-options", sessionScopeKey, validation.validation_id],
      [capabilityEnablementOption],
    );
    await waitFor(() =>
      expect(screen.getByRole("combobox", {
        name: "Governed capability profile and policy",
      })).toHaveDisplayValue(/development-read-only/));

    fireEvent.click(screen.getByLabelText(/Enablement selects only the exact signed C0\/C1/i));
    fireEvent.click(screen.getByRole("button", { name: "Enable governed capabilities" }));
    await screen.findByText(capabilityEnablement.enablement_id);

    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(typeof post?.[1]?.body === "string" ? post[1].body : "{}") as Record<string, unknown>;
    expect(body.capability_profile_id).toBe(capabilityEnablementOption.capability_profile_id);
    expect(body.capability_profile_digest).toBe(capabilityEnablementOption.capability_profile_digest);
  });

  it("disables option selection and submit while signed options are refetching", async () => {
    let optionRequests = 0;
    let resolveRefetch: ((response: Response) => void) | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = requestUrl(input);
      if (url.includes("/options?")) {
        optionRequests += 1;
        if (optionRequests > 1) {
          return new Promise<Response>((resolve) => {
            resolveRefetch = resolve;
          });
        }
        return Promise.resolve(
          new Response(JSON.stringify({ data: [capabilityEnablementOption] }), { status: 200 }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ data: [] }), { status: 200 }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderPanel(client);

    const select = await screen.findByRole("combobox", {
      name: "Governed capability profile and policy",
    });
    fireEvent.click(screen.getByLabelText(/Enablement selects only the exact signed C0\/C1/i));
    const submit = screen.getByRole("button", { name: "Enable governed capabilities" });
    expect(submit).toBeEnabled();

    const refetch = client.refetchQueries({
      queryKey: [
        "connector-capability-enablement-options",
        sessionScopeKey,
        validation.validation_id,
      ],
    });
    await waitFor(() => expect(submit).toBeDisabled());
    expect(select).toBeDisabled();
    resolveRefetch?.(
      new Response(JSON.stringify({ data: [capabilityEnablementOption] }), { status: 200 }),
    );
    await refetch;
  });
});
