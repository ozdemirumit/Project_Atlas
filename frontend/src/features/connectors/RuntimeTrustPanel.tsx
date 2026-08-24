import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, LogIn, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { ConnectorCapabilityEnablementInventoryItem } from "../../api/capabilityEnablements";
import { ApiRequestError } from "../../api/client";
import {
  createConnectorRuntimeTrustGrant,
  getConnectorRuntimeTrustGrantOptions,
  getConnectorRuntimeTrustGrants,
  type ConnectorRuntimeTrustGrantInventoryItem,
  type ConnectorRuntimeTrustGrantOption,
} from "../../api/runtimeTrustGrants";

function optionKey(option: ConnectorRuntimeTrustGrantOption): string {
  return JSON.stringify([
    option.source_enablement_id,
    option.source_enablement_digest,
    option.runtime_profile_id,
    option.runtime_profile_digest,
    option.trust_policy_id,
    option.trust_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface RuntimeTrustPanelProps {
  enablement: ConnectorCapabilityEnablementInventoryItem;
  existingGrant?: ConnectorRuntimeTrustGrantInventoryItem;
  onGrantCreated?: (grant: ConnectorRuntimeTrustGrantInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function RuntimeTrustPanel({
  enablement,
  existingGrant,
  onGrantCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: RuntimeTrustPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Bind the exact governed connector to its signed isolated runtime boundary without starting it or granting later operational authority.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const grantQueryKey = [
    "connector-runtime-trust-grants",
    sessionScopeKey,
    enablement.enablement_id,
  ];
  const grantQuery = useQuery({
    queryKey: grantQueryKey,
    queryFn: () => getConnectorRuntimeTrustGrants({ sourceEnablementId: enablement.enablement_id }),
    initialData: existingGrant ? [existingGrant] : undefined,
  });
  const currentGrant = grantQuery.data?.[0] ?? existingGrant;
  const optionsQuery = useQuery({
    queryKey: [
      "connector-runtime-trust-grant-options",
      sessionScopeKey,
      enablement.enablement_id,
    ],
    queryFn: () => getConnectorRuntimeTrustGrantOptions(enablement.enablement_id),
    enabled: grantQuery.isSuccess && !currentGrant,
  });
  const options = optionsQuery.data ?? [];
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorRuntimeTrustGrantOption) => {
      const payload = await createConnectorRuntimeTrustGrant({ enablement, option, purpose });
      onGrantCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (grant) => {
      queryClient.setQueryData<ConnectorRuntimeTrustGrantInventoryItem[]>(grantQueryKey, [grant]);
      setAcknowledgedOptionKey("");
    },
  });
  const grant = mutation.data ?? currentGrant;
  const canSubmit =
    acknowledgedOptionKey === effectiveSelectedOptionKey &&
    Boolean(selectedOption) &&
    purpose.trim().length >= 20 &&
    !grantQuery.isFetching &&
    !optionsQuery.isFetching &&
    !mutation.isPending;
  const requestError = mutation.error ?? grantQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const refresh = () => {
    mutation.reset();
    setSelectedOptionKey("");
    setAcknowledgedOptionKey("");
    void grantQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section className="target-configuration-panel runtime-trust-panel" aria-labelledby="runtime-trust-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED ISOLATED RUNTIME BOUNDARY</p>
          <h3 id="runtime-trust-title">Runtime trust</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {grantQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current runtime trust...</span>
        </div>
      )}

      {!grant && grantQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed runtime boundaries...</span>
        </div>
      )}

      {!grant && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible runtime trust option</strong>
            <span>
              A runtime authority must publish a current signed profile and policy for this exact
              capability enablement. Atlas cannot create or weaken that boundary.
            </span>
          </div>
        </div>
      )}

      {!grant && selectedOption && (
        <>
          <label>
            <span>Signed runtime profile and trust policy</span>
            <select
              aria-label="Signed runtime profile and trust policy"
              value={effectiveSelectedOptionKey}
              disabled={grantQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => {
                setSelectedOptionKey(event.target.value);
                setAcknowledgedOptionKey("");
              }}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.runtime_profile_id} / {option.trust_policy_id}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts runtime-trust-option-facts">
            <div><span>Runtime</span><strong>{selectedOption.runner_runtime_id}</strong></div>
            <div><span>Isolation</span><strong>{selectedOption.isolation_profile_id}</strong></div>
            <div><span>Assurance</span><strong>{selectedOption.required_assurance_level}</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed runtime boundary">
            <div><span>Workload identity</span><strong>{selectedOption.runner_workload_identity_id}</strong></div>
            <div><span>Filesystem</span><strong>{selectedOption.filesystem_policy_id}</strong></div>
            <div><span>Egress</span><strong>{selectedOption.egress_policy_id}</strong></div>
            <div><span>Telemetry</span><strong>{selectedOption.telemetry_policy_id}</strong></div>
            <div><span>Resource limits</span><strong>{selectedOption.resource_limit_profile_id}</strong></div>
          </div>
          <label>
            <span>Trust purpose</span>
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
              Trust binds only this signed isolated boundary. It does not start a process, load a
              package, resolve a secret, contact a target, invoke a capability, execute, deploy or
              mutate infrastructure.
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
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <ShieldCheck size={16} />}
            Establish runtime trust
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
                  ? "Runtime trust permission is required"
                  : sourceMissing
                    ? "Capability enablement is no longer current"
                    : conflict
                      ? "Runtime trust evidence changed"
                      : "Runtime trust unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again, then reload the current runtime trust evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : sourceMissing
                    ? "Refresh capability governance and wait for current signed options."
                    : "Enablement lineage, runtime profile, trust policy, freshness, scope or separation failed."}
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

      {grant && (
        <div className="package-signing-record runtime-trust-record">
          <div className="section-heading">
            <div><strong>Isolated boundary trusted</strong><code>{grant.grant_id}</code></div>
            <span className="state-badge success"><BadgeCheck size={14} /> trusted</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Runtime</span><strong>{grant.runner_runtime_id}</strong></div>
            <div><span>Runner</span><strong>not started</strong></div>
            <div><span>Secrets</span><strong>not resolved</strong></div>
            <div><span>Target</span><strong>not connected</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Trusted runtime boundary">
            <div><span>Runtime profile</span><strong>{grant.runtime_profile_id}</strong></div>
            <div><span>Workload identity</span><strong>{grant.runner_workload_identity_id}</strong></div>
            <div><span>Isolation</span><strong>{grant.isolation_profile_id}</strong></div>
            <div><span>Trust policy</span><strong>{grant.trust_policy_id} / {grant.trust_policy_version}</strong></div>
          </div>
          <p className="muted-copy">
            This immutable admission binds only the signed runtime boundary. No connector process,
            package load, secret resolution, target connection, capability invocation, execution,
            deployment or infrastructure change occurred.
          </p>
        </div>
      )}
    </section>
  );
}
