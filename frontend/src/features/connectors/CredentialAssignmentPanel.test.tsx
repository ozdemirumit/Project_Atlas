import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CredentialAssignmentPanel } from "./CredentialAssignmentPanel";
import { credentialAssignment as assignment } from "./testCredentialAssignmentFixture";
import { targetConfigurationBinding as binding } from "./testTargetBindingFixture";

afterEach(() => vi.unstubAllGlobals());

describe("CredentialAssignmentPanel", () => {
  it("assigns exact profile metadata without secret, store, target, or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: assignment }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><CredentialAssignmentPanel binding={binding} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /secret reference|vault|store path|username|password|token value|private key|endpoint|target address|runtime command/i })).toBeNull();
    fireEvent.click(screen.getByLabelText("Assignment grants no secret access, credential resolution, capability, enablement, runtime, execution, or deployment authority."));
    fireEvent.click(screen.getByRole("button", { name: "Assign credential profile" }));

    expect(await screen.findByText(assignment.assignment_id)).toBeVisible();
    expect(screen.getByText(assignment.instance_state)).toBeVisible();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy/i })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_target_binding_id: binding.binding_id,
      source_target_binding_digest: binding.canonical_digest,
      package_digest: binding.package_digest,
      credential_profile_id: assignment.credential_profile_id,
      credential_profile_digest: assignment.credential_profile_digest,
      credential_policy_id: assignment.credential_policy_id,
      credential_policy_digest: assignment.credential_policy_digest,
      acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority: true,
    });
    for (const forbidden of ["secret_reference_id", "secret_store_profile_id", "vault_path", "secret_value", "username", "password", "access_token", "private_key", "endpoint", "target_id", "capability", "runtime", "execution_authorized"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
