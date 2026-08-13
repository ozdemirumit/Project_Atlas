import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorTargetSessionVerification } from "../../api/targetSessionVerifications";
import { TargetSessionPanel } from "./TargetSessionPanel";
import { activation } from "./testTargetSessionFixture";

const profileDigest = "7".repeat(64);
const policyDigest = "c8cbf384b946a4388058ee0a9dbf3ba71b86a3138f5c8d12f2b09fd342ad797c";
const verification = {
  verification_id: "connector-target-session-verification.test",
  schema_version: "atlas.connector-target-session-verification.v1",
  version: 1,
  source_runtime_activation_id: activation.activation_id,
  source_runtime_activation_digest: activation.canonical_digest,
  organization_id: activation.organization_id,
  environment_id: activation.environment_id,
  package_digest: activation.package_digest,
  connector_id: activation.connector_id,
  release_version: activation.release_version,
  manifest_digest: activation.manifest_digest,
  instance_id: activation.instance_id,
  instance_key: activation.instance_key,
  display_name: activation.display_name,
  target_profile_digest: "5".repeat(64),
  target_identity_digest: "6".repeat(64),
  expected_target_product: "Synthetic read-only target",
  protocol_classification: "protocol.https-read-only",
  tls_classification: "tls.1-3-verified",
  session_profile_id: "connector-target-session-profile.development-synthetic",
  session_profile_digest: profileDigest,
  session_policy_id: "connector-target-session-policy.development",
  session_policy_digest: policyDigest,
  session_policy_version: "policy-v1",
  session_adapter_id: "connector-target-session-adapter.synthetic",
  connectivity_check_results: [
    { check_id: "connectivity.authentication", outcome: "connectivity.passed" },
    { check_id: "connectivity.read-only-privilege", outcome: "connectivity.passed" },
    { check_id: "connectivity.target-identity", outcome: "connectivity.passed" },
    { check_id: "connectivity.tls", outcome: "connectivity.passed" },
  ],
  instance_state: "enabled_target_session_verified",
  verified_by: "subject.connector-target-session-operator",
  purpose: "Verify one bounded read-only target session and close every ephemeral handle.",
  verified_at: "2026-08-06T00:00:02Z",
  canonical_digest: "4".repeat(64),
  runtime_health_verified: true,
  secret_brokerage_governed: true,
  target_connection_authorized: true,
  target_connectivity_verified: true,
  target_identity_verified: true,
  read_only_session_verified: true,
  target_session_established: true,
  target_session_closed: true,
  delivery_channel_closed: true,
  lease_revocation_confirmed: true,
  eligible_for_capability_invocation_governance: true,
  target_connected: false,
  capability_invocation_authorized: false,
  capability_invoked: false,
  scheduled: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorTargetSessionVerification;

afterEach(() => vi.unstubAllGlobals());

describe("TargetSessionPanel", () => {
  it("verifies a bounded session without exposing coordinates or reusable controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: verification }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><TargetSessionPanel activation={activation} /></QueryClientProvider>);

    expect(screen.queryByRole("textbox", { name: /target address|endpoint|host|port|credential|secret|lease|session handle|certificate|command|parameter/i })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Session profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Verification permits one bounded read-only connection/));
    fireEvent.click(screen.getByRole("button", { name: "Verify target session" }));

    expect(await screen.findByText(verification.verification_id)).toBeVisible();
    expect(screen.getAllByText("verified")).toHaveLength(2);
    expect(screen.getByText("read-only")).toBeVisible();
    expect(screen.getByText("closed")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_runtime_activation_id: activation.activation_id,
      source_runtime_activation_digest: activation.canonical_digest,
      package_digest: activation.package_digest,
      session_profile_id: verification.session_profile_id,
      session_profile_digest: profileDigest,
      session_policy_id: verification.session_policy_id,
      session_policy_digest: policyDigest,
      acknowledged_bounded_session_grants_no_invocation_execution_or_deployment: true,
    });
    for (const forbidden of ["target_address", "target_endpoint", "host", "port", "credential_profile_id", "secret_reference_id", "secret_store_profile_id", "broker_id", "lease_handle", "session_handle", "certificate_body", "raw_vendor_output", "command", "parameters", "execution_authorized", "deployment_approved"]) expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("reports session policy failures without presenting MFA as a prerequisite", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("policy rejected")));
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><TargetSessionPanel activation={activation} /></QueryClientProvider>);

    fireEvent.change(screen.getByRole("textbox", { name: "Session profile digest" }), { target: { value: profileDigest } });
    fireEvent.click(screen.getByLabelText(/Verification permits one bounded read-only connection/));
    fireEvent.click(screen.getByRole("button", { name: "Verify target session" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/signed session-policy and network controls.*read-only privilege.*requested scope.*separation of duties/i);
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|hardware|assurance/i);
  });
});
