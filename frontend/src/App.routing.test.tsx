import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const operationalRender = vi.hoisted(() => vi.fn());

vi.mock("./OperationalApplication", () => ({
  OperationalApplication: ({
    activeConnectorView,
    activeHealthView,
    activeWorkspace,
    onNavigateConnectorView,
    onNavigateHealthView,
    onNavigate,
  }: {
    activeConnectorView: "inventory" | "builder" | "runtime" | "knowledge";
    activeHealthView: "overview" | "investigate" | "deployments" | "governance";
    activeWorkspace: "Health" | "Connectors";
    onNavigateConnectorView: (view: "knowledge") => void;
    onNavigateHealthView: (view: "governance") => void;
    onNavigate: (workspace: "Workspace") => void;
  }) => {
    const activeView = activeWorkspace === "Connectors" ? activeConnectorView : activeHealthView;
    operationalRender(activeWorkspace, activeView);
    return (
      <main>
        <h1>Loaded {activeWorkspace} {activeView}</h1>
        <button type="button" onClick={() => onNavigate("Workspace")}>
          Return to Workspace
        </button>
        <button type="button" onClick={() => onNavigateHealthView("governance")}>
          Open governance
        </button>
        <button type="button" onClick={() => onNavigateConnectorView("knowledge")}>
          Open connector knowledge
        </button>
      </main>
    );
  },
}));

import { App } from "./ApplicationCoordinator";

const identity = {
  data: {
    subject_id: "subject.operator",
    display_name: "Atlas Operator",
    subject_kind: "human",
    organization_id: "org.test",
    role_ids: ["role.operator"],
    group_ids: [],
    authentication: {
      provider_id: "provider.test",
      method: "development",
      assurance_level: "development",
      authenticated_at: "2026-08-10T00:00:00Z",
    },
    scope: {
      organization_id: "org.test",
      environment_id: "environment.test",
      site_id: "site.test",
      domain_id: "domain.test",
      resource_id: "resource.test",
      capability_class: "read",
    },
    authorization_decision_id: "decision.test",
    effective_role_versions: ["role.operator:1"],
    effective_assignment_versions: ["assignment.operator:1"],
  },
  meta: { correlation_id: "correlation.test", generated_at: "2026-08-10T00:00:00Z" },
};

const platform = {
  data: {
    service: "atlas",
    version: "test",
    environment: "test",
    status: "healthy",
    components: [],
    warnings: [],
    operational_posture: {
      contract_id: "platform-posture.advisory-only",
      contract_version: "1.0.0",
      platform_mode: "advisory_only",
      operational_execution_enabled: false,
      process_resume_consumption_enabled: false,
      dispatch_enabled: false,
      infrastructure_mutation_enabled: false,
      ai_execution_authorized: false,
      contract_digest: "edfde9fc024bab918b587740e23d96e95f8dc3329e8e34f28897dad590c212c1",
    },
  },
  meta: { correlation_id: "correlation.platform", generated_at: "2026-08-10T00:00:00Z" },
};

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

function mockAuthenticatedRequests() {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/identity/me")) {
      return Promise.resolve(new Response(JSON.stringify(identity), { status: 200 }));
    }
    if (url.includes("/platform/status")) {
      return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
    }
    return Promise.resolve(new Response(null, { status: 404 }));
  });
}

describe("workspace route loading boundary", () => {
  beforeEach(() => {
    operationalRender.mockClear();
    vi.restoreAllMocks();
  });

  afterEach(() => cleanup());

  it("renders authenticated Workspace without evaluating the operational component", async () => {
    window.history.replaceState(null, "", "/#/workspace");
    mockAuthenticatedRequests();

    renderApp();

    expect(await screen.findByRole("heading", { name: "Storage conversations" })).toBeVisible();
    expect(operationalRender).not.toHaveBeenCalled();
  });

  it("loads Health after a Workspace navigation and preserves the URL", async () => {
    window.history.replaceState(null, "", "/#/workspace");
    mockAuthenticatedRequests();
    renderApp();
    await screen.findByRole("heading", { name: "Storage conversations" });

    fireEvent.click(screen.getByRole("button", { name: /^Health$/ }));

    expect(await screen.findByRole("heading", { name: "Loaded Health overview" })).toBeVisible();
    expect(window.location.hash).toBe("#/health/overview");
    expect(operationalRender).toHaveBeenCalledWith("Health", "overview");
  });

  it("opens exact capability destinations from Workspace", async () => {
    window.history.replaceState(null, "", "/#/workspace");
    mockAuthenticatedRequests();
    renderApp();
    await screen.findByRole("heading", { name: "Storage conversations" });

    fireEvent.click(screen.getByRole("button", { name: /MCP Builder/ }));

    expect(await screen.findByRole("heading", { name: "Loaded Connectors builder" })).toBeVisible();
    expect(window.location.hash).toBe("#/connectors/builder");
  });

  it("loads direct Connector and approval routes through the operational boundary", async () => {
    window.history.replaceState(null, "", "/#/connectors");
    mockAuthenticatedRequests();
    const view = renderApp();
    expect(await screen.findByRole("heading", { name: "Loaded Connectors inventory" })).toBeVisible();

    view.unmount();
    window.history.replaceState(null, "", "/?approval_request_id=request.test#/workspace");
    renderApp();
    expect(await screen.findByRole("heading", { name: "Loaded Health investigate" })).toBeVisible();
  });

  it("fails an unknown hash back to Workspace", async () => {
    window.history.replaceState(null, "", "/#/unknown");
    mockAuthenticatedRequests();
    renderApp();

    expect(await screen.findByRole("heading", { name: "Storage conversations" })).toBeVisible();
    await waitFor(() => expect(window.location.hash).toBe("#/workspace"));
  });

  it("fails an unknown nested Health view back to Workspace", async () => {
    window.history.replaceState(null, "", "/#/health/unknown");
    mockAuthenticatedRequests();
    renderApp();

    expect(await screen.findByRole("heading", { name: "Storage conversations" })).toBeVisible();
    expect(window.location.hash).toBe("#/workspace");
    expect(operationalRender).not.toHaveBeenCalled();
  });

  it("fails an unknown nested Connector view back to Workspace", async () => {
    window.history.replaceState(null, "", "/#/connectors/unknown");
    mockAuthenticatedRequests();
    renderApp();

    expect(await screen.findByRole("heading", { name: "Storage conversations" })).toBeVisible();
    expect(window.location.hash).toBe("#/workspace");
    expect(operationalRender).not.toHaveBeenCalled();
  });

  it("loads the existing operational sign-in owner for an unauthenticated Workspace", async () => {
    window.history.replaceState(null, "", "/#/workspace");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 401 }));

    renderApp();

    expect(await screen.findByRole("heading", { name: "Loaded Health overview" })).toBeVisible();
    expect(window.location.hash).toBe("#/workspace");
  });

  it("synchronizes browser history changes without losing the canonical route", async () => {
    window.history.replaceState(null, "", "/#/workspace");
    mockAuthenticatedRequests();
    renderApp();
    await screen.findByRole("heading", { name: "Storage conversations" });

    window.history.pushState(null, "", "/#/health");
    window.dispatchEvent(new PopStateEvent("popstate"));
    expect(await screen.findByRole("heading", { name: "Loaded Health overview" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Open governance" }));
    expect(await screen.findByRole("heading", { name: "Loaded Health governance" })).toBeVisible();
    expect(window.location.hash).toBe("#/health/governance");

    window.history.pushState(null, "", "/#/connectors/runtime");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect(await screen.findByRole("heading", { name: "Loaded Connectors runtime" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Open connector knowledge" }));
    expect(await screen.findByRole("heading", { name: "Loaded Connectors knowledge" })).toBeVisible();
    expect(window.location.hash).toBe("#/connectors/knowledge");
  });

  it("keeps Workspace fail closed until identity verification is retried successfully", async () => {
    window.history.replaceState(null, "", "/#/workspace");
    let identityAttempts = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/identity/me")) {
        identityAttempts += 1;
        return Promise.resolve(
          identityAttempts === 1
            ? new Response(null, { status: 503 })
            : new Response(JSON.stringify(identity), { status: 200 }),
        );
      }
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    renderApp();

    expect(await screen.findByRole("alert")).toHaveTextContent("Identity could not be verified");
    expect(operationalRender).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Retry identity check" }));

    expect(await screen.findByRole("heading", { name: "Storage conversations" })).toBeVisible();
    expect(identityAttempts).toBe(2);
  });
});
