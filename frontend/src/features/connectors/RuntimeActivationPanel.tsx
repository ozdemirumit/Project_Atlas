import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, BadgeCheck, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorRuntimeActivation,
  getConnectorRuntimeActivationOptions,
  getConnectorRuntimeActivations,
  type ConnectorRuntimeActivationInventoryItem,
  type ConnectorRuntimeActivationOption,
} from "../../api/runtimeActivations";
import type { ConnectorSecretBrokerageAuthorizationInventoryItem } from "../../api/secretBrokerageAuthorizations";

function optionKey(option: ConnectorRuntimeActivationOption): string {
  return JSON.stringify([
    option.source_brokerage_authorization_id,
    option.source_brokerage_authorization_digest,
    option.activation_profile_id,
    option.activation_profile_digest,
    option.activation_policy_id,
    option.activation_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface RuntimeActivationPanelProps {
  brokerage: ConnectorSecretBrokerageAuthorizationInventoryItem;
  existingActivation?: ConnectorRuntimeActivationInventoryItem;
  onActivationCreated?: (activation: ConnectorRuntimeActivationInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function RuntimeActivationPanel({
  brokerage,
  existingActivation,
  onActivationCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: RuntimeActivationPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Activate the exact isolated connector runtime and verify signed local health without contacting a target.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const activationQueryKey = [
    "connector-runtime-activations",
    sessionScopeKey,
    brokerage.authorization_id,
  ];
  const activationQuery = useQuery({
    queryKey: activationQueryKey,
    queryFn: () => getConnectorRuntimeActivations({
      sourceBrokerageAuthorizationId: brokerage.authorization_id,
    }),
    initialData: existingActivation ? [existingActivation] : undefined,
  });
  const currentActivation = activationQuery.isError ? undefined : activationQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "connector-runtime-activation-options",
      sessionScopeKey,
      brokerage.authorization_id,
    ],
    queryFn: () => getConnectorRuntimeActivationOptions(brokerage.authorization_id),
    enabled: activationQuery.isSuccess && !currentActivation,
  });
  const options = optionsQuery.isError ? [] : (optionsQuery.data ?? []);
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorRuntimeActivationOption) => {
      const payload = await createConnectorRuntimeActivation({ brokerage, option, purpose });
      onActivationCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (activation) => {
      queryClient.setQueryData<ConnectorRuntimeActivationInventoryItem[]>(
        activationQueryKey,
        [activation],
      );
      setAcknowledgedOptionKey("");
    },
  });
  const activation = activationQuery.isError ? undefined : currentActivation;
  const canSubmit = acknowledgedOptionKey === effectiveSelectedOptionKey && Boolean(selectedOption) &&
    purpose.trim().length >= 20 && !activationQuery.isFetching && !optionsQuery.isFetching &&
    !mutation.isPending;
  const requestError = mutation.error ?? activationQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const refresh = () => {
    mutation.reset();
    setSelectedOptionKey("");
    setAcknowledgedOptionKey("");
    void activationQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section className="target-configuration-panel runtime-activation-panel" aria-labelledby="runtime-activation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED ISOLATED ACTIVATION BOUNDARY</p>
          <h3 id="runtime-activation-title">Runtime activation</h3>
        </div>
        <Activity size={24} />
      </div>

      {activationQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current runtime activation...</span>
        </div>
      )}

      {!activation && activationQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed activation boundaries...</span>
        </div>
      )}

      {!activation && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible runtime activation option</strong>
            <span>
              A runtime authority must publish a current signed profile and policy for this exact
              secret brokerage authorization. Atlas cannot create or weaken that boundary.
            </span>
          </div>
        </div>
      )}

      {!activation && selectedOption && (
        <>
          <label>
            <span>Signed activation profile and policy</span>
            <select
              aria-label="Signed activation profile and policy"
              value={effectiveSelectedOptionKey}
              disabled={activationQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => {
                setSelectedOptionKey(event.target.value);
                setAcknowledgedOptionKey("");
              }}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.activation_profile_id} / {option.activation_policy_id}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts runtime-activation-option-facts">
            <div><span>Assurance</span><strong>{selectedOption.required_assurance_level}</strong></div>
            <div><span>Result</span><strong>runtime healthy</strong></div>
            <div><span>Local probes</span><strong>{selectedOption.health_probe_ids.length}</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed local health boundary">
            {selectedOption.health_probe_ids.map((probe) => (
              <div key={probe}><span>Local health probe</span><strong>{probe}</strong></div>
            ))}
          </div>
          <label>
            <span>Activation purpose</span>
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
              Activation starts only the exact isolated runtime and signed local health probes. It
              grants no target connection, capability invocation, execution, deployment or
              infrastructure mutation authority.
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
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Activity size={16} />}
            Activate runtime
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
                  ? "Runtime activation permission is required"
                  : sourceMissing
                    ? "Secret brokerage is no longer current"
                    : conflict
                      ? "Runtime activation evidence changed"
                      : "Runtime activation unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again, then reload the current runtime activation evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : sourceMissing
                    ? "Refresh secret brokerage and wait for current signed options."
                    : "Brokerage lineage, signed activation profile and policy, freshness, scope, separation or local health evidence failed."}
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

      {activation && (
        <div className="package-signing-record runtime-activation-record">
          <div className="section-heading">
            <div><strong>Runtime healthy</strong><code>{activation.activation_id}</code></div>
            <span className="state-badge success"><BadgeCheck size={14} /> healthy</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Runtime</span><strong>isolated and healthy</strong></div>
            <div><span>Package</span><strong>loaded</strong></div>
            <div><span>Delivery channel</span><strong>closed</strong></div>
            <div><span>Target</span><strong>not connected</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed runtime activation evidence">
            <div><span>Activation profile</span><strong>{activation.activation_profile_id}</strong></div>
            <div><span>Activation policy</span><strong>{activation.activation_policy_id} / {activation.activation_policy_version}</strong></div>
            <div><span>Activation adapter</span><strong>{activation.activation_adapter_id}</strong></div>
            <div><span>Healthy at</span><strong>{new Date(activation.healthy_at).toLocaleString()}</strong></div>
          </div>
          <div className="runtime-health-probe-list" aria-label="Local health probe outcomes">
            {activation.health_probe_results.map((probe) => (
              <div key={probe.probe_id}>
                <BadgeCheck size={16} />
                <span>{probe.probe_id}</span>
                <strong>passed</strong>
              </div>
            ))}
          </div>
          <p className="muted-copy">
            Signed local health evidence is complete. No target session, capability invocation,
            execution, deployment or infrastructure change is authorized or available here.
          </p>
        </div>
      )}
    </section>
  );
}
