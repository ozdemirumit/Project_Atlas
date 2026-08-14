import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../../api/client";
import {
  appendOperationalConversationTurn,
  createOperationalConversation,
  getOperationalConversation,
  listOperationalConversations,
  type OperationalConversation,
  type ConversationArtifactReference,
  type ConversationEvidenceReference,
  type OperationalConversationSummary,
  type OperationalConversationTurn,
} from "../../api/conversations";
import OperationsConversationWorkspace from "./OperationsConversationWorkspace";

vi.mock("../../api/conversations", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/conversations")>();
  return {
    ...original,
    appendOperationalConversationTurn: vi.fn(),
    createOperationalConversation: vi.fn(),
    getOperationalConversation: vi.fn(),
    listOperationalConversations: vi.fn(),
  };
});

function turn(
  ordinal: number,
  role: "user" | "assistant",
  overrides: Partial<OperationalConversationTurn> = {},
): OperationalConversationTurn {
  return {
    schema_version: "atlas.operational-conversation-turn.v1",
    turn_id: `conversation-turn.test-${ordinal}`,
    ordinal,
    role,
    status: "completed",
    text: role === "user" ? "Why is latency elevated?" : "Pool pressure correlates with latency.",
    observed_at: `2026-08-13T10:0${ordinal}:00Z`,
    evidence_references:
      role === "assistant"
        ? [
            {
              evidence_id: "evidence.storage-latency",
              artifact_id: "investigation.storage-primary",
              artifact_version: "2",
              source_type: "storage_health_snapshot",
              source_reference: "snapshot://storage.primary/health/2026-08-13T10:00:00Z",
              observed_at: "2026-08-13T10:00:00Z",
              citation: "Pool utilization reached 91% in the observed window.",
            },
          ]
        : [],
    artifact_references:
      role === "assistant"
        ? [
            {
              artifact_id: "investigation.storage-primary",
              artifact_type: "investigation",
              version: 2,
            },
          ]
        : [],
    assumptions: role === "assistant" ? ["Workload placement was unchanged."] : [],
    unknowns: role === "assistant" ? ["Host queue depth is not available."] : [],
    confidence_basis:
      role === "assistant" ? "Moderate confidence from current authorized observations." : "",
    failure_code: null,
    safety_notice: "Decision support only. No infrastructure action is authorized.",
    canonical_digest: String(ordinal).repeat(64),
    ...overrides,
  };
}

function conversation(
  overrides: Partial<OperationalConversation> = {},
): OperationalConversation {
  const turns = overrides.turns ?? [turn(1, "user"), turn(2, "assistant")];
  return {
    schema_version: "atlas.operational-conversation.v1",
    conversation_id: "conversation.storage-primary",
    version: 2,
    organization_id: "organization.test",
    environment_id: "environment.test",
    site_id: "site.local",
    owner_subject_id: "subject.operator",
    target_id: "storage.primary",
    target_type: "storage",
    title: "Primary storage latency",
    lifecycle: "open",
    turn_count: turns.length,
    created_by: "subject.operator",
    created_at: "2026-08-13T10:00:00Z",
    updated_by: "subject.operator",
    updated_at: "2026-08-13T10:02:00Z",
    durable: true,
    canonical_digest: "a".repeat(64),
    turns,
    ...overrides,
  };
}

function summary(aggregate = conversation()): OperationalConversationSummary {
  return {
    schema_version: aggregate.schema_version,
    conversation_id: aggregate.conversation_id,
    version: aggregate.version,
    organization_id: aggregate.organization_id,
    environment_id: aggregate.environment_id,
    site_id: aggregate.site_id,
    owner_subject_id: aggregate.owner_subject_id,
    target_id: aggregate.target_id,
    target_type: aggregate.target_type,
    title: aggregate.title,
    lifecycle: aggregate.lifecycle,
    turn_count: aggregate.turn_count,
    created_by: aggregate.created_by,
    created_at: aggregate.created_at,
    updated_by: aggregate.updated_by,
    updated_at: aggregate.updated_at,
    durable: aggregate.durable,
    canonical_digest: aggregate.canonical_digest,
  };
}

function renderWorkspace(
  options: {
    governedSessionAvailable?: boolean;
    onRequestEnterpriseLogin?: () => void;
    onNavigateContext?: (input: {
      destination: "inventory" | "topology";
      targetId: string;
      conversationId: string | null;
    }) => void;
    onOpenEvidence?: (reference: ConversationEvidenceReference) => void;
    onOpenArtifact?: (reference: ConversationArtifactReference) => void;
  } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <OperationsConversationWorkspace
          organizationId="organization.test"
          environmentId="environment.test"
          siteId="site.local"
          ownerSubjectId="subject.operator"
          governedSessionAvailable={options.governedSessionAvailable}
          onRequestEnterpriseLogin={options.onRequestEnterpriseLogin}
          onNavigateContext={options.onNavigateContext}
          onOpenEvidence={options.onOpenEvidence}
          onOpenArtifact={options.onOpenArtifact}
        />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => {
  const aggregate = conversation();
  vi.mocked(listOperationalConversations).mockResolvedValue({
    conversations: [summary(aggregate)],
    authorizedTargets: [
      {
        targetId: "storage.primary",
        displayName: "Primary VSP",
        description: "Production storage array",
      },
      { targetId: "storage.secondary", displayName: "Secondary VSP" },
    ],
    durable: true,
    truncated: false,
  });
  vi.mocked(getOperationalConversation).mockResolvedValue(aggregate);
  vi.mocked(createOperationalConversation).mockResolvedValue(
    conversation({ version: 1, turn_count: 0, turns: [] }),
  );
  vi.mocked(appendOperationalConversationTurn).mockResolvedValue(
    conversation({
      version: 3,
      canonical_digest: "b".repeat(64),
      turns: [
        turn(1, "user"),
        turn(2, "assistant"),
        turn(3, "user", { text: "What is the safest next check?" }),
        turn(4, "assistant", { text: "Collect a read-only host queue-depth observation." }),
      ],
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("OperationsConversationWorkspace", () => {
  it("lists and reopens durable scoped conversations with ordered grounded detail", async () => {
    const onOpenEvidence = vi.fn();
    const onOpenArtifact = vi.fn();
    renderWorkspace({ onOpenEvidence, onOpenArtifact });

    expect(await screen.findByText("Durable store")).toBeVisible();
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));

    expect(await screen.findByRole("heading", { name: "Primary storage latency" })).toBeVisible();
    const turns = await screen.findAllByRole("article");
    expect(turns).toHaveLength(2);
    expect(turns[0]).toHaveAttribute("aria-label", "Operator turn 1");
    expect(turns[1]).toHaveAttribute("aria-label", "Atlas turn 2");
    expect(screen.getByText("Moderate confidence from current authorized observations.")).toBeVisible();
    expect(screen.getByText("Workload placement was unchanged.")).toBeVisible();
    expect(screen.getByText("Host queue depth is not available.")).toBeVisible();
    expect(screen.getByText("Pool utilization reached 91% in the observed window.")).toBeVisible();
    expect(
      screen.getByText("snapshot://storage.primary/health/2026-08-13T10:00:00Z"),
    ).toBeVisible();
    expect(screen.getAllByText(/No infrastructure action is authorized/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Open evidence evidence.storage-latency" }));
    expect(onOpenEvidence).toHaveBeenCalledWith(
      expect.objectContaining({ evidence_id: "evidence.storage-latency" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /investigation v2/i }));
    expect(onOpenArtifact).toHaveBeenCalledWith(
      expect.objectContaining({ artifact_id: "investigation.storage-primary" }),
    );
  });

  it("creates a conversation only from an authorized target and exposes the safety boundary", async () => {
    renderWorkspace();
    const trigger = await screen.findByRole("button", { name: "New conversation" });
    await waitFor(() => expect(trigger).toBeEnabled());
    fireEvent.click(trigger);

    expect(screen.getByRole("dialog", { name: "New storage conversation" })).toBeVisible();
    expect(screen.getByText(/cannot execute infrastructure actions/i)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Authorized storage target"), {
      target: { value: "storage.secondary" },
    });
    fireEvent.change(screen.getByLabelText("Conversation title"), {
      target: { value: "Secondary path review" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create conversation" }));

    await waitFor(() => expect(createOperationalConversation).toHaveBeenCalledTimes(1));
    expect(createOperationalConversation).toHaveBeenCalledWith(
      expect.objectContaining({ targetId: "storage.secondary", title: "Secondary path review" }),
    );
    expect(vi.mocked(createOperationalConversation).mock.calls[0]?.[0].context).toEqual({
      organizationId: "organization.test",
      environmentId: "environment.test",
      siteId: "site.local",
      ownerSubjectId: "subject.operator",
      authorizedTargetIds: ["storage.primary", "storage.secondary"],
    });
  });

  it("authorizes no create target until the scoped list response arrives", async () => {
    let resolveList: ((value: Awaited<ReturnType<typeof listOperationalConversations>>) => void) | undefined;
    vi.mocked(listOperationalConversations).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );
    renderWorkspace();

    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    resolveList?.({
      conversations: [summary()],
      authorizedTargets: [{ targetId: "storage.primary", displayName: "Primary VSP" }],
      durable: true,
      truncated: false,
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "New conversation" })).toBeEnabled(),
    );
  });

  it("keys conversation detail by the canonical server-authorized target set", async () => {
    const { client } = renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    await screen.findByRole("heading", { name: "Primary storage latency" });

    expect(
      client
        .getQueryCache()
        .findAll({ queryKey: ["operational-conversation"] })
        .map((query) => query.queryKey),
    ).toContainEqual([
      "operational-conversation",
      "organization.test",
      "environment.test",
      "site.local",
      "subject.operator",
      "storage.primary|storage.secondary",
      "conversation.storage-primary",
    ]);
  });

  it("keeps the create dialog keyboard-bounded and restores trigger focus", async () => {
    renderWorkspace();
    const trigger = await screen.findByRole("button", { name: "New conversation" });
    await waitFor(() => expect(trigger).toBeEnabled());
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "New storage conversation" });
    const target = screen.getByLabelText("Authorized storage target");
    await waitFor(() => expect(target).toHaveFocus());
    fireEvent.change(screen.getByLabelText("Conversation title"), {
      target: { value: "Keyboard review" },
    });

    const close = screen.getByRole("button", { name: "Close new conversation" });
    const create = screen.getByRole("button", { name: "Create conversation" });
    close.focus();
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(create).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("appends a question against the exact currently loaded version and renders the returned turn", async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    const composer = await screen.findByLabelText("Infrastructure question");
    expect(composer).toHaveAttribute("maxlength", "700");
    fireEvent.change(composer, { target: { value: "What is the safest next check?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send infrastructure question" }));

    await waitFor(() => expect(appendOperationalConversationTurn).toHaveBeenCalledTimes(1));
    const appendInput = vi.mocked(appendOperationalConversationTurn).mock.calls[0]?.[0];
    expect(appendInput?.conversation.version).toBe(2);
    expect(appendInput?.question).toBe("What is the safest next check?");
    expect(
      await screen.findByText("Collect a read-only host queue-depth observation."),
    ).toBeVisible();
    expect(composer).toHaveValue("");
  });

  it("distinguishes partial and failed outcomes without fabricating success", async () => {
    const aggregate = conversation({
      version: 3,
      turns: [
        turn(1, "user"),
        turn(2, "assistant", { status: "partial" }),
        turn(3, "assistant", {
          status: "failed",
          text: "A grounded answer could not be produced.",
          failure_code: "model.unavailable",
          evidence_references: [],
          artifact_references: [],
          assumptions: [],
          unknowns: ["Current model output is unavailable."],
          confidence_basis: "No confidence can be assigned.",
        }),
      ],
    });
    vi.mocked(listOperationalConversations).mockResolvedValue({
      conversations: [summary(aggregate)],
      authorizedTargets: [
        { targetId: "storage.primary", displayName: "Primary VSP" },
        { targetId: "storage.secondary", displayName: "Secondary VSP" },
      ],
      durable: true,
      truncated: false,
    });
    vi.mocked(getOperationalConversation).mockResolvedValue(aggregate);
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));

    expect(await screen.findByText(/supports only a partial answer/i)).toBeVisible();
    expect(screen.getByText(/Generation failed safely \(model.unavailable\)/i)).toBeVisible();
    expect(screen.getByText("Current model output is unavailable.")).toBeVisible();
  });

  it("renders provenance without dead evidence or artifact controls", async () => {
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    await screen.findByRole("heading", { name: "Primary storage latency" });

    expect(
      screen.queryByRole("button", { name: "Open evidence evidence.storage-latency" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /investigation v2/i })).not.toBeInTheDocument();
    expect(screen.getByText("investigation v2")).toBeVisible();
  });

  it("keeps development access read-only and offers governed sign-in", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    renderWorkspace({ governedSessionAvailable: false, onRequestEnterpriseLogin });

    expect(await screen.findByText(/username and password/i)).toBeVisible();
    expect(screen.queryByText(/authorized browser session|MFA|second login/i)).toBeNull();
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledTimes(1);

    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    expect(await screen.findByLabelText("Infrastructure question")).toBeDisabled();
  });

  it("treats list authorization loss as expired access and disables mutations", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(listOperationalConversations).mockRejectedValue(
      new ApiRequestError("session expired", 401),
    );
    renderWorkspace({ onRequestEnterpriseLogin });

    expect(await screen.findByText(/can no longer access this conversation workspace/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
    expect(onRequestEnterpriseLogin).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Conversations are unavailable.")).not.toBeInTheDocument();
  });

  it("treats detail authorization loss as expired access and disables all mutations", async () => {
    const onRequestEnterpriseLogin = vi.fn();
    vi.mocked(getOperationalConversation).mockRejectedValue(
      new ApiRequestError("scope revoked", 403),
    );
    renderWorkspace({ onRequestEnterpriseLogin });
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));

    expect(await screen.findByText(/can no longer access this conversation workspace/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    expect(screen.queryByText("Conversation could not be reopened.")).not.toBeInTheDocument();
  });

  it("shows a scoped empty state and inventory navigation when no target is authorized", async () => {
    const onNavigateContext = vi.fn();
    vi.mocked(listOperationalConversations).mockResolvedValue({
      conversations: [],
      authorizedTargets: [],
      durable: true,
      truncated: false,
    });
    renderWorkspace({ onNavigateContext });

    expect(await screen.findByText("No conversations yet")).toBeVisible();
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    expect(screen.getByText(/No authorized storage target/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Open inventory" }));
    expect(onNavigateContext).toHaveBeenCalledWith({
      destination: "inventory",
      targetId: "",
      conversationId: null,
    });
  });

  it("offers explicit list and detail retries", async () => {
    vi.mocked(listOperationalConversations)
      .mockRejectedValueOnce(new Error("list unavailable"))
      .mockResolvedValueOnce({
        conversations: [summary()],
        authorizedTargets: [
          { targetId: "storage.primary", displayName: "Primary VSP" },
          { targetId: "storage.secondary", displayName: "Secondary VSP" },
        ],
        durable: true,
        truncated: false,
      });
    vi.mocked(getOperationalConversation)
      .mockRejectedValueOnce(new Error("detail unavailable"))
      .mockResolvedValueOnce(conversation());
    renderWorkspace();

    expect(await screen.findByText("Conversations are unavailable.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    expect(await screen.findByText("Conversation could not be reopened.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: "Primary storage latency" })).toBeVisible();
  });

  it("fails visibly on a stale version and refreshes before another append", async () => {
    vi.mocked(appendOperationalConversationTurn).mockRejectedValue(
      new ApiRequestError("stale version", 409),
    );
    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    fireEvent.change(await screen.findByLabelText("Infrastructure question"), {
      target: { value: "What is the safest next check?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send infrastructure question" }));

    expect(await screen.findByText(/changed before this question was appended/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Refresh conversation" }));
    await waitFor(() => expect(getOperationalConversation).toHaveBeenCalledTimes(2));
  });

  it("preserves conversation context in inventory and topology navigation callbacks", async () => {
    const onNavigateContext = vi.fn();
    renderWorkspace({ onNavigateContext });
    fireEvent.click(await screen.findByRole("button", { name: "Reopen Primary storage latency" }));
    await screen.findByRole("heading", { name: "Primary storage latency" });

    fireEvent.click(screen.getByRole("button", { name: "Inventory" }));
    fireEvent.click(screen.getByRole("button", { name: "Topology" }));
    expect(onNavigateContext).toHaveBeenNthCalledWith(1, {
      destination: "inventory",
      targetId: "storage.primary",
      conversationId: "conversation.storage-primary",
    });
    expect(onNavigateContext).toHaveBeenNthCalledWith(2, {
      destination: "topology",
      targetId: "storage.primary",
      conversationId: "conversation.storage-primary",
    });
  });
});
