import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConnectorInvocationAuthorization,
  getConnectorInvocationAuthorizationOptions,
  getConnectorInvocationAuthorizations,
} from "./invocationAuthorizations";
import {
  invocationAuthorizationInventoryItem as authorization,
  invocationAuthorizationOption as option,
} from "../features/connectors/testInvocationAuthorizationFixture";
import { targetSessionVerificationInventoryItem as targetSession } from "../features/connectors/testTargetSessionFixture";

afterEach(() => vi.restoreAllMocks());

describe("invocation authorization API client", () => {
  it("reloads minimized inventory only within the exact target-session scope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [authorization] }), { status: 200 }),
    );

    await expect(getConnectorInvocationAuthorizations({
      sourceTargetSessionVerificationId: targetSession.verification_id,
    })).resolves.toEqual([authorization]);
    const request = fetchMock.mock.calls[0]?.[0];
    const requestUrl = request instanceof Request ? request.url : request;
    expect(requestUrl).toContain(
      `source_target_session_verification_id=${encodeURIComponent(targetSession.verification_id)}`,
    );
  });

  it("rejects inventory that crosses the requested target-session scope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: [{
          ...authorization,
          source_target_session_verification_id: "connector-target-session-verification.foreign",
        }],
      }), { status: 200 }),
    );

    await expect(getConnectorInvocationAuthorizations({
      sourceTargetSessionVerificationId: targetSession.verification_id,
    })).rejects.toThrow("crossed the requested target-session scope");
  });

  it("accepts the exact minimized server option contract", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [option] }), { status: 200 }),
    );

    await expect(getConnectorInvocationAuthorizationOptions(targetSession.verification_id))
      .resolves.toEqual([option]);
  });

  it.each([
    ["target_address", "10.0.0.10"],
    ["target_endpoint", "https://storage.internal"],
    ["credential_profile_id", "credential.test"],
    ["secret_reference_id", "secret.test"],
    ["lease_handle", "lease.test"],
    ["session_handle", "session.test"],
    ["raw_input", { key: "value" }],
    ["command", "show storage"],
    ["raw_vendor_output", "unsafe"],
    ["mfa_challenge", "unsafe"],
    ["browser_session_id", "unsafe"],
  ])("rejects prohibited invocation option field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [{ ...option, [field]: value }] }), { status: 200 }),
    );

    await expect(getConnectorInvocationAuthorizationOptions(targetSession.verification_id))
      .rejects.toThrow("unsafe evidence");
  });

  it.each([
    ["source_target_session_digest", targetSession.canonical_digest],
    ["package_digest", option.package_digest],
    ["required_permission", option.required_permission],
    ["invocation_profile_id", option.invocation_profile_id],
    ["input_envelope_id", option.input_envelope_id],
    ["authorization_policy_id", option.authorization_policy_id],
    ["authorized_by", "subject.test"],
    ["purpose", "unsafe broad inventory"],
    ["reused", false],
    ["request_fingerprint", "unsafe"],
  ])("rejects non-minimized inventory field %s", async (field, value) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ data: [{ ...authorization, [field]: value }] }),
        { status: 200 },
      ),
    );

    await expect(getConnectorInvocationAuthorizations({
      sourceTargetSessionVerificationId: targetSession.verification_id,
    })).rejects.toThrow("unsafe records");
  });

  it("posts only the exact selected option, purpose and bounded acknowledgement", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: authorization }), { status: 201 }),
    );

    await expect(createConnectorInvocationAuthorization({
      targetSession,
      option,
      purpose:
        "  Authorize one bounded read-only capability invocation without invoking it.  ",
    })).resolves.toEqual({ data: authorization });

    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(
      typeof init?.body === "string" ? init.body : "{}",
    ) as Record<string, unknown>;
    expect(body).toEqual({
      schema_version: "atlas.connector-invocation-authorization-input.v1",
      source_target_session_verification_id: targetSession.verification_id,
      source_target_session_digest: option.source_target_session_digest,
      package_digest: option.package_digest,
      capability_id: option.capability_id,
      invocation_profile_id: option.invocation_profile_id,
      invocation_profile_digest: option.invocation_profile_digest,
      input_envelope_id: option.input_envelope_id,
      input_envelope_digest: option.input_envelope_digest,
      authorization_policy_id: option.authorization_policy_id,
      authorization_policy_digest: option.authorization_policy_digest,
      purpose: "Authorize one bounded read-only capability invocation without invoking it.",
      acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment:
        true,
    });
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });

  it("rejects a response that does not match the selected option", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        data: { ...authorization, authorization_policy_digest: "f".repeat(64) },
      }), { status: 201 }),
    );

    await expect(createConnectorInvocationAuthorization({
      targetSession,
      option,
      purpose: "Authorize one bounded read-only capability invocation without invoking it.",
    })).rejects.toThrow("does not match the exact governed evidence");
  });
});
