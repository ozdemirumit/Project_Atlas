import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, LockKeyhole, LogIn, RefreshCw, ShieldCheck, UserRoundCheck } from
  "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createOperationalKnowledgeReviewerAssignment,
  getOperationalKnowledgeReviewerAssignmentOptions,
  getOperationalKnowledgeReviewerAssignments,
  operationalKnowledgeReviewerAssignmentQueryKey,
  type OperationalKnowledgeReviewerAssignmentInventoryItem,
  type OperationalKnowledgeReviewerAssignmentOption,
  type OperationalKnowledgeReviewerAssignmentSource,
} from "../../api/reviewerAssignments";

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function AssignmentRecord({
  assignment,
}: {
  assignment: OperationalKnowledgeReviewerAssignmentInventoryItem;
}) {
  return (
    <div className="package-signing-record">
      <div className="section-heading">
        <strong>Independent review tracks</strong>
        <span className="state-badge approved">
          <ShieldCheck size={14} /> reviewers assigned
        </span>
      </div>
      <div className="mcp-builder-facts">
        <div><span>Domain track</span><strong>{assignment.domain_status}</strong></div>
        <div><span>Security track</span><strong>{assignment.security_status}</strong></div>
        <div>
          <span>Assignment expires</span>
          <strong>{new Date(assignment.expires_at).toLocaleString()}</strong>
        </div>
      </div>
      <p className="muted-copy">
        <LockKeyhole size={14} /> Reviewer identity and protected content remain unavailable.
        Inspection, findings, decisions, approval, publication, retrieval, model, workflow,
        execution and deployment remain separate stages.
      </p>
    </div>
  );
}

function OptionFacts({ option }: { option: OperationalKnowledgeReviewerAssignmentOption }) {
  return (
    <div className="mcp-builder-facts" aria-label="Signed reviewer assignment option">
      <div><span>Policy</span><strong>{option.assignment_policy_id}</strong></div>
      <div><span>Version</span><strong>{option.assignment_policy_version}</strong></div>
      <div>
        <span>Assurance</span>
        <strong>{option.required_assurance_level.replaceAll("_", " ")}</strong>
      </div>
      <div>
        <span>Option expires</span>
        <strong>{new Date(option.assignment_policy_expires_at).toLocaleString()}</strong>
      </div>
    </div>
  );
}

export function ReviewerAssignmentPanel({
  reviewRequest,
  onAssignmentCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey = "standalone",
}: {
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource;
  onAssignmentCreated?: (
    assignment: OperationalKnowledgeReviewerAssignmentInventoryItem,
  ) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey?: string;
}) {
  const queryClient = useQueryClient();
  const queryKey = operationalKnowledgeReviewerAssignmentQueryKey(
    sessionScopeKey,
    reviewRequest.review_request_id,
  );
  const attemptQueryKey = [
    "operational-knowledge-reviewer-assignment-attempted",
    sessionScopeKey,
    reviewRequest.review_request_id,
  ] as const;
  const [purpose, setPurpose] = useState(
    "Assign distinct eligible domain and security reviewers without exposing identity.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const [selectedOptionId, setSelectedOptionId] = useState("");
  const [attempted, setAttempted] = useState(
    () => queryClient.getQueryData<boolean>(attemptQueryKey) === true,
  );
  const inventoryQuery = useQuery({
    queryKey,
    queryFn: () => getOperationalKnowledgeReviewerAssignments({ reviewRequest }),
    retry: false,
    staleTime: 30_000,
  });
  const assignment = inventoryQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "operational-knowledge-reviewer-assignment-options",
      sessionScopeKey,
      reviewRequest.review_request_id,
    ],
    queryFn: () => getOperationalKnowledgeReviewerAssignmentOptions({ reviewRequest }),
    enabled: inventoryQuery.isSuccess && !assignment && !attempted,
    retry: false,
  });
  const selectedOption = optionsQuery.data?.find(
    (option) => option.assignment_option_id === selectedOptionId,
  ) ?? (optionsQuery.data?.length === 1 ? optionsQuery.data[0] : undefined);
  const mutation = useMutation({
    mutationFn: createOperationalKnowledgeReviewerAssignment,
    retry: false,
    onSuccess: ({ data }) => {
      queryClient.setQueryData<OperationalKnowledgeReviewerAssignmentInventoryItem[]>(
        queryKey,
        [data],
      );
      onAssignmentCreated?.(data);
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
    queryClient.setQueryData(attemptQueryKey, true);
    setAttempted(true);
    mutation.mutate({ reviewRequest, option: selectedOption, purpose });
  };

  if (inventoryQuery.isLoading) {
    return (
      <div className="installed-mcp-status" role="status">
        <RefreshCw className="spin" size={18} />
        <span>Loading authoritative reviewer assignment inventory...</span>
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
              ? "Reviewer assignment scope is required"
              : "Reviewer assignment inventory is unavailable"}</strong>
          <span>{authenticationFailed
            ? "Sign in again with your username and password, then reload the inventory."
            : authorizationFailed
              ? "This signed-in account cannot read or create reviewer assignments."
              : "Assignment controls remain hidden until authoritative inventory can be read."}</span>
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
    <section className="target-configuration-panel" aria-labelledby="reviewer-assignment-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">REVIEW GOVERNANCE</p>
          <h3 id="reviewer-assignment-title">Reviewer assignment</h3>
        </div>
        <UserRoundCheck size={24} />
      </div>
      {assignment ? <AssignmentRecord assignment={assignment} /> : (
        <>
          {optionsQuery.isLoading && (
            <div className="installed-mcp-status" role="status">
              <RefreshCw className="spin" size={18} />
              <span>Loading signed reviewer assignment options...</span>
            </div>
          )}
          {optionsQuery.isError && !attempted && (
            <div className="installed-mcp-status error-state" role="alert">
              {authenticationFailed ? <LogIn size={18} /> : <AlertTriangle size={18} />}
              <div>
                <strong>{authenticationFailed
                  ? "Your signed-in session has expired"
                  : authorizationFailed
                    ? "Reviewer assignment scope is required"
                    : "Signed reviewer assignment options are unavailable"}</strong>
                <span>{authenticationFailed
                  ? "Sign in again with your username and password."
                  : authorizationFailed
                    ? "This signed-in account cannot assign reviewers."
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
              <UserRoundCheck size={20} />
              <div>
                <strong>No signed reviewer assignment option is available</strong>
                <span>The review request remains unassigned and unchanged.</span>
              </div>
            </div>
          )}
          {optionsQuery.data && optionsQuery.data.length > 0 && !attempted && (
            <>
              {optionsQuery.data.length > 1 ? (
                <label>
                  <span>Signed reviewer assignment option</span>
                  <select
                    value={selectedOption?.assignment_option_id ?? ""}
                    onChange={(event) => setSelectedOptionId(event.target.value)}
                  >
                    {optionsQuery.data.map((option) => (
                      <option key={option.assignment_option_id} value={option.assignment_option_id}>
                        {option.assignment_policy_id} / {option.assignment_policy_version}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {selectedOption ? <OptionFacts option={selectedOption} /> : null}
              <label>
                <span>Assignment purpose</span>
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
                  This assigns distinct eligible domain and security review tracks only. It exposes
                  no identity or content and grants no inspection, decision, approval, publication,
                  retrieval, model, workflow, execution, deployment or mutation authority.
                </span>
              </label>
              <button className="primary-button" type="button" disabled={!canSubmit} onClick={submit}>
                <UserRoundCheck size={16} /> Assign reviewers
              </button>
            </>
          )}
          {attempted && !assignment && (
            <div
              className={`installed-mcp-status ${mutation.isError ? "error-state" : ""}`}
              role={mutation.isError ? "alert" : "status"}
            >
              {mutation.isPending
                ? <RefreshCw className="spin" size={18} />
                : <AlertTriangle size={18} />}
              <div>
                <strong>{mutation.isPending
                  ? "Assigning independent review tracks..."
                  : authenticationFailed
                    ? "Your signed-in session has expired"
                    : authorizationFailed
                      ? "Reviewer assignment scope is required"
                      : "Reviewer assignment attempt requires inventory reconciliation"}</strong>
                <span>{mutation.isPending
                  ? "This one-way attempt is not automatically repeated."
                  : authenticationFailed
                    ? "Sign in again with your username and password. The POST will not be repeated."
                    : authorizationFailed
                      ? "This account cannot assign reviewers. The POST will not be repeated."
                      : "The attempt is permanently locked. Reload authoritative inventory to determine whether an assignment exists."}</span>
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
