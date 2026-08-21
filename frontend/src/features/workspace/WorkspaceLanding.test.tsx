import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentIdentity } from "../../api/identity";
import {
  getOperationalConversation,
  listOperationalConversations,
  type OperationalConversation,
  type OperationalConversationSummary,
} from "../../api/conversations";
import { WorkspaceLanding } from "./WorkspaceLanding";

vi.mock("../../api/conversations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/conversations")>();
  return {
    ...original,
    getOperationalConversation: vi.fn(),
    listOperationalConversations: vi.fn(),
  };
});

const identity: CurrentIdentity = {
  subject_id: "subject.operator",
  display_name: "Atlas Operator",
  subject_kind: "human",
  organization_id: "organization.test",
  credential_kind: "browser_session",
  role_ids: ["role.operator"],
  group_ids: [],
  authentication: {
    provider_id: "provider.oidc",
    method: "oidc",
    assurance_level: "aal2",
    authenticated_at: "2026-08-10T00:00:00Z",
  },
  scope: {
    organization_id: "organization.test",
    environment_id: "environment.test",
    site_id: "site.test",
    domain_id: "domain.test",
    resource_id: "resource.test",
    capability_class: "C0",
  },
  authorization_decision_id: "decision.test",
  effective_role_versions: ["role.operator:v1"],
  effective_assignment_versions: ["assignment.operator:v1"],
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
  meta: { correlation_id: "correlation.test", generated_at: "2026-08-10T00:00:00Z" },
};

const conversation: OperationalConversation = {
  schema_version: "atlas.operational-conversation.v1",
  conversation_id: "conversation.server-authorized",
  version: 1,
  organization_id: "organization.test",
  environment_id: "environment.test",
  site_id: "site.test",
  owner_subject_id: "subject.operator",
  target_id: "storage.server-authorized",
  target_type: "storage",
  title: "Server-authorized investigation",
  lifecycle: "open",
  turn_count: 0,
  created_by: "subject.operator",
  created_at: "2026-08-13T10:00:00Z",
  updated_by: "subject.operator",
  updated_at: "2026-08-13T10:00:00Z",
  durable: true,
  canonical_digest: "a".repeat(64),
  turns: [],
};

function conversationSummary(): OperationalConversationSummary {
  const { turns, ...summary } = conversation;
  void turns;
  return summary;
}

function renderLanding(onNavigateCapability = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <WorkspaceLanding
        activeView="home"
        identity={identity}
        onNavigate={() => undefined}
        onNavigateCapability={onNavigateCapability}
        onNavigateView={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("WorkspaceLanding", () => {
  beforeEach(() => {
    vi.mocked(listOperationalConversations).mockResolvedValue({
      conversations: [],
      authorizedTargets: [
        {
          targetId: "storage.server-authorized",
          displayName: "Server-authorized storage",
          description: "Returned by the scoped conversation inventory.",
        },
      ],
      durable: true,
      truncated: false,
    });
    vi.mocked(getOperationalConversation).mockResolvedValue(conversation);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("uses the existing current-session endpoint for sign-out", async () => {
    const requests: Array<{ method: string; url: string }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      requests.push({ method: init?.method ?? "GET", url });
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 204 }));
    });
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() =>
      expect(requests).toContainEqual({
        method: "DELETE",
        url: "/api/v1/authentication/sessions/current",
      }),
    );
  });

  it("keeps the current session authoritative when sign-out fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 503 }));
    });
    renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(
      await screen.findByText(/Your current session remains authoritative/),
    ).toBeVisible();
  });

  it("blocks the workspace when the advisory-only contract is violated", async () => {
    const unsafePlatform = {
      ...platform,
      data: {
        ...platform.data,
        operational_posture: {
          ...platform.data.operational_posture,
          operational_execution_enabled: true,
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(unsafePlatform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 204 }));
    });

    renderLanding();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Advisory boundary unavailable");
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("uses only server-returned storage authorization in the conversation workspace", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/platform/status")) {
        return Promise.resolve(new Response(JSON.stringify(platform), { status: 200 }));
      }
      return Promise.resolve(new Response(null, { status: 204 }));
    });
    renderLanding();

    const trigger = await screen.findByRole("button", { name: "New conversation" });
    await waitFor(() => expect(trigger).toBeEnabled());
    fireEvent.click(trigger);
    expect(screen.getByRole("option", { name: "Server-authorized storage" })).toBeVisible();
    expect(screen.queryByText("VSP G400 Lab")).not.toBeInTheDocument();
    expect(screen.queryByText("VSP One B28 Lab")).not.toBeInTheDocument();
  });

  it("preserves target and conversation URL context while routing to safe existing views", async () => {
    const onNavigateCapability = vi.fn();
    vi.mocked(listOperationalConversations).mockResolvedValue({
      conversations: [
        conversationSummary(),
      ],
      authorizedTargets: [
        { targetId: "storage.server-authorized", displayName: "Server-authorized storage" },
      ],
      durable: true,
      truncated: false,
    });
    renderLanding(onNavigateCapability);
    fireEvent.click(
      await screen.findByRole("button", { name: "Reopen Server-authorized investigation" }),
    );
    await screen.findByRole("heading", { name: "Server-authorized investigation" });

    fireEvent.click(screen.getByRole("button", { name: "Inventory" }));
    expect(new URLSearchParams(window.location.search).get("target_id")).toBe(
      "storage.server-authorized",
    );
    expect(new URLSearchParams(window.location.search).get("conversation_id")).toBe(
      "conversation.server-authorized",
    );
    expect(onNavigateCapability).toHaveBeenLastCalledWith({
      workspace: "Connectors",
      view: "inventory",
    });

    fireEvent.click(screen.getByRole("button", { name: "Topology" }));
    expect(onNavigateCapability).toHaveBeenLastCalledWith({
      workspace: "Health",
      view: "overview",
    });
    expect(window.location.search).toContain("target_id=storage.server-authorized");
    expect(window.location.search).toContain("conversation_id=conversation.server-authorized");
  });
});
