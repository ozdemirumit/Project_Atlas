import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, LogIn, Play, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  createConnectorBoundedInvocation,
  getConnectorBoundedInvocationOptions,
  getConnectorBoundedInvocations,
  type ConnectorBoundedInvocationInventoryItem,
  type ConnectorBoundedInvocationOption,
} from "../../api/boundedInvocations";
import { ApiRequestError } from "../../api/client";
import type {
  ConnectorInvocationAuthorizationInventoryItem,
} from "../../api/invocationAuthorizations";

function optionKey(option: ConnectorBoundedInvocationOption): string {
  return JSON.stringify([
    option.source_authorization_id,
    option.source_authorization_digest,
    option.package_digest,
    option.capability_id,
    option.required_permission,
    option.invocation_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function assuranceLabel(level: ConnectorBoundedInvocationOption["required_assurance_level"]): string {
  if (level === "hardware_backed") return "hardware-backed step-up";
  if (level === "multi_factor") return "multi-factor step-up";
  return "username and password";
}

interface BoundedInvocationPanelProps {
  authorization: ConnectorInvocationAuthorizationInventoryItem;
  existingInvocation?: ConnectorBoundedInvocationInventoryItem;
  onInvocationCreated?: (invocation: ConnectorBoundedInvocationInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function BoundedInvocationPanel({
  authorization,
  existingInvocation,
  onInvocationCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: BoundedInvocationPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Invoke one authorized read-only capability and close every ephemeral resource.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const inventoryQueryKey = [
    "connector-bounded-invocations",
    sessionScopeKey,
    authorization.authorization_id,
  ];
  const inventoryQuery = useQuery({
    queryKey: inventoryQueryKey,
    queryFn: () => getConnectorBoundedInvocations({
      sourceAuthorizationId: authorization.authorization_id,
    }),
    initialData: existingInvocation ? [existingInvocation] : undefined,
  });
  const currentInvocation = inventoryQuery.isError ? undefined : inventoryQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "connector-bounded-invocation-options",
      sessionScopeKey,
      authorization.authorization_id,
    ],
    queryFn: () => getConnectorBoundedInvocationOptions(authorization.authorization_id),
    enabled: inventoryQuery.isSuccess && !currentInvocation,
  });
  const options = optionsQuery.isError ? [] : (optionsQuery.data ?? []);
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorBoundedInvocationOption) => {
      const payload = await createConnectorBoundedInvocation({
        authorization,
        option,
        purpose,
      });
      onInvocationCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (invocation) => {
      queryClient.setQueryData<ConnectorBoundedInvocationInventoryItem[]>(
        inventoryQueryKey,
        [invocation],
      );
      setAcknowledgedOptionKey("");
    },
  });
  const invocation = inventoryQuery.isError ? undefined : currentInvocation;
  const canSubmit = acknowledgedOptionKey === effectiveSelectedOptionKey &&
    Boolean(selectedOption) && purpose.trim().length >= 20 &&
    !inventoryQuery.isFetching && !optionsQuery.isFetching && !mutation.isPending;
  const requestError = invocation
    ? undefined
    : (mutation.error ?? inventoryQuery.error ?? optionsQuery.error);
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const uncertain = hasStatus(requestError, 503);
  const refreshEvidence = () => {
    mutation.reset();
    setSelectedOptionKey("");
    setAcknowledgedOptionKey("");
    void inventoryQuery.refetch();
    void optionsQuery.refetch();
  };
  const reloadAfterUncertainAttempt = () => {
    void inventoryQuery.refetch();
  };

  return (
    <section
      className="target-configuration-panel bounded-invocation-panel"
      aria-labelledby="bounded-invocation-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">ATOMIC SINGLE-USE READ</p>
          <h3 id="bounded-invocation-title">Bounded invocation</h3>
        </div>
        <Play size={24} />
      </div>

      {inventoryQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking immutable invocation completion...</span>
        </div>
      )}

      {!invocation && inventoryQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed invocation options...</span>
        </div>
      )}

      {!invocation && optionsQuery.isSuccess && options.length === 0 && !uncertain && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible bounded invocation option</strong>
            <span>
              The authorization may be consumed, expired or no longer match a current signed
              policy. Atlas cannot create or edit an invocation scope in the browser.
            </span>
          </div>
        </div>
      )}

      {!invocation && selectedOption && !uncertain && (
        <>
          <label>
            <span>Signed bounded invocation option</span>
            <select
              aria-label="Signed bounded invocation option"
              value={effectiveSelectedOptionKey}
              disabled={inventoryQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => {
                setSelectedOptionKey(event.target.value);
                setAcknowledgedOptionKey("");
              }}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.capability_id} / {option.capability_class}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts bounded-invocation-option-facts">
            <div><span>Permission</span><strong>{selectedOption.required_permission}</strong></div>
            <div><span>Timeout limit</span><strong>{selectedOption.maximum_timeout_seconds}s</strong></div>
            <div><span>Output limit</span><strong>{selectedOption.maximum_output_bytes} bytes</strong></div>
            <div><span>Observation limit</span><strong>{selectedOption.maximum_observations}</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed bounded invocation boundary">
            <div><span>Invocation policy</span><code>{selectedOption.invocation_policy_id}</code></div>
            <div><span>Policy version</span><strong>{selectedOption.invocation_policy_version}</strong></div>
            <div><span>Policy expires</span><strong>{new Date(selectedOption.invocation_policy_expires_at).toLocaleString()}</strong></div>
            <div><span>Assurance</span><strong>{assuranceLabel(selectedOption.required_assurance_level)}</strong></div>
          </div>
          <label>
            <span>Invocation purpose</span>
            <textarea
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              rows={3}
              minLength={20}
              maxLength={1000}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={acknowledgedOptionKey === effectiveSelectedOptionKey}
              onChange={(event) => setAcknowledgedOptionKey(
                event.target.checked ? effectiveSelectedOptionKey : "",
              )}
            />
            <span>
              The authorization is consumed before the call and cannot be released or retried if
              the outcome is uncertain. Exactly one read-only capability may run; no scheduling,
              evidence ingestion, execution, deployment or infrastructure mutation is granted.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => {
              if (selectedOption) mutation.mutate(selectedOption);
            }}
          >
            {mutation.isPending
              ? <RefreshCw className="spin" size={16} />
              : <Play size={16} />}
            {mutation.isPending ? "Invoking once..." : "Invoke once"}
          </button>
        </>
      )}

      {requestError && (
        <div className="workspace-message error-state" role="alert">
          {authenticationFailed ? <LogIn size={20} /> : <AlertTriangle size={20} />}
          <div>
            <h3>
              {authenticationFailed
                ? "Your signed-in session has expired"
                : authorizationFailed
                  ? "Bounded invocation permission is required"
                  : uncertain
                    ? "Invocation outcome is uncertain"
                    : sourceMissing
                      ? "Invocation authorization is no longer current"
                      : conflict
                        ? "Bounded invocation evidence changed"
                        : "Bounded invocation unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again with your username and password, then reload current evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : uncertain
                    ? "The authorization may already be consumed. Do not retry; reload only the authoritative completion inventory."
                    : sourceMissing
                      ? "Reload the invocation authorization and wait for current signed options."
                      : "Authorization lineage, exact permission, policy, freshness, separation or cleanup evidence failed."}
            </p>
          </div>
          {authenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : uncertain ? (
            <button type="button" onClick={reloadAfterUncertainAttempt}>
              <RefreshCw size={15} /> Reload authoritative inventory
            </button>
          ) : !authorizationFailed ? (
            <button type="button" onClick={refreshEvidence}>
              <RefreshCw size={15} /> Refresh evidence
            </button>
          ) : null}
        </div>
      )}

      {invocation && (
        <div className="package-signing-record bounded-invocation-record">
          <div className="section-heading">
            <div>
              <strong>Invocation completed</strong>
              <code>{invocation.invocation_id}</code>
            </div>
            <span className="state-badge success">
              <BadgeCheck size={14} /> closed safely
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Capability</span><strong>{invocation.capability_id}</strong></div>
            <div><span>Permission</span><strong>{invocation.required_permission}</strong></div>
            <div><span>Observations</span><strong>{invocation.observation_count}</strong></div>
            <div><span>Output</span><strong>{invocation.output_bytes} bytes</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Immutable invocation completion evidence">
            <div><span>Result</span><strong>validated and redacted</strong></div>
            <div><span>Target</span><strong>disconnected</strong></div>
            <div><span>Evidence</span><strong>not ingested</strong></div>
            <div><span>Completed</span><strong>{new Date(invocation.completed_at).toLocaleString()}</strong></div>
          </div>
          <p className="muted-copy">
            The exact read-only capability ran once. The authorization is consumed, every
            ephemeral resource is closed, and no workflow, scheduling, execution, deployment or
            infrastructure-change authority was created.
          </p>
        </div>
      )}
    </section>
  );
}
