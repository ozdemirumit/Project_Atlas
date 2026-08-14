import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  ExternalLink,
  FileSearch,
  LogIn,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Server,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent,
  type MouseEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { ApiRequestError } from "../../api/client";
import {
  appendOperationalConversationTurn,
  createOperationalConversation,
  getOperationalConversation,
  listOperationalConversations,
  type AuthorizedStorageTarget,
  type ConversationAccessContext,
  type ConversationArtifactReference,
  type ConversationEvidenceReference,
  type OperationalConversation,
  type OperationalConversationTurn,
} from "../../api/conversations";
import "./OperationsConversationWorkspace.css";

export type ConversationContextDestination = "inventory" | "topology";

export interface OperationsConversationWorkspaceProps {
  organizationId: string;
  environmentId: string;
  siteId: string;
  ownerSubjectId: string;
  governedSessionAvailable?: boolean;
  onRequestEnterpriseLogin?: () => void;
  onNavigateContext?: (input: {
    destination: ConversationContextDestination;
    targetId: string;
    conversationId: string | null;
  }) => void;
  onOpenEvidence?: (reference: ConversationEvidenceReference) => void;
  onOpenArtifact?: (reference: ConversationArtifactReference) => void;
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function targetLabel(targets: AuthorizedStorageTarget[], targetId: string): string {
  return targets.find((target) => target.targetId === targetId)?.displayName ?? targetId;
}

function ConversationCreatePanel({
  targets,
  pending,
  returnFocusTo,
  onCancel,
  onSubmit,
}: {
  targets: AuthorizedStorageTarget[];
  pending: boolean;
  returnFocusTo: HTMLElement | null;
  onCancel: () => void;
  onSubmit: (input: { targetId: string; title: string }) => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [targetId, setTargetId] = useState(targets[0]?.targetId ?? "");
  const [title, setTitle] = useState("");
  const valid = targets.some((target) => target.targetId === targetId) && title.trim().length >= 3;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !pending) onSubmit({ targetId, title: title.trim() });
  }

  useEffect(() => {
    const dialog = dialogRef.current;
    const firstControl =
      dialog?.querySelector<HTMLElement>("select:not([disabled])") ??
      dialog?.querySelector<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
    );
    firstControl?.focus();
    return () => returnFocusTo?.focus();
  }, [returnFocusTo]);

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
      ),
    );
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return (
    <div
      ref={dialogRef}
      className="operations-conversation-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-conversation-title"
      onKeyDown={handleDialogKeyDown}
    >
      <form onSubmit={submit}>
        <div className="operations-conversation-dialog-heading">
          <div>
            <p className="eyebrow">DURABLE INVESTIGATION CONTEXT</p>
            <h3 id="create-conversation-title">New storage conversation</h3>
          </div>
          <button
            className="operations-conversation-icon-button"
            type="button"
            aria-label="Close new conversation"
            onClick={onCancel}
          >
            <X size={17} />
          </button>
        </div>
        <label>
          Authorized storage target
          <select
            autoFocus
            required
            value={targetId}
            onChange={(event) => setTargetId(event.target.value)}
          >
            {targets.map((target) => (
              <option key={target.targetId} value={target.targetId}>
                {target.displayName}
              </option>
            ))}
          </select>
        </label>
        {targets.find((target) => target.targetId === targetId)?.description && (
          <p className="operations-conversation-target-description">
            {targets.find((target) => target.targetId === targetId)?.description}
          </p>
        )}
        <label>
          Conversation title
          <input
            required
            minLength={3}
            maxLength={120}
            value={title}
            placeholder="Primary storage latency review"
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <div className="operations-conversation-dialog-boundary">
          <ShieldCheck size={17} />
          <span>This conversation is decision support only and cannot execute infrastructure actions.</span>
        </div>
        <div className="operations-conversation-dialog-actions">
          <button type="button" disabled={pending} onClick={onCancel}>
            Cancel
          </button>
          <button className="operations-conversation-primary" type="submit" disabled={!valid || pending}>
            {pending ? <Clock3 size={15} /> : <Plus size={15} />} Create conversation
          </button>
        </div>
      </form>
    </div>
  );
}

function TurnReferenceList({
  turn,
  onOpenEvidence,
  onOpenArtifact,
}: {
  turn: OperationalConversationTurn;
  onOpenEvidence?: (reference: ConversationEvidenceReference) => void;
  onOpenArtifact?: (reference: ConversationArtifactReference) => void;
}) {
  if (turn.evidence_references.length === 0 && turn.artifact_references.length === 0) return null;
  return (
    <div className="operations-conversation-references">
      {turn.evidence_references.length > 0 && (
        <section aria-label={`Evidence for turn ${turn.ordinal}`}>
          <h4>Grounded evidence</h4>
          <ul>
            {turn.evidence_references.map((reference) => (
              <li key={`${reference.evidence_id}.${reference.artifact_version}`}>
                <FileSearch size={15} />
                <div>
                  <strong>{reference.citation}</strong>
                  <span>{reference.source_reference}</span>
                  <span>
                    {reference.source_type} | observed {formatTimestamp(reference.observed_at)}
                  </span>
                </div>
                {onOpenEvidence && (
                  <button
                    type="button"
                    aria-label={`Open evidence ${reference.evidence_id}`}
                    onClick={() => onOpenEvidence(reference)}
                  >
                    <ExternalLink size={14} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {turn.artifact_references.length > 0 && (
        <section aria-label={`Artifacts for turn ${turn.ordinal}`}>
          <h4>Related artifacts</h4>
          <div className="operations-conversation-artifacts">
            {turn.artifact_references.map((reference) => (
              onOpenArtifact ? (
                <button
                  key={`${reference.artifact_id}.${reference.version}`}
                  type="button"
                  onClick={() => onOpenArtifact(reference)}
                >
                  <FileSearch size={14} /> {reference.artifact_type} v{reference.version}
                </button>
              ) : (
                <span key={`${reference.artifact_id}.${reference.version}`}>
                  <FileSearch size={14} /> {reference.artifact_type} v{reference.version}
                </span>
              )
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ConversationTurn({
  turn,
  onOpenEvidence,
  onOpenArtifact,
}: {
  turn: OperationalConversationTurn;
  onOpenEvidence?: (reference: ConversationEvidenceReference) => void;
  onOpenArtifact?: (reference: ConversationArtifactReference) => void;
}) {
  const assistant = turn.role === "assistant";
  return (
    <article
      className={`operations-conversation-turn ${turn.role} ${turn.status}`}
      aria-label={`${assistant ? "Atlas" : "Operator"} turn ${turn.ordinal}`}
    >
      <header>
        <span className="operations-conversation-turn-author">
          {assistant ? <Bot size={17} /> : <UserRound size={17} />}
          {assistant ? "Atlas" : "Operator"}
        </span>
        <span className={`operations-conversation-status ${turn.status}`}>
          {turn.status === "completed" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
          {turn.status}
        </span>
        <time dateTime={turn.observed_at}>{formatTimestamp(turn.observed_at)}</time>
      </header>
      {turn.status === "partial" && (
        <div className="operations-conversation-outcome-warning" role="status">
          <AlertTriangle size={16} /> The available evidence supports only a partial answer.
        </div>
      )}
      {turn.status === "failed" && (
        <div className="operations-conversation-outcome-warning failed" role="alert">
          <AlertTriangle size={16} /> Generation failed safely ({turn.failure_code}). No conclusion was produced.
        </div>
      )}
      <p className="operations-conversation-turn-text">{turn.text}</p>
      {assistant && turn.confidence_basis && (
        <div className="operations-conversation-confidence">
          <strong>Confidence basis</strong>
          <span>{turn.confidence_basis}</span>
        </div>
      )}
      {turn.assumptions.length > 0 && (
        <section className="operations-conversation-epistemic">
          <h4>Assumptions</h4>
          <ul>{turn.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}
      {turn.unknowns.length > 0 && (
        <section className="operations-conversation-epistemic unknowns">
          <h4>Unknowns</h4>
          <ul>{turn.unknowns.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}
      <TurnReferenceList
        turn={turn}
        onOpenEvidence={onOpenEvidence}
        onOpenArtifact={onOpenArtifact}
      />
      <footer>
        <ShieldCheck size={14} />
        <span>{turn.safety_notice}</span>
      </footer>
    </article>
  );
}

export default function OperationsConversationWorkspace({
  organizationId,
  environmentId,
  siteId,
  ownerSubjectId,
  governedSessionAvailable = true,
  onRequestEnterpriseLogin,
  onNavigateContext,
  onOpenEvidence,
  onOpenArtifact,
}: OperationsConversationWorkspaceProps) {
  const queryClient = useQueryClient();
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [question, setQuestion] = useState("");
  const [createTrigger, setCreateTrigger] = useState<HTMLElement | null>(null);
  const scope = useMemo(
    () => ({
      organizationId,
      environmentId,
      siteId,
      ownerSubjectId,
    }),
    [organizationId, environmentId, siteId, ownerSubjectId],
  );
  const listKey = [
    "operational-conversations",
    organizationId,
    environmentId,
    siteId,
    ownerSubjectId,
  ] as const;
  const listQuery = useQuery({
    queryKey: listKey,
    queryFn: () => listOperationalConversations(scope),
    retry: false,
  });
  const listAccessExpired =
    listQuery.error instanceof ApiRequestError &&
    (listQuery.error.status === 401 || listQuery.error.status === 403);
  const authorizedStorageTargets = useMemo(
    () => (listAccessExpired ? [] : (listQuery.data?.authorizedTargets ?? [])),
    [listAccessExpired, listQuery.data?.authorizedTargets],
  );
  const authorizedTargetIds = useMemo(
    () => authorizedStorageTargets.map((target) => target.targetId).sort(),
    [authorizedStorageTargets],
  );
  const targetKey = authorizedTargetIds.join("|");
  const context = useMemo<ConversationAccessContext>(
    () => ({ ...scope, authorizedTargetIds }),
    [scope, authorizedTargetIds],
  );
  const detailKey = [
    "operational-conversation",
    organizationId,
    environmentId,
    siteId,
    ownerSubjectId,
    targetKey,
    selectedConversationId,
  ] as const;
  const detailQuery = useQuery({
    queryKey: detailKey,
    queryFn: () =>
      getOperationalConversation({ conversationId: selectedConversationId ?? "", context }),
    enabled: selectedConversationId !== null,
    retry: false,
  });
  const createMutation = useMutation({
    mutationFn: ({ targetId, title }: { targetId: string; title: string }) =>
      createOperationalConversation({ context, targetId, title }),
    onSuccess: async (conversation) => {
      queryClient.setQueryData(
        [
          "operational-conversation",
          organizationId,
          environmentId,
          siteId,
          ownerSubjectId,
          targetKey,
          conversation.conversation_id,
        ],
        conversation,
      );
      setSelectedConversationId(conversation.conversation_id);
      setCreating(false);
      await queryClient.invalidateQueries({ queryKey: listKey, exact: true });
    },
  });
  const appendMutation = useMutation({
    mutationFn: ({ conversation, prompt }: { conversation: OperationalConversation; prompt: string }) =>
      appendOperationalConversationTurn({ context, conversation, question: prompt }),
    onSuccess: async (conversation) => {
      queryClient.setQueryData(
        [
          "operational-conversation",
          organizationId,
          environmentId,
          siteId,
          ownerSubjectId,
          targetKey,
          conversation.conversation_id,
        ],
        conversation,
      );
      setQuestion("");
      await queryClient.invalidateQueries({ queryKey: listKey, exact: true });
    },
  });

  const detailAccessExpired =
    detailQuery.error instanceof ApiRequestError &&
    (detailQuery.error.status === 401 || detailQuery.error.status === 403);
  const mutationError = createMutation.error ?? appendMutation.error;
  const mutationAccessExpired =
    mutationError instanceof ApiRequestError &&
    (mutationError.status === 401 || mutationError.status === 403);
  const accessExpired =
    listAccessExpired || detailAccessExpired || mutationAccessExpired;
  const versionConflict =
    appendMutation.error instanceof ApiRequestError && appendMutation.error.status === 409;
  const selectedConversation = detailQuery.data;
  const canAppend =
    governedSessionAvailable &&
    !accessExpired &&
    selectedConversation?.lifecycle === "open" &&
    question.trim().length >= 3 &&
    question.trim().length <= 700 &&
    !appendMutation.isPending;

  function submitQuestion(event?: FormEvent) {
    event?.preventDefault();
    if (!canAppend || !selectedConversation) return;
    appendMutation.mutate({ conversation: selectedConversation, prompt: question.trim() });
  }

  function openCreatePanel(event: MouseEvent<HTMLButtonElement>) {
    setCreateTrigger(event.currentTarget);
    createMutation.reset();
    setCreating(true);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submitQuestion();
    }
  }

  return (
    <section
      className="operations-conversation-workspace"
      aria-labelledby="operations-conversation-title"
    >
      <header className="operations-conversation-heading">
        <div>
          <p className="eyebrow">OPERATIONS WORKSPACE</p>
          <h1 id="operations-conversation-title">Storage conversations</h1>
          <p>Durable, target-bound investigation context for evidence-grounded decision support.</p>
        </div>
        <div className="operations-conversation-heading-actions">
          {listQuery.data && (
            <span className={`operations-conversation-persistence ${listQuery.data.durable ? "durable" : "memory"}`}>
              <Database size={14} /> {listQuery.data.durable ? "Durable store" : "Development memory"}
            </span>
          )}
          <button
            className="operations-conversation-primary"
            type="button"
            disabled={
              !governedSessionAvailable || accessExpired || authorizedStorageTargets.length === 0
            }
            onClick={openCreatePanel}
          >
            <Plus size={15} /> New conversation
          </button>
        </div>
      </header>

      <div className="operations-conversation-boundary" role="note">
        <ShieldCheck size={18} />
        <div>
          <strong>No execution authority</strong>
          <span>
            Chat cannot invoke connectors, access credentials, create approvals, mutate ITSM records,
            dispatch workflows, or change infrastructure.
          </span>
        </div>
      </div>

      {!governedSessionAvailable && (
        <div className="operations-conversation-message access" role="status">
          <LogIn size={17} />
          <span>Sign in with your username and password to create or continue conversations.</span>
          {onRequestEnterpriseLogin && (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in
            </button>
          )}
        </div>
      )}
      {accessExpired && (
        <div className="operations-conversation-message error" role="alert">
          <LogIn size={17} />
          <span>Your session can no longer access this conversation workspace.</span>
          {onRequestEnterpriseLogin && (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          )}
        </div>
      )}
      {versionConflict && (
        <div className="operations-conversation-message error" role="alert">
          <RefreshCw size={17} />
          <span>The conversation changed before this question was appended.</span>
          <button type="button" onClick={() => void detailQuery.refetch()}>
            Refresh conversation
          </button>
        </div>
      )}
      {createMutation.isError && !accessExpired && (
        <div className="operations-conversation-message error" role="alert">
          <AlertTriangle size={17} /> Conversation creation failed. Review the target and retry.
        </div>
      )}
      {appendMutation.isError && !accessExpired && !versionConflict && (
        <div className="operations-conversation-message error" role="alert">
          <AlertTriangle size={17} /> The turn was not appended. No answer was accepted.
        </div>
      )}

      <div className={`operations-conversation-layout ${selectedConversationId ? "detail-open" : ""}`}>
        <aside className="operations-conversation-list" aria-label="Operational conversations">
          <div className="operations-conversation-list-heading">
            <div>
              <h2>Conversations</h2>
              <span>{listQuery.data?.conversations.length ?? 0} available</span>
            </div>
            <button
              className="operations-conversation-icon-button"
              type="button"
              aria-label="Refresh conversations"
              disabled={listQuery.isFetching}
              onClick={() => void listQuery.refetch()}
            >
              <RefreshCw size={16} />
            </button>
          </div>
          {listQuery.isLoading && (
            <div className="operations-conversation-list-state" role="status">
              <Clock3 size={18} /> Loading conversations
            </div>
          )}
          {listQuery.isError && !listAccessExpired && (
            <div className="operations-conversation-list-state error" role="alert">
              <AlertTriangle size={18} />
              <span>Conversations are unavailable.</span>
              <button type="button" onClick={() => void listQuery.refetch()}>
                <RefreshCw size={15} /> Retry
              </button>
            </div>
          )}
          {listQuery.data?.truncated && (
            <div className="operations-conversation-list-note" role="status">
              Showing the newest 50 authorized conversations.
            </div>
          )}
          {listQuery.data && listQuery.data.conversations.length === 0 && (
            <div className="operations-conversation-list-state empty">
              <MessageSquare size={20} />
              <strong>No conversations yet</strong>
              <span>Create a target-bound storage investigation context.</span>
              {governedSessionAvailable && !accessExpired && authorizedStorageTargets.length > 0 && (
                <button type="button" onClick={openCreatePanel}>
                  <Plus size={15} /> New conversation
                </button>
              )}
            </div>
          )}
          {listQuery.data && listQuery.data.conversations.length > 0 && (
            <ul>
              {listQuery.data.conversations.map((conversation) => (
                <li key={conversation.conversation_id}>
                  <button
                    type="button"
                    className={selectedConversationId === conversation.conversation_id ? "active" : ""}
                    aria-pressed={selectedConversationId === conversation.conversation_id}
                    aria-label={`Reopen ${conversation.title}`}
                    onClick={() => {
                      appendMutation.reset();
                      setSelectedConversationId(conversation.conversation_id);
                    }}
                  >
                    <span className="operations-conversation-list-title">
                      <MessageSquare size={16} />
                      <strong>{conversation.title}</strong>
                    </span>
                    <span>{targetLabel(authorizedStorageTargets, conversation.target_id)}</span>
                    <span className="operations-conversation-list-meta">
                      <span className={`operations-conversation-lifecycle ${conversation.lifecycle}`}>
                        {conversation.lifecycle}
                      </span>
                      <span>{conversation.turn_count} turns</span>
                      <time dateTime={conversation.updated_at}>{formatTimestamp(conversation.updated_at)}</time>
                    </span>
                    <span className="operations-conversation-reopen">
                      Reopen <ExternalLink size={13} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="operations-conversation-detail" aria-live="polite">
          {!selectedConversationId && (
            <div className="operations-conversation-welcome">
              <MessageSquare size={28} />
              <h2>Select or create a conversation</h2>
              <p>Each conversation remains bound to one authorized storage target and owner.</p>
              {authorizedStorageTargets.length === 0 ? (
                <>
                  <div className="operations-conversation-message warning" role="status">
                    <Server size={17} /> No authorized storage target is available in this scope.
                  </div>
                  {onNavigateContext && (
                    <button
                      type="button"
                      onClick={() =>
                        onNavigateContext({
                          destination: "inventory",
                          targetId: "",
                          conversationId: null,
                        })
                      }
                    >
                      <Server size={15} /> Open inventory
                    </button>
                  )}
                </>
              ) : null}
            </div>
          )}
          {selectedConversationId && detailQuery.isLoading && (
            <div className="operations-conversation-detail-state" role="status">
              <Clock3 size={20} /> Reopening durable conversation
            </div>
          )}
          {selectedConversationId && detailQuery.isError && !detailAccessExpired && (
            <div className="operations-conversation-detail-state error" role="alert">
              <AlertTriangle size={20} />
              <strong>Conversation could not be reopened.</strong>
              <span>The server did not return an exact authorized aggregate.</span>
              <div>
                <button type="button" onClick={() => setSelectedConversationId(null)}>
                  <ArrowLeft size={15} /> Back
                </button>
                <button type="button" onClick={() => void detailQuery.refetch()}>
                  <RefreshCw size={15} /> Retry
                </button>
              </div>
            </div>
          )}
          {selectedConversation && (
            <div className="operations-conversation-thread">
              <header className="operations-conversation-thread-heading">
                <button
                  className="operations-conversation-back"
                  type="button"
                  aria-label="Back to conversations"
                  onClick={() => setSelectedConversationId(null)}
                >
                  <ArrowLeft size={17} />
                </button>
                <div>
                  <p className="eyebrow">{targetLabel(authorizedStorageTargets, selectedConversation.target_id)}</p>
                  <h2>{selectedConversation.title}</h2>
                  <span>
                    Version {selectedConversation.version} | {selectedConversation.lifecycle} |
                    updated {formatTimestamp(selectedConversation.updated_at)}
                  </span>
                </div>
                <div className="operations-conversation-context-actions">
                  {onNavigateContext && (
                    <>
                      <button
                        type="button"
                        onClick={() =>
                          onNavigateContext({
                            destination: "inventory",
                            targetId: selectedConversation.target_id,
                            conversationId: selectedConversation.conversation_id,
                          })
                        }
                      >
                        <Server size={14} /> Inventory
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          onNavigateContext({
                            destination: "topology",
                            targetId: selectedConversation.target_id,
                            conversationId: selectedConversation.conversation_id,
                          })
                        }
                      >
                        <ExternalLink size={14} /> Topology
                      </button>
                    </>
                  )}
                </div>
              </header>

              <div className="operations-conversation-turns">
                {selectedConversation.turns.length === 0 && (
                  <div className="operations-conversation-thread-empty">
                    <Bot size={24} />
                    <strong>Start with an infrastructure question</strong>
                    <span>Atlas will preserve evidence, uncertainty, confidence basis, and safety boundaries.</span>
                  </div>
                )}
                {selectedConversation.turns.map((turn) => (
                  <ConversationTurn
                    key={turn.turn_id}
                    turn={turn}
                    onOpenEvidence={onOpenEvidence}
                    onOpenArtifact={onOpenArtifact}
                  />
                ))}
                {appendMutation.isPending && (
                  <div className="operations-conversation-generating" role="status">
                    <Clock3 size={17} /> Atlas is producing a bounded, evidence-grounded outcome.
                  </div>
                )}
              </div>

              <form className="operations-conversation-composer" onSubmit={submitQuestion}>
                {selectedConversation.lifecycle === "closed" && (
                  <div className="operations-conversation-message warning" role="status">
                    <ShieldCheck size={17} /> This conversation is closed and preserved as read-only history.
                  </div>
                )}
                <label htmlFor="operations-conversation-question">Infrastructure question</label>
                <div>
                  <textarea
                    id="operations-conversation-question"
                    rows={3}
                    minLength={3}
                    maxLength={700}
                    disabled={
                      !governedSessionAvailable ||
                      accessExpired ||
                      selectedConversation.lifecycle !== "open"
                    }
                    value={question}
                    placeholder="Ask about observed behavior, evidence, likely causes, or the safest next diagnostic step."
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                  />
                  <button
                    className="operations-conversation-send"
                    type="submit"
                    aria-label="Send infrastructure question"
                    disabled={!canAppend}
                  >
                    {appendMutation.isPending ? <Clock3 size={18} /> : <Send size={18} />}
                  </button>
                </div>
                <span>
                  Questions are bounded to this target. Responses cannot authorize or execute operations.
                </span>
              </form>
            </div>
          )}
        </div>
      </div>

      {creating && !accessExpired && (
        <ConversationCreatePanel
          targets={authorizedStorageTargets}
          pending={createMutation.isPending}
          returnFocusTo={createTrigger}
          onCancel={() => setCreating(false)}
          onSubmit={(input) => createMutation.mutate(input)}
        />
      )}
    </section>
  );
}
