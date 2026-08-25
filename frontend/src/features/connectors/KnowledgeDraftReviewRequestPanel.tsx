import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, LockKeyhole, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createOperationalKnowledgeReviewRequest,
  getOperationalKnowledgeReviewRequestOptions,
  getOperationalKnowledgeReviewRequests,
  operationalKnowledgeReviewRequestQueryKey,
  type OperationalKnowledgeReviewRequestInventoryItem,
  type OperationalKnowledgeReviewRequestOption,
  type ReviewableOperationalEvidenceKnowledgeDraft,
} from "../../api/knowledgeReviewRequests";

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function ReviewRequestRecord({
  reviewRequest,
}: {
  reviewRequest: OperationalKnowledgeReviewRequestInventoryItem;
}) {
  return (
    <div className="package-signing-record">
      <div className="section-heading">
        <div>
          <strong>{reviewRequest.title}</strong>
          <code>{reviewRequest.review_request_id}</code>
        </div>
        <span className="state-badge pending">
          <ClipboardCheck size={14} /> awaiting reviewer
        </span>
      </div>
      <div className="mcp-builder-facts">
        <div><span>Lifecycle</span><strong>review requested</strong></div>
        <div><span>Domain track</span><strong>awaiting reviewer</strong></div>
        <div><span>Security track</span><strong>awaiting reviewer</strong></div>
        <div><span>Content access</span><strong>locked</strong></div>
      </div>
      <p className="muted-copy">
        <LockKeyhole size={14} /> This request is unassigned and exposes no protected draft
        content. Assignment, inspection, decisions, approval, publication, retrieval, model,
        workflow, execution and deployment remain unavailable.
      </p>
    </div>
  );
}

function OptionFacts({ option }: { option: OperationalKnowledgeReviewRequestOption }) {
  return (
    <div className="mcp-builder-facts" aria-label="Signed review request option">
      <div><span>Policy</span><strong>{option.orchestration_policy_id}</strong></div>
      <div><span>Version</span><strong>{option.orchestration_policy_version}</strong></div>
      <div>
        <span>Assurance</span>
        <strong>{option.required_assurance_level.replaceAll("_", " ")}</strong>
      </div>
      <div>
        <span>Expires</span>
        <strong>{new Date(option.orchestration_policy_expires_at).toLocaleString()}</strong>
      </div>
    </div>
  );
}

export function KnowledgeDraftReviewRequestPanel({
  draft,
  onRequestCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey = "standalone",
}: {
  draft: ReviewableOperationalEvidenceKnowledgeDraft;
  onRequestCreated?: (reviewRequest: OperationalKnowledgeReviewRequestInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey?: string;
}) {
  const queryClient = useQueryClient();
  const queryKey = operationalKnowledgeReviewRequestQueryKey(sessionScopeKey, draft.draft_id);
  const [purpose, setPurpose] = useState(
    "Request independent review for this exact immutable operational knowledge draft.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const [selectedOptionId, setSelectedOptionId] = useState("");
  const [attempted, setAttempted] = useState(false);
  const inventoryQuery = useQuery({
    queryKey,
    queryFn: () => getOperationalKnowledgeReviewRequests({ draft }),
    retry: false,
    staleTime: 30_000,
  });
  const reviewRequest = inventoryQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: ["operational-knowledge-review-request-options", sessionScopeKey, draft.draft_id],
    queryFn: () => getOperationalKnowledgeReviewRequestOptions({ draft }),
    enabled: inventoryQuery.isSuccess && !reviewRequest && !attempted,
    retry: false,
  });
  const selectedOption = optionsQuery.data?.find(
    (option) => option.review_request_option_id === selectedOptionId,
  ) ?? (optionsQuery.data?.length === 1 ? optionsQuery.data[0] : undefined);
  const mutation = useMutation({
    mutationFn: createOperationalKnowledgeReviewRequest,
    retry: false,
    onSuccess: ({ data }) => {
      queryClient.setQueryData<OperationalKnowledgeReviewRequestInventoryItem[]>(queryKey, [data]);
      onRequestCreated?.(data);
    },
    onSettled: () => {
      void inventoryQuery.refetch();
    },
  });
  const canSubmit = Boolean(
    selectedOption && acknowledged && purpose.trim().length >= 20 && purpose.length <= 1000 &&
    !attempted && !mutation.isPending,
  );
  const error = mutation.error ?? optionsQuery.error ?? inventoryQuery.error;
  const authenticationFailed = hasStatus(error, 401);
  const authorizationFailed = hasStatus(error, 403);

  const submit = () => {
    if (!selectedOption || !canSubmit) return;
    setAttempted(true);
    mutation.mutate({ draft, option: selectedOption, purpose });
  };

  if (inventoryQuery.isLoading) {
    return (
      <div className="installed-mcp-status" role="status">
        <RefreshCw className="spin" size={18} />
        <span>Loading authoritative review request inventory...</span>
      </div>
    );
  }

  if (inventoryQuery.isError) {
    return (
      <div className="installed-mcp-status error-state" role="alert">
        {authenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
        <div>
          <strong>{authenticationFailed
            ? "Your signed-in session has expired"
            : authorizationFailed
              ? "Knowledge review request scope is required"
              : "Review request inventory is unavailable"}</strong>
          <span>{authenticationFailed
            ? "Sign in again with your username and password, then reload the inventory."
            : authorizationFailed
              ? "This signed-in account cannot read or request operational knowledge review."
              : "Review controls remain hidden until authoritative inventory can be read."}</span>
        </div>
        {authenticationFailed && onRequestEnterpriseLogin ? (
          <button type="button" onClick={onRequestEnterpriseLogin}>
            <LogIn size={15} /> Sign in again
          </button>
        ) : !authorizationFailed ? (
          <button type="button" onClick={() => void inventoryQuery.refetch()}>
            <RefreshCw size={15} /> Reload inventory
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <section className="target-configuration-panel" aria-labelledby="knowledge-review-request-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">REVIEW REQUEST</p>
          <h3 id="knowledge-review-request-title">Knowledge review request</h3>
        </div>
        <ClipboardCheck size={24} />
      </div>
      {reviewRequest ? <ReviewRequestRecord reviewRequest={reviewRequest} /> : (
        <>
          {optionsQuery.isLoading && (
            <div className="installed-mcp-status" role="status">
              <RefreshCw className="spin" size={18} />
              <span>Loading signed review request options...</span>
            </div>
          )}
          {optionsQuery.isError && !attempted && (
            <div className="installed-mcp-status error-state" role="alert">
              {authenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
              <div>
                <strong>{authenticationFailed
                  ? "Your signed-in session has expired"
                  : authorizationFailed
                    ? "Knowledge review request scope is required"
                    : "Signed review request options are unavailable"}</strong>
                <span>{authenticationFailed
                  ? "Sign in again with your username and password."
                  : authorizationFailed
                    ? "This signed-in account cannot request operational knowledge review."
                    : "No POST is available until exact server-provided options can be read."}</span>
              </div>
              {authenticationFailed && onRequestEnterpriseLogin ? (
                <button type="button" onClick={onRequestEnterpriseLogin}>
                  <LogIn size={15} /> Sign in again
                </button>
              ) : !authorizationFailed ? (
                <button type="button" onClick={() => void optionsQuery.refetch()}>
                  <RefreshCw size={15} /> Reload options
                </button>
              ) : null}
            </div>
          )}
          {optionsQuery.isSuccess && optionsQuery.data.length === 0 && !attempted && (
            <div className="installed-mcp-empty compact">
              <ClipboardCheck size={20} />
              <div>
                <strong>No signed review request option is available</strong>
                <span>The immutable draft remains unreviewed and unchanged.</span>
              </div>
            </div>
          )}
          {optionsQuery.data && optionsQuery.data.length > 0 && !attempted && (
            <>
              {optionsQuery.data.length > 1 ? (
                <label>
                  <span>Signed review request option</span>
                  <select
                    value={selectedOption?.review_request_option_id ?? ""}
                    onChange={(event) => setSelectedOptionId(event.target.value)}
                  >
                    {optionsQuery.data.map((option) => (
                      <option
                        key={option.review_request_option_id}
                        value={option.review_request_option_id}
                      >
                        {option.orchestration_policy_id} / {option.orchestration_policy_version}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {selectedOption ? <OptionFacts option={selectedOption} /> : null}
              <label>
                <span>Review purpose</span>
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
                  The result is only an unassigned review request. It grants no content access,
                  assignment, decision, approval, publication, model, workflow, execution,
                  deployment or mutation authority.
                </span>
              </label>
              <button className="primary-button" type="button" disabled={!canSubmit} onClick={submit}>
                <ClipboardCheck size={16} /> Request review
              </button>
            </>
          )}
          {attempted && !reviewRequest && (
            <div
              className={`installed-mcp-status ${mutation.isError ? "error-state" : ""}`}
              role={mutation.isError ? "alert" : "status"}
            >
              {mutation.isPending
                ? <RefreshCw className="spin" size={18} />
                : <AlertTriangle size={18} />}
              <div>
                <strong>{mutation.isPending
                  ? "Creating unassigned review request..."
                  : authenticationFailed
                    ? "Your signed-in session has expired"
                    : authorizationFailed
                      ? "Knowledge review request scope is required"
                      : "Review request attempt requires inventory reconciliation"}</strong>
                <span>{mutation.isPending
                  ? "This one-way attempt is not automatically repeated."
                  : authenticationFailed
                    ? "Sign in again with your username and password. The POST will not be repeated."
                    : authorizationFailed
                      ? "This account cannot request review. The POST will not be repeated."
                      : "The attempt is permanently locked. Reload authoritative inventory to determine whether a request exists."}</span>
              </div>
              {!mutation.isPending && (
                authenticationFailed && onRequestEnterpriseLogin ? (
                  <button type="button" onClick={onRequestEnterpriseLogin}>
                    <LogIn size={15} /> Sign in again
                  </button>
                ) : !authorizationFailed ? (
                  <button type="button" onClick={() => void inventoryQuery.refetch()}>
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
