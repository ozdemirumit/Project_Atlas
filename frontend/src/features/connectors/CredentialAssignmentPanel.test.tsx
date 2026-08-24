import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorCredentialAssignmentOption } from "../../api/credentialAssignments";
import { CredentialAssignmentPanel } from "./CredentialAssignmentPanel";
import { credentialAssignment as assignment } from "./testCredentialAssignmentFixture";
import { targetConfigurationBinding as binding } from "./testTargetBindingFixture";

const option = {
  source_target_binding_id: binding.binding_id,
  credential_profile_id: assignment.credential_profile_id,
  credential_profile_digest: assignment.credential_profile_digest,
  credential_class: assignment.credential_class,
  authentication_method: assignment.authentication_method,
  vendor_role: assignment.vendor_role,
  privilege_class: assignment.privilege_class,
  rotation_state: assignment.rotation_state,
  revocation_state: assignment.revocation_state,
  next_rotation_at: assignment.next_rotation_at,
  credential_profile_expires_at: "2030-01-01T00:00:00Z",
  credential_policy_id: assignment.credential_policy_id,
  credential_policy_digest: assignment.credential_policy_digest,
  credential_policy_version: assignment.credential_policy_version,
  credential_policy_expires_at: "2030-01-01T00:00:00Z",
  required_assurance_level: "SINGLE_FACTOR",
  resulting_instance_state: "disabled_credentials_assigned",
  resulting_credential_references_assigned: true,
  eligible_for_configuration_validation: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorCredentialAssignmentOption;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CredentialAssignmentPanel", () => {
  it("assigns only a server-provided governed profile without secret or runtime input", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input, init) => {
      const url = input instanceof Request ? input.url : input instanceof URL ? input.href : input;
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ data: assignment }), { status: 201 }));
      }
      if (url.includes("/options?")) {
        return Promise.resolve(new Response(JSON.stringify({ data: [option] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ data: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <CredentialAssignmentPanel binding={binding} />
      </QueryClientProvider>,
    );

    await screen.findByRole("combobox", { name: "Governed credential profile" });
    expect(
      screen.queryByRole("textbox", {
        name: /secret reference|vault|store path|username|password|token value|private key|endpoint|target address|profile digest|policy digest/i,
      }),
    ).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Assignment grants no secret access, credential resolution, capability, enablement, runtime, execution, or deployment authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Assign credential profile" }));

    expect(await screen.findByText(assignment.assignment_id)).toBeVisible();
    expect(screen.getAllByText("Disabled / credentials assigned").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /enable|execute|deploy/i })).toBeNull();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => call[1]?.method === "POST")).toBe(true),
    );
    const postCall = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    const init = postCall?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_target_binding_id: binding.binding_id,
      source_target_binding_digest: binding.canonical_digest,
      package_digest: binding.package_digest,
      credential_profile_id: option.credential_profile_id,
      credential_profile_digest: option.credential_profile_digest,
      credential_policy_id: option.credential_policy_id,
      credential_policy_digest: option.credential_policy_digest,
      acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority: true,
    });
    for (const forbidden of [
      "secret_reference_id",
      "secret_store_profile_id",
      "vault_path",
      "secret_value",
      "username",
      "password",
      "access_token",
      "private_key",
      "endpoint",
      "target_id",
      "capability",
      "runtime",
      "execution_authorized",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("renders a reloaded assignment without offering another assignment mutation", () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CredentialAssignmentPanel existingAssignment={assignment} binding={binding} />
      </QueryClientProvider>,
    );

    expect(screen.getByText(assignment.assignment_id)).toBeVisible();
    expect(screen.getAllByText("Disabled / credentials assigned").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Assign credential profile" })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps legal profile and policy identifiers collision-free in the option value", async () => {
    const first = {
      ...option,
      credential_profile_id: "connector-credential-profile.alpha:shared",
      credential_policy_id: "connector-credential-policy.beta",
    };
    const second = {
      ...option,
      credential_profile_id: "connector-credential-profile.alpha",
      credential_policy_id: "shared:connector-credential-policy.beta",
      vendor_role: "vendor-role.storage-auditor",
    };
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = input instanceof Request ? input.url : input instanceof URL ? input.href : input;
      return Promise.resolve(
        new Response(
          JSON.stringify({ data: url.includes("/options?") ? [first, second] : [] }),
          { status: 200 },
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CredentialAssignmentPanel binding={binding} />
      </QueryClientProvider>,
    );

    const select = await screen.findByRole("combobox", { name: "Governed credential profile" });
    const values = Array.from((select as HTMLSelectElement).options).map((item) => item.value);
    expect(values).toHaveLength(2);
    expect(new Set(values).size).toBe(2);
  });
});
