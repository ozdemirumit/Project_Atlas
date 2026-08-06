import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PackageInstallationPanel } from "./PackageInstallationPanel";
import { registration } from "./testRegistrationFixture";
import { installationReceipt as receipt } from "./testInstallationFixture";

afterEach(() => vi.unstubAllGlobals());

describe("PackageInstallationPanel", () => {
  it("installs only the exact registration without runtime or destination input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: receipt }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PackageInstallationPanel registration={registration} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByLabelText(
        /package bytes|manifest content|registry address|store path|dependency source|target address|secret reference/i,
      ),
    ).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Installation grants no instance, target, secret, enablement, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Install registered package" }));

    expect(await screen.findByText(receipt.receipt_id)).toBeVisible();
    expect(screen.getByText(receipt.installation.installation_store_profile_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: /configure|enable|execute|deploy/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_registration_record_id: registration.record_id,
      source_registration_record_digest: registration.canonical_digest,
      package_digest: registration.package_digest,
      installation_policy_id: receipt.installation_policy_id,
      installation_policy_digest: receipt.installation_policy_digest,
      acknowledged_installation_grants_no_instance_or_runtime_authority: true,
    });
    for (const forbidden of [
      "package_bytes",
      "manifest",
      "registry_url",
      "artifact_reference",
      "installation_path",
      "dependency_source",
      "instance",
      "target",
      "secret_reference",
      "enable",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
