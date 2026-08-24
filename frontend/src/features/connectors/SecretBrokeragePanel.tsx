import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, KeyRound, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import type { ConnectorRuntimeTrustGrantInventoryItem } from "../../api/runtimeTrustGrants";
import {
  createConnectorSecretBrokerageAuthorization,
  getConnectorSecretBrokerageAuthorizationOptions,
  getConnectorSecretBrokerageAuthorizations,
  type ConnectorSecretBrokerageAuthorizationInventoryItem,
  type ConnectorSecretBrokerageAuthorizationOption,
} from "../../api/secretBrokerageAuthorizations";

function optionKey(option: ConnectorSecretBrokerageAuthorizationOption): string {
  return JSON.stringify([
    option.source_runtime_trust_grant_id,
    option.source_runtime_trust_digest,
    option.brokerage_profile_id,
    option.brokerage_profile_digest,
    option.brokerage_policy_id,
    option.brokerage_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface SecretBrokeragePanelProps {
  runtimeTrust: ConnectorRuntimeTrustGrantInventoryItem;
  existingAuthorization?: ConnectorSecretBrokerageAuthorizationInventoryItem;
  onAuthorizationCreated?: (
    authorization: ConnectorSecretBrokerageAuthorizationInventoryItem,
  ) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function SecretBrokeragePanel({
  runtimeTrust,
  existingAuthorization,
  onAuthorizationCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: SecretBrokeragePanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Authorize the exact signed memory-only secret brokerage boundary without issuing a lease or resolving credentials.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const authorizationQueryKey = [
    "connector-secret-brokerage-authorizations",
    sessionScopeKey,
    runtimeTrust.grant_id,
  ];
  const authorizationQuery = useQuery({
    queryKey: authorizationQueryKey,
    queryFn: () => getConnectorSecretBrokerageAuthorizations({
      sourceRuntimeTrustGrantId: runtimeTrust.grant_id,
    }),
    initialData: existingAuthorization ? [existingAuthorization] : undefined,
  });
  const currentAuthorization = authorizationQuery.isError
    ? undefined
    : authorizationQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "connector-secret-brokerage-authorization-options",
      sessionScopeKey,
      runtimeTrust.grant_id,
    ],
    queryFn: () => getConnectorSecretBrokerageAuthorizationOptions(runtimeTrust.grant_id),
    enabled: authorizationQuery.isSuccess && !currentAuthorization,
  });
  const options = optionsQuery.isError ? [] : (optionsQuery.data ?? []);
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorSecretBrokerageAuthorizationOption) => {
      const payload = await createConnectorSecretBrokerageAuthorization({
        runtimeTrust,
        option,
        purpose,
      });
      onAuthorizationCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (authorization) => {
      queryClient.setQueryData<ConnectorSecretBrokerageAuthorizationInventoryItem[]>(
        authorizationQueryKey,
        [authorization],
      );
      setAcknowledgedOptionKey("");
    },
  });
  const authorization = authorizationQuery.isError
    ? undefined
    : (mutation.data ?? currentAuthorization);
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
    <section className="target-configuration-panel secret-brokerage-panel" aria-labelledby="secret-brokerage-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED MEMORY-ONLY BROKERAGE BOUNDARY</p>
          <h3 id="secret-brokerage-title">Secret brokerage</h3>
        </div>
        <KeyRound size={24} />
      </div>

      {authorizationQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current secret brokerage authorization...</span>
        </div>
      )}

      {!authorization && authorizationQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed brokerage boundaries...</span>
        </div>
      )}

      {!authorization && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible secret brokerage option</strong>
            <span>
              A brokerage authority must publish a current signed profile and policy for this exact
              runtime trust grant. Atlas cannot create or weaken that boundary.
            </span>
          </div>
        </div>
      )}

      {!authorization && selectedOption && (
        <>
          <label>
            <span>Signed brokerage profile and policy</span>
            <select
              aria-label="Signed brokerage profile and policy"
              value={effectiveSelectedOptionKey}
              disabled={authorizationQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => {
                setSelectedOptionKey(event.target.value);
                setAcknowledgedOptionKey("");
              }}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.brokerage_profile_id} / {option.brokerage_policy_id}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts secret-brokerage-option-facts">
            <div><span>Runtime profile</span><strong>{runtimeTrust.runtime_profile_id}</strong></div>
            <div><span>Assurance</span><strong>{selectedOption.required_assurance_level}</strong></div>
            <div><span>Delivery</span><strong>{selectedOption.delivery_policy_id}</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed secret brokerage boundary">
            <div><span>Lease policy</span><strong>{selectedOption.lease_policy_id}</strong></div>
            <div><span>Maximum lease</span><strong>{selectedOption.maximum_lease_seconds} seconds</strong></div>
            <div><span>Revocation</span><strong>{selectedOption.revocation_policy_id}</strong></div>
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
              Authorization governs only a future memory-only brokerage request. It does not issue
              a lease, resolve or deliver a secret, start a process, load a package, contact a
              target, invoke, execute, deploy or mutate infrastructure.
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
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <KeyRound size={16} />}
            Authorize secret brokerage
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
                  ? "Secret brokerage permission is required"
                  : sourceMissing
                    ? "Runtime trust is no longer current"
                    : conflict
                      ? "Secret brokerage evidence changed"
                      : "Secret brokerage unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again, then reload the current secret brokerage evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : sourceMissing
                    ? "Refresh runtime trust and wait for current signed options."
                    : "Runtime lineage, credential posture, signed profile and policy, freshness, scope or separation failed."}
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
        <div className="package-signing-record secret-brokerage-record">
          <div className="section-heading">
            <div><strong>Future brokerage governed</strong><code>{authorization.authorization_id}</code></div>
            <span className="state-badge success"><BadgeCheck size={14} /> authorized</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Credential class</span><strong>{authorization.credential_class}</strong></div>
            <div><span>Privilege</span><strong>{authorization.privilege_class}</strong></div>
            <div><span>Lease</span><strong>not issued</strong></div>
            <div><span>Secrets</span><strong>not resolved</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Governed secret brokerage boundary">
            <div><span>Brokerage profile</span><strong>{authorization.brokerage_profile_id}</strong></div>
            <div><span>Delivery policy</span><strong>{authorization.delivery_policy_id}</strong></div>
            <div><span>Revocation</span><strong>{authorization.revocation_policy_id}</strong></div>
            <div><span>Brokerage policy</span><strong>{authorization.brokerage_policy_id} / {authorization.brokerage_policy_version}</strong></div>
          </div>
          <p className="muted-copy">
            This immutable authorization records only a governed future brokerage boundary. No
            secret, lease, process, package, target session, invocation, execution, deployment or
            infrastructure change exists.
          </p>
        </div>
      )}
    </section>
  );
}
