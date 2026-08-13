import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorInvocationAuthorization } from "../../api/invocationAuthorizations";
import type { ConnectorTargetSessionVerification } from "../../api/targetSessionVerifications";
import { InvocationAuthorizationPanel } from "./InvocationAuthorizationPanel";
import { activation } from "./testTargetSessionFixture";

const profileDigest = "7".repeat(64);
const envelopeDigest = "8".repeat(64);
const policyDigest = "9".repeat(64);
const targetSession = {
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
  session_profile_digest: "3".repeat(64),
  session_policy_id: "connector-target-session-policy.development",
  session_policy_digest: "4".repeat(64),
  session_policy_version: "policy-v1",
  session_adapter_id: "connector-target-session-adapter.synthetic",
  connectivity_check_results: [],
  instance_state: "enabled_target_session_verified",
  verified_by: "subject.connector-target-session-operator",
  purpose: "Verify one bounded target session and close every ephemeral handle.",
  verified_at: "2026-08-06T00:00:02Z",
  canonical_digest: "a".repeat(64),
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

const authorization = {
  authorization_id: "connector-invocation-authorization.test",
  schema_version: "atlas.connector-invocation-authorization.v1",
  version: 1,
  source_target_session_verification_id: targetSession.verification_id,
  source_target_session_digest: targetSession.canonical_digest,
  organization_id: targetSession.organization_id,
  environment_id: targetSession.environment_id,
  package_digest: targetSession.package_digest,
  connector_id: targetSession.connector_id,
  release_version: targetSession.release_version,
  manifest_digest: targetSession.manifest_digest,
  instance_id: targetSession.instance_id,
  instance_key: targetSession.instance_key,
  display_name: targetSession.display_name,
  target_profile_digest: targetSession.target_profile_digest,
  target_identity_digest: targetSession.target_identity_digest,
  capability_id: "capability.storage.health.read",
  capability_class: "C1",
  required_permission: "storage.health.read",
  invocation_profile_id: "connector-invocation-profile.development-read-only",
  invocation_profile_digest: profileDigest,
  input_envelope_id: "connector-invocation-input-envelope.development-empty",
  input_envelope_digest: envelopeDigest,
  input_envelope_schema: "atlas.connector-invocation-input-envelope.v1",
  normalized_input_digest: "b".repeat(64),
  input_schema_digest: "c".repeat(64),
  output_schema_digest: "d".repeat(64),
  result_policy_digest: "e".repeat(64),
  maximum_timeout_seconds: 30,
  maximum_output_bytes: 262144,
  authorization_policy_id: "connector-invocation-authorization-policy.development",
  authorization_policy_digest: policyDigest,
  authorization_policy_version: "policy-v1",
  instance_state: "enabled_capability_invocation_governed",
  authorized_by: "subject.connector-invocation-authorizer",
  purpose: "Authorize one bounded read-only capability invocation without invoking it.",
  authorized_at: "2026-08-06T00:00:02Z",
  expires_at: "2026-08-06T00:15:02Z",
  canonical_digest: "f".repeat(64),
  target_session_verified: true,
  capability_enabled: true,
  capability_permission_verified: true,
  capability_invocation_authorized: true,
  eligible_for_bounded_capability_invocation: true,
  single_use: true,
  renewable: false,
  consumed: false,
  target_connected: false,
  capability_invoked: false,
  scheduled: false,
  result_received: false,
  result_validated: false,
  evidence_ingested: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorInvocationAuthorization;

afterEach(() => vi.unstubAllGlobals());

describe("InvocationAuthorizationPanel", () => {
  it("authorizes exactly one capability without invoking or exposing runtime controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: authorization }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <InvocationAuthorizationPanel targetSession={targetSession} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /target address|endpoint|host|port|credential|secret|lease|session handle|command|raw parameter/i,
      }),
    ).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Invocation profile digest" }), {
      target: { value: profileDigest },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Input envelope digest" }), {
      target: { value: envelopeDigest },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Signed policy digest" }), {
      target: { value: policyDigest },
    });
    fireEvent.click(screen.getByLabelText(/Authorization is short-lived, single-use/));
    fireEvent.click(screen.getByRole("button", { name: "Authorize invocation" }));

    expect(await screen.findByText(authorization.authorization_id)).toBeVisible();
    expect(screen.getByText("single use")).toBeVisible();
    expect(screen.getByText("unconsumed")).toBeVisible();
    expect(screen.getByText("verified")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(
      typeof init?.body === "string" ? init.body : "{}",
    ) as Record<string, unknown>;
    expect(body).toMatchObject({
      source_target_session_verification_id: targetSession.verification_id,
      source_target_session_digest: targetSession.canonical_digest,
      capability_id: authorization.capability_id,
      invocation_profile_id: authorization.invocation_profile_id,
      invocation_profile_digest: profileDigest,
      input_envelope_id: authorization.input_envelope_id,
      input_envelope_digest: envelopeDigest,
      authorization_policy_id: authorization.authorization_policy_id,
      authorization_policy_digest: policyDigest,
      acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment:
        true,
    });
    for (const forbidden of [
      "raw_input",
      "input_values",
      "raw_parameters",
      "target_address",
      "target_endpoint",
      "host",
      "port",
      "credential_profile_id",
      "secret_reference_id",
      "lease_handle",
      "session_handle",
      "command",
      "execution_authorized",
      "deployment_approved",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("reports authorization policy failures without presenting MFA as a prerequisite", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("policy rejected")));
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const view = render(
      <QueryClientProvider client={client}>
        <InvocationAuthorizationPanel targetSession={targetSession} />
      </QueryClientProvider>,
    );
    const panel = within(view.container);

    fireEvent.change(panel.getByRole("textbox", { name: "Invocation profile digest" }), {
      target: { value: profileDigest },
    });
    fireEvent.change(panel.getByRole("textbox", { name: "Input envelope digest" }), {
      target: { value: envelopeDigest },
    });
    fireEvent.change(panel.getByRole("textbox", { name: "Signed policy digest" }), {
      target: { value: policyDigest },
    });
    fireEvent.click(panel.getByLabelText(/Authorization is short-lived, single-use/));
    fireEvent.click(panel.getByRole("button", { name: "Authorize invocation" }));

    const alert = await panel.findByRole("alert");
    expect(alert).toHaveTextContent(/signed authorization-policy evidence.*requested scope.*separation of duties/i);
    expect(alert).not.toHaveTextContent(/MFA|multi[- ]factor|hardware|assurance/i);
  });
});
