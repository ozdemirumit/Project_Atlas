import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CapabilityEnablementPanel } from "./CapabilityEnablementPanel";
import {
  capabilityEnablement as enablement,
  capabilityPolicyDigest as policyDigest,
  capabilityProfileDigest as profileDigest,
} from "./testCapabilityEnablementFixture";
import { configurationValidation as validation } from "./testConfigurationValidationFixture";

afterEach(() => vi.unstubAllGlobals());

describe("CapabilityEnablementPanel", () => {
  it("enables only an exact signed manifest-bound profile without operational inputs", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: enablement }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CapabilityEnablementPanel validation={validation} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /endpoint|target ip|host|port|username|password|token|secret reference|vault|command|parameter|runtime/i,
      }),
    ).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Capability profile digest" }), {
      target: { value: profileDigest },
    });
    fireEvent.click(
      screen.getByLabelText(
        "Enablement selects only signed C0/C1 metadata and grants no secret resolution, connection, runtime trust, execution, deployment, or mutation authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Enable governed capabilities" }));

    expect(await screen.findByText(enablement.enablement_id)).toBeVisible();
    expect(screen.getByText(enablement.instance_state)).toBeVisible();
    expect(screen.getByText("not granted")).toBeVisible();
    expect(screen.getByText("not authorized")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_validation_id: validation.validation_id,
      source_validation_digest: validation.canonical_digest,
      package_digest: validation.package_digest,
      capability_profile_id: enablement.capability_profile_id,
      capability_profile_digest: profileDigest,
      enablement_policy_id: enablement.enablement_policy_id,
      enablement_policy_digest: policyDigest,
      acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority: true,
    });
    for (const forbidden of [
      "capabilities",
      "capability_class",
      "required_permission",
      "endpoint_url",
      "target_ip",
      "host",
      "port",
      "secret_reference_id",
      "secret_value",
      "username",
      "password",
      "access_token",
      "command",
      "parameters",
      "runtime_trust_granted",
      "execution_authorized",
      "deployment_approved",
    ]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
