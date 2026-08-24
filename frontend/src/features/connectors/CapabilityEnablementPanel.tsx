import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, LogIn, Power, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import {
  createConnectorCapabilityEnablement,
  getConnectorCapabilityEnablementOptions,
  getConnectorCapabilityEnablements,
  type ConnectorCapabilityEnablementInventoryItem,
  type ConnectorCapabilityEnablementOption,
} from "../../api/capabilityEnablements";
import { ApiRequestError } from "../../api/client";
import type {
  ConnectorConfigurationValidation,
  ConnectorConfigurationValidationInventoryItem,
} from "../../api/configurationValidations";

function optionKey(option: ConnectorCapabilityEnablementOption): string {
  return JSON.stringify([
    option.source_validation_id,
    option.source_validation_digest,
    option.capability_profile_id,
    option.capability_profile_digest,
    option.enablement_policy_id,
    option.enablement_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface CapabilityEnablementPanelProps {
  validation: ConnectorConfigurationValidation | ConnectorConfigurationValidationInventoryItem;
  existingEnablement?: ConnectorCapabilityEnablementInventoryItem;
  onEnablementCreated?: (enablement: ConnectorCapabilityEnablementInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function CapabilityEnablementPanel({
  validation,
  existingEnablement,
  onEnablementCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: CapabilityEnablementPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Apply the exact signed C0 and C1 capability policy without secret, runtime, execution, or deployment authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const enablementQueryKey = [
    "connector-capability-enablements",
    sessionScopeKey,
    validation.validation_id,
  ];
  const enablementQuery = useQuery({
    queryKey: enablementQueryKey,
    queryFn: () =>
      getConnectorCapabilityEnablements({ sourceValidationId: validation.validation_id }),
    initialData: existingEnablement ? [existingEnablement] : undefined,
  });
  const currentEnablement = enablementQuery.data?.[0] ?? existingEnablement;
  const optionsQuery = useQuery({
    queryKey: [
      "connector-capability-enablement-options",
      sessionScopeKey,
      validation.validation_id,
    ],
    queryFn: () => getConnectorCapabilityEnablementOptions(validation.validation_id),
    enabled: enablementQuery.isSuccess && !currentEnablement,
  });
  const options = optionsQuery.data ?? [];
  const selectedOption =
    options.find((option) => optionKey(option) === selectedOptionKey) ?? options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";

  const mutation = useMutation({
    mutationFn: async (option: ConnectorCapabilityEnablementOption) => {
      const payload = await createConnectorCapabilityEnablement({
        validation,
        option,
        purpose,
      });
      onEnablementCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (enablement) => {
      queryClient.setQueryData<ConnectorCapabilityEnablementInventoryItem[]>(
        enablementQueryKey,
        [enablement],
      );
      setAcknowledged(false);
    },
  });
  const enablement = mutation.data ?? currentEnablement;
  const canSubmit =
    acknowledged &&
    Boolean(selectedOption) &&
    purpose.trim().length >= 20 &&
    !enablementQuery.isFetching &&
    !optionsQuery.isFetching &&
    !mutation.isPending;
  const requestError = mutation.error ?? enablementQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const refresh = () => {
    mutation.reset();
    setSelectedOptionKey("");
    void enablementQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section
      className="target-configuration-panel capability-enablement-panel"
      aria-labelledby="capability-enablement-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED C0/C1 CAPABILITY GOVERNANCE</p>
          <h3 id="capability-enablement-title">Capability governance</h3>
        </div>
        <Power size={24} />
      </div>

      {enablementQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current capability governance...</span>
        </div>
      )}

      {!enablement && enablementQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed capability profiles...</span>
        </div>
      )}

      {!enablement && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible capability governance option</strong>
            <span>
              A capability authority must publish a current signed C0/C1 profile and policy for
              this exact configuration validation. Atlas cannot create or expand that authority.
            </span>
          </div>
        </div>
      )}

      {!enablement && selectedOption && (
        <>
          <label>
            <span>Governed capability profile and policy</span>
            <select
              aria-label="Governed capability profile and policy"
              value={effectiveSelectedOptionKey}
              disabled={enablementQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => setSelectedOptionKey(event.target.value)}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.capability_profile_id} / {option.enablement_policy_id}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts capability-enablement-option-facts">
            <div>
              <span>Capabilities</span>
              <strong>{selectedOption.capabilities.length}</strong>
            </div>
            <div>
              <span>Classes</span>
              <strong>
                {[...new Set(selectedOption.capabilities.map((item) => item.capability_class))]
                  .join(", ")}
              </strong>
            </div>
            <div>
              <span>Policy</span>
              <strong>{selectedOption.enablement_policy_version}</strong>
            </div>
            <div>
              <span>Assurance</span>
              <strong>{selectedOption.required_assurance_level}</strong>
            </div>
          </div>
          <div className="capability-enablement-capabilities" aria-label="Governed capabilities">
            {selectedOption.capabilities.map((capability) => (
              <div key={capability.capability_id}>
                <div>
                  <strong>{capability.capability_id}</strong>
                  <span>{capability.required_permission}</span>
                </div>
                <span className="state-badge neutral">{capability.capability_class}</span>
              </div>
            ))}
          </div>
          <label>
            <span>Enablement purpose</span>
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
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              Enablement selects only the exact signed C0/C1 metadata and grants no secret
              resolution, target connection, runtime trust, execution, deployment, or mutation
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
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <ShieldCheck size={16} />}
            Enable governed capabilities
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
                  ? "Capability governance permission is required"
                  : sourceMissing
                    ? "Governed capability source is no longer current"
                    : conflict
                      ? "Capability governance evidence changed"
                      : "Capability governance unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again, then reload the current capability evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : sourceMissing
                    ? "Refresh the configuration validation and wait for current signed options."
                    : "Validation lineage, profile, policy, manifest parity, freshness, scope or separation failed."}
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

      {enablement && (
        <div className="package-signing-record capability-enablement-record">
          <div className="section-heading">
            <div>
              <strong>
                {enablement.capabilities.length} governed{" "}
                {enablement.capabilities.length === 1 ? "capability" : "capabilities"}
              </strong>
              <code>{enablement.enablement_id}</code>
            </div>
            <span className="state-badge success"><BadgeCheck size={14} /> governed</span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Classes</span>
              <strong>
                {[...new Set(enablement.capabilities.map((item) => item.capability_class))].join(", ")}
              </strong>
            </div>
            <div><span>Runtime trust</span><strong>not granted</strong></div>
            <div><span>Execution</span><strong>not authorized</strong></div>
            <div><span>Deployment</span><strong>not approved</strong></div>
          </div>
          <div className="capability-enablement-capabilities" aria-label="Enabled governed capabilities">
            {enablement.capabilities.map((capability) => (
              <div key={capability.capability_id}>
                <div>
                  <strong>{capability.capability_id}</strong>
                  <span>{capability.required_permission}</span>
                </div>
                <span className="state-badge neutral">{capability.capability_class}</span>
              </div>
            ))}
          </div>
          <div className="credential-assignment-lineage">
            <span>Capability profile</span>
            <strong>{enablement.capability_profile_id}</strong>
            <span>Enablement policy</span>
            <strong>
              {enablement.enablement_policy_id} / {enablement.enablement_policy_version}
            </strong>
          </div>
          <p className="muted-copy">
            Administrative governance selected only signed manifest-bound capabilities. No secret,
            target connection, connector process, invocation, runtime trust, deployment, or
            infrastructure change occurred.
          </p>
        </div>
      )}
    </section>
  );
}
