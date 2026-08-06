import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfigurationValidationPanel } from "./ConfigurationValidationPanel";
import { configurationValidation as validation } from "./testConfigurationValidationFixture";
import { credentialAssignment as assignment } from "./testCredentialAssignmentFixture";

const evidenceDigest = validation.evidence_digest;
const policyDigest = "5c683a88f96dd8597098811fb868453e1566767f92ffe940ea2f05cb2ef02aab";

afterEach(() => vi.unstubAllGlobals());

describe("ConfigurationValidationPanel", () => {
  it("verifies exact bounded evidence without target, secret, network, or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: validation }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><ConfigurationValidationPanel assignment={assignment} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /endpoint|target ip|host|port|username|password|token|secret reference|vault|raw probe|command|capability|runtime/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Evidence digest" }), { target: { value: evidenceDigest } });
    fireEvent.click(screen.getByLabelText("Validation grants no target access, secret resolution, capability, enablement, runtime, execution, deployment, or mutation authority."));
    fireEvent.click(screen.getByRole("button", { name: "Verify evidence" }));

    expect(await screen.findByText(validation.validation_id)).toBeVisible();
    expect(screen.getByText(validation.instance_state)).toBeVisible();
    expect(screen.getByRole("button", { name: "Enable governed capabilities" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /execute|deploy|connect/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_assignment_id: assignment.assignment_id,
      source_assignment_digest: assignment.canonical_digest,
      package_digest: assignment.package_digest,
      evidence_id: validation.evidence_id,
      evidence_digest: evidenceDigest,
      validation_policy_id: validation.validation_policy_id,
      validation_policy_digest: policyDigest,
      acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: true,
    });
    for (const forbidden of ["endpoint_url", "target_ip", "host", "port", "secret_reference_id", "secret_store_profile_id", "vault_path", "secret_value", "username", "password", "access_token", "private_key", "raw_probe_output", "command", "capability", "runtime", "execution_authorized"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
