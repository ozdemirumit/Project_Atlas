import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConnectorConfigurationValidationOption } from "../../api/configurationValidations";
import { ConfigurationValidationPanel } from "./ConfigurationValidationPanel";
import { configurationValidation as validation } from "./testConfigurationValidationFixture";
import { credentialAssignment as assignment } from "./testCredentialAssignmentFixture";

const option = {
  source_assignment_id: assignment.assignment_id,
  source_assignment_digest: assignment.canonical_digest,
  package_digest: assignment.package_digest,
  evidence_id: validation.evidence_id,
  evidence_digest: validation.evidence_digest,
  evidence_observed_at: validation.evidence_observed_at,
  evidence_expires_at: "2030-01-01T00:00:00Z",
  configuration_result: validation.configuration_result,
  connectivity_result: validation.connectivity_result,
  tls_result: validation.tls_result,
  endpoint_identity_result: validation.endpoint_identity_result,
  authentication_result: validation.authentication_result,
  authorization_result: validation.authorization_result,
  product_identity_result: validation.product_identity_result,
  latency_band: validation.latency_band,
  completed_checks: validation.completed_checks,
  validation_policy_id: validation.validation_policy_id,
  validation_policy_digest: validation.validation_policy_digest,
  validation_policy_version: validation.validation_policy_version,
  validation_policy_expires_at: "2030-01-01T00:00:00Z",
  required_assurance_level: "SINGLE_FACTOR",
  resulting_instance_state: "disabled_configuration_validated",
  resulting_configuration_validated: true,
  resulting_connectivity_evidence_verified: true,
  eligible_for_capability_governance: true,
  credentials_resolved: false,
  connector_enabled: false,
  runtime_trust_granted: false,
  execution_authorized: false,
  deployment_approved: false,
  infrastructure_mutation_performed: false,
} satisfies ConnectorConfigurationValidationOption;

const sessionScopeKey = "subject.connector-operator:org.atlas:env.atlas";

function renderPanel(existingValidation = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const rendered = render(
    <QueryClientProvider client={client}>
      <ConfigurationValidationPanel
        assignment={assignment}
        existingValidation={existingValidation ? validation : undefined}
        sessionScopeKey={sessionScopeKey}
      />
    </QueryClientProvider>,
  );
  return { ...rendered, client };
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ConfigurationValidationPanel", () => {
  it("uses only server-selected evidence and grants no operational authority", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = requestUrl(input);
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ data: validation }), { status: 201 }));
      }
      if (url.includes("/options?")) {
        return Promise.resolve(new Response(JSON.stringify({ data: [option] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ data: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    expect(await screen.findByLabelText("Governed evidence and policy")).toHaveTextContent(
      validation.evidence_id,
    );
    expect(
      screen.queryByRole("textbox", {
        name: /evidence id|evidence digest|policy id|policy digest|endpoint|target ip|host|port|username|password|token|secret reference|vault|raw probe|command/i,
      }),
    ).toBeNull();
    fireEvent.click(
      screen.getByLabelText(
        "Validation grants no target access, secret resolution, capability, enablement, runtime, execution, deployment, or mutation authority.",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Verify signed evidence" }));

    expect(await screen.findByText(validation.validation_id)).toBeVisible();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true),
    );
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(typeof post?.[1]?.body === "string" ? post[1].body : "{}") as Record<string, unknown>;
    expect(body).toMatchObject({
      source_assignment_id: assignment.assignment_id,
      source_assignment_digest: option.source_assignment_digest,
      evidence_id: option.evidence_id,
      evidence_digest: option.evidence_digest,
      validation_policy_id: option.validation_policy_id,
      validation_policy_digest: option.validation_policy_digest,
      acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority: true,
    });
    expect(screen.queryByRole("button", { name: /enable|execute|deploy|connect/i })).toBeNull();
  });

  it("renders a restored validation as read-only evidence", () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>());
    renderPanel(true);

    expect(screen.getByText(validation.validation_id)).toBeVisible();
    expect(screen.getByText(validation.evidence_id)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Verify signed evidence" })).toBeNull();
    expect(screen.queryByRole("button", { name: /enable|execute|deploy|connect/i })).toBeNull();
  });

  it("keeps the validation blocked when no compatible evidence exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({ data: [] }), { status: 200 })),
      ),
    );
    renderPanel();

    expect(await screen.findByText("No compatible signed probe evidence")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Verify signed evidence" })).toBeNull();
  });

  it("keeps legal identifier tuples collision-free", async () => {
    const first = { ...option, evidence_id: "evidence.alpha:beta", validation_policy_id: "policy.gamma" };
    const second = { ...option, evidence_id: "evidence.alpha", validation_policy_id: "beta:policy.gamma" };
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((input) =>
        Promise.resolve(
          requestUrl(input).includes("/options?")
            ? new Response(JSON.stringify({ data: [first, second] }), { status: 200 })
            : new Response(JSON.stringify({ data: [] }), { status: 200 }),
        ),
      ),
    );
    renderPanel();

    const select = await screen.findByLabelText("Governed evidence and policy");
    const values = Array.from(select.querySelectorAll("option")).map((item) => item.value);
    expect(new Set(values).size).toBe(2);
  });

  it("submits the visible fallback when selected evidence disappears on refetch", async () => {
    document.cookie = "atlas_csrf=test-csrf; path=/";
    const replacement = {
      ...option,
      evidence_id: "connector-configuration-evidence.replacement",
      evidence_digest: "d".repeat(64),
    };
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ data: validation }), { status: 201 }));
      }
      return Promise.resolve(
        requestUrl(input).includes("/options?")
          ? new Response(JSON.stringify({ data: [option, replacement] }), { status: 200 })
          : new Response(JSON.stringify({ data: [] }), { status: 200 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const { client } = renderPanel();
    const select = await screen.findByLabelText("Governed evidence and policy");
    fireEvent.change(select, {
      target: {
        value: JSON.stringify([
          replacement.evidence_id,
          replacement.evidence_digest,
          replacement.validation_policy_id,
          replacement.validation_policy_digest,
        ]),
      },
    });

    act(() => {
      client.setQueryData(
        ["connector-configuration-validation-options", sessionScopeKey, assignment.assignment_id],
        [option],
      );
    });
    await waitFor(() => expect(select).toHaveValue(JSON.stringify([
      option.evidence_id,
      option.evidence_digest,
      option.validation_policy_id,
      option.validation_policy_digest,
    ])));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Verify signed evidence" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(typeof post?.[1]?.body === "string" ? post[1].body : "{}") as Record<string, unknown>;
    expect(body.evidence_id).toBe(option.evidence_id);
    expect(body.evidence_digest).toBe(option.evidence_digest);
  });
});
