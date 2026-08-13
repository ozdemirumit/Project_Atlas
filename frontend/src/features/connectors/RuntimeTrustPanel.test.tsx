import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RuntimeTrustPanel } from "./RuntimeTrustPanel";
import { capabilityEnablement as enablement } from "./testCapabilityEnablementFixture";
import {
  runtimePolicyDigest as policyDigest,
  runtimeProfileDigest as profileDigest,
  runtimeTrustGrant as grant,
} from "./testRuntimeTrustFixture";

afterEach(() => vi.unstubAllGlobals());

describe("RuntimeTrustPanel", () => {
  it("binds exact signed runtime evidence without caller-controlled operational inputs", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: grant }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><RuntimeTrustPanel enablement={enablement} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /runner|image|workload|isolation|filesystem|egress|secret|target|host|port|command|parameter/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Runtime profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Trust binds only the signed isolated runtime boundary/));
    fireEvent.click(screen.getByRole("button", { name: "Grant runtime trust" }));

    expect(await screen.findByText(grant.grant_id)).toBeVisible();
    expect(screen.getByText(grant.instance_state)).toBeVisible();
    expect(screen.getByText("not started")).toBeVisible();
    expect(screen.getByText("not resolved")).toBeVisible();
    expect(screen.getByText("not connected")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_enablement_id: enablement.enablement_id,
      source_enablement_digest: enablement.canonical_digest,
      package_digest: enablement.package_digest,
      runtime_profile_id: grant.runtime_profile_id,
      runtime_profile_digest: profileDigest,
      trust_policy_id: grant.trust_policy_id,
      trust_policy_digest: policyDigest,
      acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority: true,
    });
    for (const forbidden of ["runner_runtime_id", "runner_pool_id", "runner_image_digest", "runner_workload_identity_id", "isolation_profile_id", "filesystem_policy_id", "egress_policy_id", "secret_delivery_policy_id", "target_profile_id", "credential_profile_id", "endpoint_url", "host", "port", "secret_reference_id", "command", "parameters", "execution_authorized", "deployment_approved"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("reports policy evidence failures without presenting MFA as a prerequisite", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("policy rejected")));
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><RuntimeTrustPanel enablement={enablement} /></QueryClientProvider>);

    fireEvent.change(screen.getByRole("textbox", { name: "Runtime profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Trust binds only the signed isolated runtime boundary/));
    fireEvent.click(screen.getByRole("button", { name: "Grant runtime trust" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/signed runtime controls.*trust-policy evidence.*requested scope.*separation of duties/i);
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|hardware|assurance/i);
  });
});
