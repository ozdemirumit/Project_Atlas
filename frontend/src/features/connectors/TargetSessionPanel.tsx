import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Link2, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import type { ConnectorRuntimeActivationInventoryItem } from "../../api/runtimeActivations";
import {
  createConnectorTargetSessionVerification,
  getConnectorTargetSessionVerificationOptions,
  getConnectorTargetSessionVerifications,
  type ConnectorTargetSessionVerificationInventoryItem,
  type ConnectorTargetSessionVerificationOption,
} from "../../api/targetSessionVerifications";

function optionKey(option: ConnectorTargetSessionVerificationOption): string {
  return JSON.stringify([
    option.source_runtime_activation_id,
    option.source_runtime_activation_digest,
    option.session_profile_id,
    option.session_profile_digest,
    option.session_policy_id,
    option.session_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface TargetSessionPanelProps {
  activation: ConnectorRuntimeActivationInventoryItem;
  existingVerification?: ConnectorTargetSessionVerificationInventoryItem;
  onRequestEnterpriseLogin?: () => void;
  onVerificationCreated?: (
    verification: ConnectorTargetSessionVerificationInventoryItem,
  ) => void;
  sessionScopeKey: string;
}

export function TargetSessionPanel({
  activation,
  existingVerification,
  onRequestEnterpriseLogin,
  onVerificationCreated,
  sessionScopeKey,
}: TargetSessionPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Verify one bounded read-only target session, validate identity and TLS, then close every ephemeral handle.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const verificationQueryKey = [
    "connector-target-session-verifications",
    sessionScopeKey,
    activation.activation_id,
  ];
  const verificationQuery = useQuery({
    queryKey: verificationQueryKey,
    queryFn: () => getConnectorTargetSessionVerifications({
      sourceRuntimeActivationId: activation.activation_id,
    }),
    initialData: existingVerification ? [existingVerification] : undefined,
  });
  const currentVerification = verificationQuery.isError
    ? undefined
    : verificationQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "connector-target-session-verification-options",
      sessionScopeKey,
      activation.activation_id,
    ],
    queryFn: () => getConnectorTargetSessionVerificationOptions(activation.activation_id),
    enabled: verificationQuery.isSuccess && !currentVerification,
  });
  const options = optionsQuery.isError ? [] : (optionsQuery.data ?? []);
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorTargetSessionVerificationOption) => {
      const payload = await createConnectorTargetSessionVerification({
        activation,
        option,
        purpose,
      });
      onVerificationCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (verification) => {
      queryClient.setQueryData<ConnectorTargetSessionVerificationInventoryItem[]>(
        verificationQueryKey,
        [verification],
      );
      setAcknowledgedOptionKey("");
    },
  });
  const verification = verificationQuery.isError ? undefined : currentVerification;
  const canSubmit = acknowledgedOptionKey === effectiveSelectedOptionKey &&
    Boolean(selectedOption) && purpose.trim().length >= 20 &&
    !verificationQuery.isFetching && !optionsQuery.isFetching && !mutation.isPending;
  const requestError = mutation.error ?? verificationQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const refresh = () => {
    mutation.reset();
    setSelectedOptionKey("");
    setAcknowledgedOptionKey("");
    void verificationQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section
      className="target-configuration-panel target-session-panel"
      aria-labelledby="target-session-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">BOUNDED READ-ONLY CONNECTIVITY EVIDENCE</p>
          <h3 id="target-session-title">Target session verification</h3>
        </div>
        <Link2 size={24} />
      </div>

      {verificationQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current target session verification...</span>
        </div>
      )}

      {!verification && verificationQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed target session boundaries...</span>
        </div>
      )}

      {!verification && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible target session option</strong>
            <span>
              A target authority must publish a current signed profile and policy for this exact
              healthy runtime. Atlas cannot create, edit or weaken that boundary.
            </span>
          </div>
        </div>
      )}

      {!verification && selectedOption && (
        <>
          <label>
            <span>Signed target session profile and policy</span>
            <select
              aria-label="Signed target session profile and policy"
              value={effectiveSelectedOptionKey}
              disabled={verificationQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => {
                setSelectedOptionKey(event.target.value);
                setAcknowledgedOptionKey("");
              }}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.session_profile_id} / {option.session_policy_id}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts target-session-option-facts">
            <div><span>Target product</span><strong>{selectedOption.expected_target_product}</strong></div>
            <div><span>Protocol</span><strong>{selectedOption.protocol_classification}</strong></div>
            <div><span>Checks</span><strong>{selectedOption.connectivity_check_ids.length}</strong></div>
            <div><span>Assurance</span><strong>{selectedOption.required_assurance_level}</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed target session boundary">
            {selectedOption.connectivity_check_ids.map((check) => (
              <div key={check}><span>Bounded connectivity check</span><strong>{check}</strong></div>
            ))}
          </div>
          <label>
            <span>Verification purpose</span>
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
              Verification permits one bounded read-only connection and immediately closes its
              target session, delivery channel and secret lease. It grants no reusable session,
              capability invocation, execution, deployment, scheduling or infrastructure mutation
              authority.
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
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Link2 size={16} />}
            Verify target session
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
                  ? "Target session verification permission is required"
                  : sourceMissing
                    ? "Runtime activation is no longer current"
                    : conflict
                      ? "Target session evidence changed"
                      : "Target session verification unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again, then reload the current target session evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : sourceMissing
                    ? "Refresh runtime activation and wait for current signed options."
                    : "Runtime lineage, signed session profile and policy, freshness, network controls, TLS, target identity, read-only privilege, scope or separation failed."}
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

      {verification && (
        <div className="package-signing-record target-session-record">
          <div className="section-heading">
            <div><strong>Target session verified</strong><code>{verification.verification_id}</code></div>
            <span className="state-badge success"><BadgeCheck size={14} /> closed safely</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Target identity</span><strong>verified</strong></div>
            <div><span>TLS</span><strong>{verification.tls_classification}</strong></div>
            <div><span>Privilege</span><strong>read-only</strong></div>
            <div><span>Session</span><strong>closed</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed target session evidence">
            <div><span>Target identity digest</span><code>{verification.target_identity_digest.slice(0, 16)}</code></div>
            <div><span>Session profile digest</span><code>{verification.session_profile_digest.slice(0, 16)}</code></div>
            <div><span>Session policy digest</span><code>{verification.session_policy_digest.slice(0, 16)}</code></div>
            <div><span>Verified at</span><strong>{new Date(verification.verified_at).toLocaleString()}</strong></div>
          </div>
          <div className="runtime-health-probe-list" aria-label="Connectivity check outcomes">
            {verification.connectivity_check_results.map((check) => (
              <div key={check.check_id}>
                <BadgeCheck size={16} />
                <span>{check.check_id}</span>
                <strong>passed</strong>
              </div>
            ))}
          </div>
          <p className="muted-copy">
            Signed connectivity evidence is complete. The target session, delivery channel and
            lease are closed; no capability was invoked and no reusable connection remains.
          </p>
        </div>
      )}
    </section>
  );
}
