import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ConnectorPackageApprovalRecord,
  ConnectorPackageFinalValidation,
} from "../../api/connectors";
import { PackageApprovalPanel } from "./PackageApprovalPanel";

const digest = "a".repeat(64);
const source = {
  validation_id: "connector-package-final-validation.test",
  canonical_digest: digest,
  package_digest: "b".repeat(64),
  environment_id: "environment.development",
  eligible_for_human_approval: true,
  promotion_blocked: false,
} as unknown as ConnectorPackageFinalValidation;

function approvalRecord(): ConnectorPackageApprovalRecord {
  return {
    request: {
      request_id: "connector-package-approval-request.test",
      schema_version: "atlas.connector-package-approval-request.v1",
      version: 1,
      source_final_validation_id: source.validation_id,
      source_final_validation_digest: source.canonical_digest,
      source_handoff_id: "mcp-builder-candidate-handoff.test",
      source_project_id: "mcp-builder-project.test",
      source_actor_set_digest: "c".repeat(64),
      organization_id: "organization.development",
      environment_id: "environment.development",
      requested_by: "subject.package-requester",
      purpose: "Approve this exact validated package for publisher governance review.",
      approval_policy_id: "connector-package-approval-policy.development",
      approval_policy_digest:
        "7c2b227494a4b93aa1539887880783543e3ae05c898931c01028111a68a10dde",
      approval_policy_version: "version.1.0",
      package_digest: source.package_digest,
      inventory_digest: "d".repeat(64),
      product_family: "product.synthetic",
      observed_product_version: "version.1.0",
      evidence_digest: "e".repeat(64),
      final_policy_id: "connector-final-policy.development",
      final_policy_digest: "f".repeat(64),
      final_policy_version: "version.1.0",
      stage_count: 13,
      passed_stage_count: 13,
      finding_count: 0,
      limitation_count: 1,
      blocking_risk_count: 0,
      created_at: "2026-08-06T10:00:00Z",
      expires_at: "2026-08-07T10:00:00Z",
      canonical_digest: digest,
      final_validation_completed: true,
      connector_approved: false,
      connector_rejected: false,
      eligible_for_publisher_governance: false,
      promotion_blocked: true,
      reused: false,
    },
    decision: null,
    state: "pending",
    approval_valid: false,
    connector_approved: false,
    connector_rejected: false,
    eligible_for_publisher_governance: false,
    promotion_blocked: true,
    package_signed: false,
    publisher_attested: false,
    connector_registered: false,
    connector_installed: false,
    connector_enabled: false,
    target_configured: false,
    credentials_resolved: false,
    runtime_trust_granted: false,
    execution_authorized: false,
    deployment_approved: false,
    infrastructure_mutation_performed: false,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("PackageApprovalPanel", () => {
  it("binds a neutral human decision to the exact pending packet", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const pending = approvalRecord();
    const approved: ConnectorPackageApprovalRecord = {
      ...pending,
      decision: {
        decision_id: "connector-package-approval-decision.test",
        schema_version: "atlas.connector-package-approval-decision.v1",
        version: 1,
        request_id: pending.request.request_id,
        request_version: 1,
        request_digest: pending.request.canonical_digest,
        outcome: "approve",
        decided_by: "subject.package-independent-approver",
        rationale: "The exact evidence is complete and independently satisfies policy.",
        organization_id: pending.request.organization_id,
        environment_id: pending.request.environment_id,
        source_final_validation_id: pending.request.source_final_validation_id,
        source_final_validation_digest: pending.request.source_final_validation_digest,
        package_digest: pending.request.package_digest,
        approval_policy_id: pending.request.approval_policy_id,
        approval_policy_digest: pending.request.approval_policy_digest,
        decided_at: "2026-08-06T10:05:00Z",
        canonical_digest: "9".repeat(64),
        reused: false,
      },
      state: "approved",
      approval_valid: true,
      connector_approved: true,
      eligible_for_publisher_governance: true,
      promotion_blocked: false,
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: pending }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: approved }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <PackageApprovalPanel
          source={source}
          subjectId="subject.package-independent-approver"
        />
      </QueryClientProvider>,
    );

    fireEvent.click(
      screen.getByLabelText("This request is not an approval and grants no connector authority."),
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit approval request" }));
    expect(await screen.findByText(pending.request.request_id)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.change(screen.getByLabelText("Rationale"), {
      target: { value: approved.decision?.rationale },
    });
    fireEvent.click(
      screen.getByLabelText(
        "This decision grants no signing, installation, runtime, or execution authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Record decision" }));

    expect(await screen.findByText("subject.package-independent-approver")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const decisionInit = fetchMock.mock.calls[1]?.[1];
    expect(typeof decisionInit?.body).toBe("string");
    const decisionBody = JSON.parse(
      typeof decisionInit?.body === "string" ? decisionInit.body : "{}",
    ) as Record<string, unknown>;
    expect(decisionBody).toMatchObject({
      expected_request_version: 1,
      request_digest: pending.request.canonical_digest,
      outcome: "approve",
      acknowledged_decision_grants_no_runtime_authority: true,
    });
    expect(decisionBody).not.toHaveProperty("execution_authorized");
    expect(new Headers(decisionInit?.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
