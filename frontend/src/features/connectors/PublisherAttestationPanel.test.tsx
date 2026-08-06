import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorPackageApprovalRecord } from "../../api/connectors";
import type { ConnectorPublisherAttestation } from "../../api/publisherAttestations";
import { PublisherAttestationPanel } from "./PublisherAttestationPanel";

const digest = "a".repeat(64);
const approval = {
  request: {
    request_id: "connector-package-approval-request.test",
    canonical_digest: digest,
    package_digest: "b".repeat(64),
    environment_id: "environment.development",
  },
  decision: { outcome: "approve" },
  approval_valid: true,
  eligible_for_publisher_governance: true,
  promotion_blocked: false,
} as unknown as ConnectorPackageApprovalRecord;

const report = {
  report_id: "connector-publisher-attestation.test",
  schema_version: "atlas.connector-publisher-attestation.v1",
  version: 1,
  source_approval_request_id: approval.request.request_id,
  source_approval_request_digest: approval.request.canonical_digest,
  source_approval_decision_id: "connector-package-approval-decision.test",
  source_approval_decision_digest: "c".repeat(64),
  organization_id: "organization.development",
  environment_id: "environment.development",
  verified_by: "subject.publisher-independent-verifier",
  purpose: "Independently verify publisher identity and package provenance evidence.",
  package_digest: approval.request.package_digest,
  publisher_claim_id: "connector-publisher-claim.development",
  publisher_claim_digest: "d".repeat(64),
  publisher_id: "publisher.atlas-labs",
  publisher_display_name: "Atlas Labs",
  connector_id: "connector.hitachi-ops-center",
  release_version: "version.1.0.0",
  provenance_digest: "e".repeat(64),
  support_contact_ref: "support-contact.atlas-labs",
  support_expires_at: "2027-08-06T00:00:00Z",
  claim_issued_by: "subject.publisher-claim-authority",
  attestation_policy_id: "connector-publisher-attestation-policy.development",
  attestation_policy_digest:
    "296d294eec2036effbbe1e5a40eb825a0e88dd49b65ddea3bedc97088fe31af0",
  attestation_policy_version: "version.1.0",
  check_codes: ["check.approval.current"],
  outcome: "verified",
  reason_codes: [],
  verified_at: "2026-08-06T00:00:00Z",
  canonical_digest: "f".repeat(64),
  publisher_attested: true,
  eligible_for_package_signing_governance: true,
  promotion_blocked: false,
  reused: false,
  package_signed: false,
  connector_registered: false,
  connector_installed: false,
  connector_enabled: false,
  target_configured: false,
  credentials_resolved: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorPublisherAttestation;

afterEach(() => vi.unstubAllGlobals());

describe("PublisherAttestationPanel", () => {
  it("binds exact publisher evidence without exposing later lifecycle controls", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: report }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PublisherAttestationPanel approval={approval} />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("Publisher claim digest"), {
      target: { value: report.publisher_claim_digest },
    });
    fireEvent.click(
      screen.getByLabelText(
        "Attestation grants no signing, registry, installation, runtime, or execution authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Verify publisher evidence" }));

    expect(await screen.findByText("Atlas Labs")).toBeVisible();
    expect(screen.getByText("publisher.atlas-labs")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /register|install|enable|publish|execute/i }),
    ).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const init = fetchMock.mock.calls[0]?.[1];
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      source_approval_request_id: approval.request.request_id,
      source_approval_request_digest: approval.request.canonical_digest,
      package_digest: approval.request.package_digest,
      publisher_claim_id: report.publisher_claim_id,
      publisher_claim_digest: report.publisher_claim_digest,
      acknowledged_attestation_grants_no_lifecycle_authority: true,
    });
    expect(body).not.toHaveProperty("package_signed");
    expect(body).not.toHaveProperty("execution_authorized");
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
