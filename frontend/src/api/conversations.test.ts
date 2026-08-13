import { afterEach, describe, expect, it, vi } from "vitest";

import {
  appendOperationalConversationTurn,
  createOperationalConversation,
  getOperationalConversation,
  listOperationalConversations,
  type ConversationAccessContext,
  type OperationalConversation,
  type OperationalConversationSummary,
  type OperationalConversationTurn,
} from "./conversations";

const context: ConversationAccessContext = {
  organizationId: "organization.test",
  environmentId: "environment.test",
  siteId: "site.local",
  ownerSubjectId: "subject.operator",
  authorizedTargetIds: ["storage.primary"],
};

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
    text: role === "user" ? "Why is latency elevated?" : "Latency is correlated with pool pressure.",
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
              citation: "Pool utilization reached 91% during the observed window.",
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
      role === "assistant" ? "Moderate confidence from two current authorized observations." : "",
    failure_code: null,
    safety_notice: "Decision support only. No infrastructure action is authorized.",
    canonical_digest: String(ordinal).repeat(64),
    ...overrides,
  };
}

function conversation(
  overrides: Partial<OperationalConversation> = {},
): OperationalConversation {
  const turns = overrides.turns ?? [];
  return {
    schema_version: "atlas.operational-conversation.v1",
    conversation_id: "conversation.storage-primary",
    version: 1,
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
    updated_at: "2026-08-13T10:00:00Z",
    durable: true,
    canonical_digest: "a".repeat(64),
    turns,
    ...overrides,
  };
}

function summary(overrides: Partial<OperationalConversationSummary> = {}) {
  const aggregate = conversation();
  const record: OperationalConversationSummary = {
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
  return { ...record, ...overrides };
}

function response(data: unknown, status = 200): Response {
  return new Response(
    JSON.stringify({
      data,
      meta: {
        correlation_id: "correlation.test",
        generated_at: "2026-08-13T10:10:00Z",
      },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

const authorizedTargets = [
  {
    target_id: "storage.primary",
    display_name: "Primary VSP",
    description: "Production storage array",
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("operational conversation API client", () => {
  it("lists only exact owner, scope, target, and persistence-bound summaries", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        conversations: [summary()],
        authorized_targets: authorizedTargets,
        durable: true,
        truncated: false,
      }),
    );

    await expect(listOperationalConversations(context)).resolves.toEqual({
      conversations: [summary()],
      authorizedTargets: [
        {
          targetId: "storage.primary",
          displayName: "Primary VSP",
          description: "Production storage array",
        },
      ],
      durable: true,
      truncated: false,
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/conversations?limit=50");
  });

  it("fails closed on foreign scope, unauthorized targets, persistence mismatch, or extra fields", async () => {
    for (const unsafe of [
      summary({ organization_id: "organization.foreign" }),
      summary({ target_id: "storage.unauthorized" }),
      { ...summary(), credential: "must-not-render" },
    ]) {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        response({
          conversations: [unsafe],
          authorized_targets: authorizedTargets,
          durable: true,
          truncated: false,
        }),
      );
      await expect(listOperationalConversations(context)).rejects.toMatchObject({ status: 200 });
    }

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        conversations: [summary({ durable: false })],
        authorized_targets: authorizedTargets,
        durable: true,
        truncated: false,
      }),
    );
    await expect(listOperationalConversations(context)).rejects.toMatchObject({ status: 200 });
  });

  it("accepts only exact server-authorized targets and rejects ambiguous target grants", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        conversations: [summary()],
        authorized_targets: authorizedTargets,
        durable: true,
        truncated: false,
      }),
    );
    await expect(listOperationalConversations(context)).resolves.toMatchObject({
      authorizedTargets: [{ targetId: "storage.primary", displayName: "Primary VSP" }],
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({
        conversations: [summary()],
        authorized_targets: [...authorizedTargets, ...authorizedTargets],
        durable: true,
        truncated: false,
      }),
    );
    await expect(listOperationalConversations(context)).rejects.toMatchObject({ status: 200 });
  });

  it("accepts 240-character identifiers and the full bounded confidence representation", async () => {
    const identifier = `a${"b".repeat(239)}`;
    const aggregate = conversation({
      conversation_id: identifier,
      version: 2,
      turn_count: 2,
      turns: [turn(1, "user"), turn(2, "assistant", { confidence_basis: "c".repeat(10_019) })],
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(aggregate));

    await expect(
      getOperationalConversation({ conversationId: identifier, context }),
    ).resolves.toEqual(aggregate);
  });

  it("retrieves the exact requested aggregate and rejects unordered or mismatched turns", async () => {
    const aggregate = conversation({
      version: 2,
      turns: [turn(1, "user"), turn(2, "assistant")],
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(aggregate));

    await expect(
      getOperationalConversation({
        conversationId: "conversation.storage-primary",
        context,
      }),
    ).resolves.toEqual(aggregate);

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({ ...aggregate, conversation_id: "conversation.other" }),
    );
    await expect(
      getOperationalConversation({
        conversationId: "conversation.storage-primary",
        context,
      }),
    ).rejects.toMatchObject({ status: 200 });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response({ ...aggregate, turns: [turn(2, "user"), turn(1, "assistant")] }),
    );
    await expect(
      getOperationalConversation({
        conversationId: "conversation.storage-primary",
        context,
      }),
    ).rejects.toMatchObject({ status: 200 });
  });

  it("creates a target-bound empty conversation without caller-shaped evidence or authority", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(conversation(), 201));

    await createOperationalConversation({
      context,
      targetId: "storage.primary",
      title: " Primary storage latency ",
      idempotencyKey: "conversation-create.test",
    });

    const request = fetchMock.mock.calls[0]?.[1];
    expect(request?.method).toBe("POST");
    expect(new Headers(request?.headers).get("Idempotency-Key")).toBe("conversation-create.test");
    if (typeof request?.body !== "string") throw new Error("Expected a JSON request body");
    const body = JSON.parse(request.body) as Record<string, unknown>;
    expect(body).toEqual({
      schema_version: "atlas.operational-conversation-create.v1",
      target_id: "storage.primary",
      target_type: "storage",
      title: "Primary storage latency",
      acknowledged_decision_support_only: true,
    });
    for (const forbidden of [
      "evidence_references",
      "confidence_basis",
      "artifact_references",
      "execution_authorized",
      "credential",
    ]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });

  it("rejects locally unauthorized targets and create responses that are not request-bound", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    await expect(
      createOperationalConversation({
        context,
        targetId: "storage.unauthorized",
        title: "Unauthorized conversation",
      }),
    ).rejects.toMatchObject({ status: 403 });
    expect(fetchMock).not.toHaveBeenCalled();

    fetchMock.mockResolvedValueOnce(
      response(conversation({ title: "Server-selected different title" }), 201),
    );
    await expect(
      createOperationalConversation({
        context,
        targetId: "storage.primary",
        title: "Primary storage latency",
      }),
    ).rejects.toMatchObject({ status: 201 });
  });

  it("appends one version-bound user and assistant turn with idempotency", async () => {
    const before = conversation();
    const after = conversation({
      version: 2,
      turn_count: 2,
      updated_at: "2026-08-13T10:02:00Z",
      canonical_digest: "b".repeat(64),
      turns: [turn(1, "user"), turn(2, "assistant")],
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(after));

    await expect(
      appendOperationalConversationTurn({
        context,
        conversation: before,
        question: " Why is latency elevated? ",
        idempotencyKey: "conversation-turn.test",
      }),
    ).resolves.toEqual(after);

    const request = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(request?.headers).get("Idempotency-Key")).toBe("conversation-turn.test");
    if (typeof request?.body !== "string") throw new Error("Expected a JSON request body");
    expect(JSON.parse(request.body)).toEqual({
      schema_version: "atlas.operational-conversation-turn-append.v1",
      expected_version: 1,
      question: "Why is latency elevated?",
      acknowledged_decision_support_only: true,
    });
  });

  it("rejects questions beyond the 700-character retrieval-safe boundary before transport", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    await expect(
      appendOperationalConversationTurn({
        context,
        conversation: conversation(),
        question: "q".repeat(701),
      }),
    ).rejects.toMatchObject({ status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects stale, replaced, or malformed assistant outcomes", async () => {
    const before = conversation();
    const validTurns = [turn(1, "user"), turn(2, "assistant")];
    for (const unsafe of [
      conversation({ version: 1, turn_count: 2, turns: validTurns }),
      conversation({
        version: 2,
        turn_count: 2,
        turns: [turn(1, "user", { text: "A different question" }), turn(2, "assistant")],
      }),
      conversation({
        version: 2,
        turn_count: 2,
        turns: [
          turn(1, "user"),
          turn(2, "assistant", { status: "failed", failure_code: null }),
        ],
      }),
    ]) {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response(unsafe));
      await expect(
        appendOperationalConversationTurn({
          context,
          conversation: before,
          question: "Why is latency elevated?",
        }),
      ).rejects.toMatchObject({ status: 200 });
    }
  });
});
