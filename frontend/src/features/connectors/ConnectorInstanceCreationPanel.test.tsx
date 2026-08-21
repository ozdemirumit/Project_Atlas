import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorInstanceCreationPanel } from "./ConnectorInstanceCreationPanel";
import { connectorInstanceRecord as record } from "./testInstanceFixture";
import { installationReceipt as receipt } from "./testInstallationFixture";

afterEach(() => vi.unstubAllGlobals());

describe("ConnectorInstanceCreationPanel", () => {
  it("creates only a disabled identity without target, secret, capability, or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((_input, init) =>
      Promise.resolve(
        init?.method === "POST"
          ? new Response(JSON.stringify({ data: record }), { status: 201 })
          : new Response(JSON.stringify({ data: [] }), { status: 200 }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ConnectorInstanceCreationPanel installation={receipt} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name:
        /target address|endpoint|secret reference|credential|capability|network route|proxy|schedule|runtime command/i,
      }),
    ).toBeNull();
    fireEvent.change(screen.getByLabelText("Instance key"), {
      target: { value: record.instance_key },
    });
    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: record.display_name },
    });
    fireEvent.click(
      screen.getByLabelText(
        "The instance remains disabled and unconfigured, with no target, secret, capability, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create disabled instance" }));

    expect(await screen.findByText(record.instance_id)).toBeVisible();
    expect(screen.getByText(record.instance_state)).toBeVisible();
    expect(screen.queryByRole("button", { name: /configure|enable|execute|deploy/i })).toBeNull();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => call[1]?.method === "POST")).toBe(true),
    );
    const init = fetchMock.mock.calls.find((call) => call[1]?.method === "POST")?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_installation_receipt_id: receipt.receipt_id,
      source_installation_receipt_digest: receipt.canonical_digest,
      package_digest: receipt.package_digest,
      instance_key: record.instance_key,
      instance_policy_id: record.instance_policy_id,
      instance_policy_digest: record.instance_policy_digest,
      acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: true,
    });
    for (const forbidden of [
      "instance_id",
      "state",
      "target",
      "endpoint",
      "secret_reference",
      "credential",
      "capability",
      "proxy",
      "network_route",
      "schedule",
      "runtime",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
