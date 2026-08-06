import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorBoundedInvocation } from "../../api/boundedInvocations";
import type { ConnectorInvocationAuthorization } from "../../api/invocationAuthorizations";
import { BoundedInvocationPanel } from "./BoundedInvocationPanel";

const policyDigest = "e0f70ea92c5b6eeddb1a1818c595d2f6896a4ff585379d789737d0c1413870fa";
const authorization = {
  authorization_id: "connector-invocation-authorization.test",
  schema_version: "atlas.connector-invocation-authorization.v1",
  version: 1,
  source_target_session_verification_id: "connector-target-session-verification.test",
  source_target_session_digest: "1".repeat(64),
  organization_id: "organization.development",
  environment_id: "environment.development",
  package_digest: "2".repeat(64),
  connector_id: "connector.storage.test",
  release_version: "release.1-0-0",
  manifest_digest: "3".repeat(64),
  instance_id: "connector-instance.test",
  instance_key: "connector-instance-key.test",
  display_name: "Test storage connector",
  target_profile_digest: "4".repeat(64),
  target_identity_digest: "5".repeat(64),
  capability_id: "capability.storage.health.read",
  capability_class: "C1",
  required_permission: "storage.health.read",
  invocation_profile_id: "connector-invocation-profile.development-read-only",
  invocation_profile_digest: "6".repeat(64),
  input_envelope_id: "connector-invocation-input-envelope.development-empty",
  input_envelope_digest: "7".repeat(64),
  input_envelope_schema: "atlas.connector-invocation-input-envelope.v1",
  normalized_input_digest: "8".repeat(64),
  input_schema_digest: "9".repeat(64),
  output_schema_digest: "a".repeat(64),
  result_policy_digest: "b".repeat(64),
  maximum_timeout_seconds: 30,
  maximum_output_bytes: 262144,
  authorization_policy_id: "connector-invocation-authorization-policy.development",
  authorization_policy_digest: "c".repeat(64),
  authorization_policy_version: "policy-v1",
  instance_state: "enabled_capability_invocation_governed",
  authorized_by: "subject.connector-invocation-authorizer",
  purpose: "Authorize one bounded read-only capability invocation without invoking it.",
  authorized_at: "2026-08-06T00:00:02Z",
  expires_at: "2026-08-06T00:15:02Z",
  canonical_digest: "d".repeat(64),
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

const invocation = {
  invocation_id: "connector-bounded-invocation.test",
  schema_version: "atlas.connector-bounded-invocation.v1",
  version: 1,
  consumption_claim_id: "connector-invocation-consumption-claim.test",
  source_authorization_id: authorization.authorization_id,
  source_authorization_digest: authorization.canonical_digest,
  organization_id: authorization.organization_id,
  environment_id: authorization.environment_id,
  package_digest: authorization.package_digest,
  connector_id: authorization.connector_id,
  release_version: authorization.release_version,
  manifest_digest: authorization.manifest_digest,
  instance_id: authorization.instance_id,
  instance_key: authorization.instance_key,
  display_name: authorization.display_name,
  capability_id: authorization.capability_id,
  capability_class: authorization.capability_class,
  required_permission: authorization.required_permission,
  invocation_profile_id: authorization.invocation_profile_id,
  invocation_profile_digest: authorization.invocation_profile_digest,
  input_envelope_id: authorization.input_envelope_id,
  input_envelope_digest: authorization.input_envelope_digest,
  input_schema_digest: authorization.input_schema_digest,
  output_schema_digest: authorization.output_schema_digest,
  result_policy_digest: authorization.result_policy_digest,
  invocation_policy_id: "connector-bounded-invocation-policy.development",
  invocation_policy_digest: policyDigest,
  invocation_policy_version: "policy-v1",
  invocation_adapter_id: "connector-bounded-invocation-adapter.synthetic",
  normalized_redacted_result_digest: "e".repeat(64),
  observation_count: 1,
  output_bytes: 256,
  instance_state: "enabled_bounded_capability_invocation_completed",
  invoked_by: "subject.connector-bounded-invoker",
  purpose: "Invoke one authorized read-only capability and close every ephemeral resource.",
  started_at: "2026-08-06T00:00:03Z",
  completed_at: "2026-08-06T00:00:03.025Z",
  canonical_digest: "f".repeat(64),
  authorization_consumed: true,
  target_connection_opened: true,
  capability_invoked: true,
  result_received: true,
  result_validated: true,
  result_redacted: true,
  target_session_closed: true,
  delivery_channel_closed: true,
  lease_revocation_confirmed: true,
  target_connected: false,
  reusable_session_available: false,
  scheduled: false,
  evidence_ingested: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
  reused: false,
} satisfies ConnectorBoundedInvocation;

afterEach(() => vi.unstubAllGlobals());

describe("BoundedInvocationPanel", () => {
  it("consumes one authorization and renders only minimized closed-result evidence", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: invocation }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <BoundedInvocationPanel authorization={authorization} />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByRole("textbox", {
        name: /target address|endpoint|host|port|credential|secret|lease|session handle|command|input value|raw output/i,
      }),
    ).toBeNull();
    fireEvent.click(screen.getByLabelText(/authorization is consumed before the call/i));
    fireEvent.click(screen.getByRole("button", { name: "Invoke once" }));

    expect(await screen.findByText(invocation.invocation_id)).toBeVisible();
    expect(screen.getByText("invoked once")).toBeVisible();
    expect(screen.getByText("validated")).toBeVisible();
    expect(screen.getByText("disconnected")).toBeVisible();
    expect(screen.getByText("not ingested")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(
      typeof init?.body === "string" ? init.body : "{}",
    ) as Record<string, unknown>;
    expect(body).toMatchObject({
      source_authorization_id: authorization.authorization_id,
      source_authorization_digest: authorization.canonical_digest,
      package_digest: authorization.package_digest,
      invocation_policy_id: invocation.invocation_policy_id,
      invocation_policy_digest: policyDigest,
      acknowledged_authorization_is_consumed_once_without_retry_on_uncertain_outcome: true,
    });
    for (const forbidden of [
      "capability_id",
      "handler",
      "input",
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
      "timeout",
      "output_limit",
      "schedule",
      "execution_authorized",
      "deployment_approved",
    ])
      expect(body).not.toHaveProperty(forbidden);
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
