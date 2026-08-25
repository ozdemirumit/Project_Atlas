import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookMarked, FileCheck2, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createOperationalEvidenceKnowledgeDraft,
  getOperationalEvidenceKnowledgeDraftOptions,
  getOperationalEvidenceKnowledgeDrafts,
  operationalEvidenceKnowledgeDraftQueryKey,
  type OperationalEvidenceKnowledgeDraftInventoryItem,
  type OperationalEvidenceKnowledgeDraftOption,
} from "../../api/evidenceDrafts";
import type { ConnectorInvocationEvidenceInventoryItem } from "../../api/invocationEvidence";

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function DraftRecord({ draft }: { draft: OperationalEvidenceKnowledgeDraftInventoryItem }) {
  return (
    <div className="package-signing-record">
      <div className="section-heading">
        <div>
          <strong>{draft.title}</strong>
          <code>{draft.draft_id}</code>
        </div>
        <span className="state-badge neutral">
          <FileCheck2 size={14} />draft
        </span>
      </div>
      <div className="mcp-builder-facts">
        <div><span>Lifecycle</span><strong>draft</strong></div>
        <div><span>Classification</span><strong>{draft.classification.replace("classification.", "")}</strong></div>
        <div><span>Items</span><strong>{draft.draft_item_count}</strong></div>
        <div><span>Retrieval</span><strong>not published</strong></div>
      </div>
      <p className="muted-copy">
        This immutable draft is not reviewed, approved, indexed, published, available to models,
        scheduled, executable, deployable or authorized to mutate infrastructure.
      </p>
    </div>
  );
}

function OptionFacts({ option }: { option: OperationalEvidenceKnowledgeDraftOption }) {
  return (
    <div className="mcp-builder-facts" aria-label="Signed curation option">
      <div><span>Policy</span><strong>{option.curation_policy_id}</strong></div>
      <div><span>Assurance</span><strong>{option.required_assurance_level.replaceAll("_", " ")}</strong></div>
      <div><span>Classification</span><strong>{option.classification.replace("classification.", "")}</strong></div>
      <div><span>Expires</span><strong>{new Date(option.curation_policy_expires_at).toLocaleString()}</strong></div>
    </div>
  );
}

export function EvidenceKnowledgeDraftPanel({
  evidence,
  onDraftCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey = "standalone",
}: {
  evidence: ConnectorInvocationEvidenceInventoryItem;
  onDraftCreated?: (draft: OperationalEvidenceKnowledgeDraftInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey?: string;
}) {
  const queryClient = useQueryClient();
  const queryKey = operationalEvidenceKnowledgeDraftQueryKey(
    sessionScopeKey,
    evidence.ingestion_id,
  );
  const [purpose, setPurpose] = useState(
    "Create a governed unapproved draft from this exact immutable operational evidence.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const [selectedOptionId, setSelectedOptionId] = useState("");
  const [attempted, setAttempted] = useState(false);
  const draftQuery = useQuery({
    queryKey,
    queryFn: () => getOperationalEvidenceKnowledgeDrafts({ evidence }),
    retry: false,
    staleTime: 30_000,
  });
  const draft = draftQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: ["operational-evidence-knowledge-draft-options", sessionScopeKey, evidence.ingestion_id],
    queryFn: () => getOperationalEvidenceKnowledgeDraftOptions({ evidence }),
    enabled: draftQuery.isSuccess && !draft && !attempted,
    retry: false,
  });
  const selectedOption = optionsQuery.data?.find(
    (option) => option.curation_option_id === selectedOptionId,
  ) ?? (optionsQuery.data?.length === 1 ? optionsQuery.data[0] : undefined);
  const mutation = useMutation({
    mutationFn: createOperationalEvidenceKnowledgeDraft,
    onSuccess: ({ data }) => {
      queryClient.setQueryData<OperationalEvidenceKnowledgeDraftInventoryItem[]>(queryKey, [data]);
      onDraftCreated?.(data);
    },
    onSettled: () => {
      void draftQuery.refetch();
    },
  });
  const canSubmit = Boolean(
    selectedOption && acknowledged && purpose.trim().length >= 20 && purpose.length <= 1000 &&
    !attempted && !mutation.isPending,
  );
  const error = mutation.error ?? optionsQuery.error ?? draftQuery.error;
  const authenticationFailed = hasStatus(error, 401);
  const authorizationFailed = hasStatus(error, 403);

  const submit = () => {
    if (!selectedOption || !canSubmit) return;
    setAttempted(true);
    mutation.mutate({ evidence, option: selectedOption, purpose });
  };

  if (draftQuery.isLoading) {
    return (
      <div className="installed-mcp-status" role="status">
        <RefreshCw className="spin" size={18} />
        <span>Loading authoritative knowledge draft inventory...</span>
      </div>
    );
  }

  if (draftQuery.isError) {
    return (
      <div className="installed-mcp-status error-state" role="alert">
        {authenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
        <div>
          <strong>{authenticationFailed
            ? "Your signed-in session has expired"
            : authorizationFailed
              ? "Knowledge draft scope is required"
              : "Knowledge draft inventory is unavailable"}</strong>
          <span>{authenticationFailed
            ? "Sign in again with your username and password, then reload the inventory."
            : authorizationFailed
              ? "This signed-in account cannot read or curate operational evidence drafts."
              : "Curation controls remain hidden until authoritative inventory can be read."}</span>
        </div>
        {authenticationFailed && onRequestEnterpriseLogin ? (
          <button type="button" onClick={onRequestEnterpriseLogin}><LogIn size={15} /> Sign in again</button>
        ) : !authorizationFailed ? (
          <button type="button" onClick={() => void draftQuery.refetch()}>
            <RefreshCw size={15} /> Reload inventory
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <section
      className="target-configuration-panel evidence-knowledge-draft-panel"
      aria-labelledby="evidence-knowledge-draft-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">KNOWLEDGE CURATION</p>
          <h3 id="evidence-knowledge-draft-title">Knowledge draft curation</h3>
        </div>
        <BookMarked size={24} />
      </div>
      {draft ? <DraftRecord draft={draft} /> : (
        <>
          {optionsQuery.isLoading && (
            <div className="installed-mcp-status" role="status">
              <RefreshCw className="spin" size={18} />
              <span>Loading signed curation options...</span>
            </div>
          )}
          {optionsQuery.isError && !attempted && (
            <div className="installed-mcp-status error-state" role="alert">
              {authenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
              <div>
                <strong>{authenticationFailed
                  ? "Your signed-in session has expired"
                  : authorizationFailed
                    ? "Knowledge draft scope is required"
                    : "Signed curation options are unavailable"}</strong>
                <span>{authenticationFailed
                  ? "Sign in again with your username and password."
                  : authorizationFailed
                    ? "This signed-in account cannot curate operational evidence."
                    : "No POST is available until exact server-provided options can be read."}</span>
              </div>
              {authenticationFailed && onRequestEnterpriseLogin ? (
                <button type="button" onClick={onRequestEnterpriseLogin}><LogIn size={15} /> Sign in again</button>
              ) : !authorizationFailed ? (
                <button type="button" onClick={() => void optionsQuery.refetch()}>
                  <RefreshCw size={15} /> Reload options
                </button>
              ) : null}
            </div>
          )}
          {optionsQuery.isSuccess && optionsQuery.data.length === 0 && !attempted && (
            <div className="installed-mcp-empty compact">
              <BookMarked size={20} />
              <div><strong>No signed curation option is available</strong><span>The evidence remains preserved and unchanged.</span></div>
            </div>
          )}
          {optionsQuery.data && optionsQuery.data.length > 0 && !attempted && (
            <>
              {optionsQuery.data.length > 1 ? (
                <label>
                  <span>Signed curation option</span>
                  <select
                    value={selectedOption?.curation_option_id ?? ""}
                    onChange={(event) => setSelectedOptionId(event.target.value)}
                  >
                    {optionsQuery.data.map((option) => (
                      <option key={option.curation_option_id} value={option.curation_option_id}>
                        {option.curation_policy_id} / {option.curation_policy_version}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {selectedOption ? <OptionFacts option={selectedOption} /> : null}
              <label>
                <span>Curation purpose</span>
                <textarea
                  value={purpose}
                  onChange={(event) => setPurpose(event.target.value)}
                  rows={3}
                  maxLength={1000}
                />
              </label>
              <label className="approval-check">
                <input
                  type="checkbox"
                  checked={acknowledged}
                  onChange={(event) => setAcknowledged(event.target.checked)}
                />
                <span>
                  The result is an unapproved, non-retrievable draft and grants no review,
                  publication, model, workflow, execution, deployment or mutation authority.
                </span>
              </label>
              <button className="primary-button" type="button" disabled={!canSubmit} onClick={submit}>
                <BookMarked size={16} /> Create knowledge draft
              </button>
            </>
          )}
          {attempted && !draft && (
            <div className={`installed-mcp-status ${mutation.isError ? "error-state" : ""}`} role={mutation.isError ? "alert" : "status"}>
              {mutation.isPending ? <RefreshCw className="spin" size={18} /> : <AlertTriangle size={18} />}
              <div>
                <strong>{mutation.isPending ? "Creating immutable draft..." : authenticationFailed
                  ? "Your signed-in session has expired"
                  : authorizationFailed
                    ? "Knowledge draft scope is required"
                    : "Draft attempt requires inventory reconciliation"}</strong>
                <span>{mutation.isPending
                  ? "This one-way attempt is not automatically repeated."
                  : authenticationFailed
                    ? "Sign in again with your username and password. The POST will not be repeated."
                    : authorizationFailed
                      ? "This account cannot curate the evidence. The POST will not be repeated."
                      : "The attempt is permanently locked. Reload authoritative inventory to determine whether a draft exists."}</span>
              </div>
              {!mutation.isPending && (
                authenticationFailed && onRequestEnterpriseLogin ? (
                  <button type="button" onClick={onRequestEnterpriseLogin}><LogIn size={15} /> Sign in again</button>
                ) : !authorizationFailed ? (
                  <button type="button" onClick={() => void draftQuery.refetch()}>
                    <RefreshCw size={15} /> Reload inventory
                  </button>
                ) : null
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
