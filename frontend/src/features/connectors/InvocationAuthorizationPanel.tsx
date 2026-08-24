import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, LogIn, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorInvocationAuthorization,
  getConnectorInvocationAuthorizationOptions,
  getConnectorInvocationAuthorizations,
  type ConnectorInvocationAuthorizationInventoryItem,
  type ConnectorInvocationAuthorizationOption,
} from "../../api/invocationAuthorizations";
import type {
  ConnectorTargetSessionVerificationInventoryItem,
} from "../../api/targetSessionVerifications";

function optionKey(option: ConnectorInvocationAuthorizationOption): string {
  return JSON.stringify([
    option.source_target_session_verification_id,
    option.source_target_session_digest,
    option.capability_id,
    option.invocation_profile_digest,
    option.input_envelope_digest,
    option.authorization_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface InvocationAuthorizationPanelProps {
  targetSession: ConnectorTargetSessionVerificationInventoryItem;
  existingAuthorization?: ConnectorInvocationAuthorizationInventoryItem;
  onAuthorizationCreated?: (
    authorization: ConnectorInvocationAuthorizationInventoryItem,
  ) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function InvocationAuthorizationPanel({
  targetSession,
  existingAuthorization,
  onAuthorizationCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: InvocationAuthorizationPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Authorize one bounded read-only capability invocation without invoking or scheduling it.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const authorizationQueryKey = [
    "connector-invocation-authorizations",
    sessionScopeKey,
    targetSession.verification_id,
  ];
  const authorizationQuery = useQuery({
    queryKey: authorizationQueryKey,
    queryFn: () => getConnectorInvocationAuthorizations({
      sourceTargetSessionVerificationId: targetSession.verification_id,
    }),
    initialData: existingAuthorization ? [existingAuthorization] : undefined,
  });
  const currentAuthorization = authorizationQuery.isError
    ? undefined
    : authorizationQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "connector-invocation-authorization-options",
      sessionScopeKey,
      targetSession.verification_id,
    ],
    queryFn: () => getConnectorInvocationAuthorizationOptions(targetSession.verification_id),
    enabled: authorizationQuery.isSuccess && !currentAuthorization,
  });
  const options = optionsQuery.isError ? [] : (optionsQuery.data ?? []);
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorInvocationAuthorizationOption) => {
      const payload = await createConnectorInvocationAuthorization({
        targetSession,
        option,
        purpose,
      });
      onAuthorizationCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (authorization) => {
      queryClient.setQueryData<ConnectorInvocationAuthorizationInventoryItem[]>(
        authorizationQueryKey,
        [authorization],
      );
      setAcknowledgedOptionKey("");
    },
  });
  const authorization = authorizationQuery.isError ? undefined : currentAuthorization;
  const canSubmit = acknowledgedOptionKey === effectiveSelectedOptionKey &&
    Boolean(selectedOption) && purpose.trim().length >= 20 &&
    !authorizationQuery.isFetching && !optionsQuery.isFetching && !mutation.isPending;
  const requestError = mutation.error ?? authorizationQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const refresh = () => {
    mutation.reset();
    setSelectedOptionKey("");
    setAcknowledgedOptionKey("");
    void authorizationQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section
      className="target-configuration-panel invocation-authorization-panel"
      aria-labelledby="invocation-authorization-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">SINGLE-USE CAPABILITY AUTHORIZATION</p>
          <h3 id="invocation-authorization-title">Invocation authorization</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {authorizationQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current invocation authorization...</span>
        </div>
      )}

      {!authorization && authorizationQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed invocation boundaries...</span>
        </div>
      )}

      {!authorization && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible invocation authorization option</strong>
            <span>
              A capability authority must publish a current signed profile, input envelope and
              policy for this exact closed target session. Atlas cannot create or edit that scope.
            </span>
          </div>
        </div>
      )}

      {!authorization && selectedOption && (
        <>
          <label>
            <span>Signed capability, profile, envelope and policy</span>
            <select
              aria-label="Signed capability, profile, envelope and policy"
              value={effectiveSelectedOptionKey}
              disabled={
                authorizationQuery.isFetching || optionsQuery.isFetching || mutation.isPending
              }
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
          <div className="mcp-builder-facts invocation-authorization-option-facts">
            <div><span>Permission</span><strong>{selectedOption.required_permission}</strong></div>
            <div><span>Input fields</span><strong>{selectedOption.input_envelope_field_count}</strong></div>
            <div><span>Maximum timeout</span><strong>{selectedOption.maximum_timeout_seconds}s</strong></div>
            <div><span>Maximum output</span><strong>{selectedOption.maximum_output_bytes} bytes</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed invocation authorization boundary">
            <div><span>Invocation profile</span><code>{selectedOption.invocation_profile_id}</code></div>
            <div><span>Input envelope</span><code>{selectedOption.input_envelope_id}</code></div>
            <div><span>Authorization policy</span><code>{selectedOption.authorization_policy_id}</code></div>
            <div><span>Assurance</span><strong>username and password</strong></div>
          </div>
          <label>
            <span>Authorization purpose</span>
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
              Authorization is short-lived, single-use, non-renewable and unconsumed. It grants
              no target connection, capability invocation, scheduling, result ingestion,
              execution, deployment or infrastructure mutation.
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
              : <ShieldCheck size={16} />}
            Authorize invocation
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
                  ? "Invocation authorization permission is required"
                  : sourceMissing
                    ? "Target session verification is no longer current"
                    : conflict
                      ? "Invocation authorization evidence changed"
                      : "Invocation authorization unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again with your username and password, then reload current evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : sourceMissing
                    ? "Refresh the target session and wait for current signed options."
                    : "Target-session lineage, capability, permission, signed profile, input envelope, policy, freshness, requested scope or separation failed."}
            </p>
          </div>
          {authenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : !authorizationFailed ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Refresh evidence
            </button>
          ) : null}
        </div>
      )}

      {authorization && (
        <div className="package-signing-record invocation-authorization-record">
          <div className="section-heading">
            <div>
              <strong>Invocation authorized</strong>
              <code>{authorization.authorization_id}</code>
            </div>
            <span className="state-badge success">
              <BadgeCheck size={14} /> single use
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Capability</span><strong>{authorization.capability_id}</strong></div>
            <div><span>Class</span><strong>{authorization.capability_class}</strong></div>
            <div><span>Permission</span><strong>verified</strong></div>
            <div><span>State</span><strong>unconsumed</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed invocation authorization evidence">
            <div><span>Profile digest</span><code>{authorization.invocation_profile_digest.slice(0, 16)}</code></div>
            <div><span>Envelope digest</span><code>{authorization.input_envelope_digest.slice(0, 16)}</code></div>
            <div><span>Policy digest</span><code>{authorization.authorization_policy_digest.slice(0, 16)}</code></div>
            <div><span>Expires</span><strong>{new Date(authorization.expires_at).toLocaleString()}</strong></div>
          </div>
          <p className="muted-copy">
            The exact capability is eligible for one later bounded invocation. No connection was
            opened, no capability was called, and no scheduling, execution or deployment authority
            exists.
          </p>
        </div>
      )}
    </section>
  );
}
