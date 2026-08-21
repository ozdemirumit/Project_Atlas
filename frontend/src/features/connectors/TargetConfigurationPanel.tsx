import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Link2, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import type { ConnectorInstanceRecord } from "../../api/connectorInstances";
import {
  createConnectorTargetConfiguration,
  getConnectorTargetConfigurationOptions,
  getConnectorTargetConfigurations,
  type ConnectorTargetConfigurationBinding,
  type ConnectorTargetConfigurationOption,
} from "../../api/targetConfigurations";

function optionKey(option: ConnectorTargetConfigurationOption): string {
  return `${option.target_profile_id}:${option.configuration_policy_id}`;
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface TargetConfigurationPanelProps {
  existingBinding?: ConnectorTargetConfigurationBinding;
  instance: ConnectorInstanceRecord;
  onBindingCreated?: (binding: ConnectorTargetConfigurationBinding) => void;
  onRequestEnterpriseLogin?: () => void;
}

export function TargetConfigurationPanel({
  existingBinding,
  instance,
  onBindingCreated,
  onRequestEnterpriseLogin,
}: TargetConfigurationPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Bind governed target metadata without credentials, enablement, or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const bindingQuery = useQuery({
    queryKey: ["connector-target-bindings", instance.record_id],
    queryFn: () =>
      getConnectorTargetConfigurations({ sourceInstanceRecordId: instance.record_id }),
    enabled: !existingBinding,
    initialData: existingBinding ? [existingBinding] : undefined,
  });
  const currentBinding = existingBinding ?? bindingQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: ["connector-target-options", instance.record_id],
    queryFn: () => getConnectorTargetConfigurationOptions(instance.record_id),
    enabled: bindingQuery.isSuccess && !currentBinding,
  });
  const options = optionsQuery.data ?? [];
  const selectedOption =
    options.find((option) => optionKey(option) === selectedOptionKey) ?? options[0];
  const mutation = useMutation({
    mutationFn: createConnectorTargetConfiguration,
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["connector-target-bindings"] });
      onBindingCreated?.(payload.data);
    },
  });
  const binding = mutation.data?.data ?? currentBinding;
  const canSubmit =
    acknowledged && Boolean(selectedOption) && purpose.trim().length >= 20 && !mutation.isPending;
  const requestError = mutation.error ?? bindingQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const recordMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409);
  const refresh = () => {
    mutation.reset();
    void bindingQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section className="target-configuration-panel" aria-labelledby="target-configuration-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED TARGET PROFILE</p>
          <h3 id="target-configuration-title">Governed target binding</h3>
        </div>
        <Link2 size={24} />
      </div>

      {!existingBinding && bindingQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current target binding...</span>
        </div>
      )}

      {!binding && bindingQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible governed targets...</span>
        </div>
      )}

      {!binding && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible governed target</strong>
            <span>
              Inventory governance must publish a current signed target profile and policy for this
              connector, scope, and account.
            </span>
          </div>
        </div>
      )}

      {!binding && selectedOption && (
        <>
          <label>
            <span>Governed target</span>
            <select
              value={optionKey(selectedOption)}
              onChange={(event) => setSelectedOptionKey(event.target.value)}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.target_product} / {option.site_id} / {option.target_version}
                </option>
              ))}
            </select>
          </label>
          <div className="target-configuration-option-facts" aria-label="Selected target evidence">
            <div>
              <span>Target type</span>
              <strong>{selectedOption.target_type}</strong>
            </div>
            <div>
              <span>Profile</span>
              <code>{selectedOption.target_profile_id}</code>
            </div>
            <div>
              <span>Policy</span>
              <code>{selectedOption.configuration_policy_id}</code>
            </div>
            <div>
              <span>Resulting state</span>
              <strong>Disabled / target configured</strong>
            </div>
          </div>
          <label>
            <span>Binding purpose</span>
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
              Binding grants no credential, capability, enablement, runtime, execution, or
              deployment authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                instance,
                targetProfileId: selectedOption.target_profile_id,
                targetProfileDigest: selectedOption.target_profile_digest,
                policyId: selectedOption.configuration_policy_id,
                policyDigest: selectedOption.configuration_policy_digest,
                purpose,
              })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <Link2 size={16} />
            )}
            Bind governed target
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
                  ? "Target configuration permission is required"
                  : recordMissing
                    ? "Target configuration evidence is unavailable"
                    : conflict
                      ? "Target configuration changed"
                      : "Target binding unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again before managing target metadata."
                : authorizationFailed
                  ? "This account is missing the required role, scope, or separation."
                  : recordMissing
                    ? "Refresh the MCP inventory and confirm that the instance still exists."
                    : conflict
                      ? "Refresh the authoritative binding and target-option inventory."
                      : "Instance lineage, signed target evidence, policy, scope, or freshness failed."}
            </p>
          </div>
          {authenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : conflict || recordMissing ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Refresh target data
            </button>
          ) : null}
        </div>
      )}

      {binding && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{binding.target_product}</strong>
              <code>{binding.binding_id}</code>
            </div>
            <span className="state-badge neutral">
              <BadgeCheck size={14} /> configured
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Instance</span>
              <strong>{binding.instance_key}</strong>
            </div>
            <div>
              <span>Site</span>
              <strong>{binding.site_id}</strong>
            </div>
            <div>
              <span>Target type</span>
              <strong>{binding.target_type}</strong>
            </div>
            <div>
              <span>State</span>
              <strong>Disabled / target configured</strong>
            </div>
          </div>
          <p className="muted-copy">
            The governed target metadata is bound. Endpoint, trust, route, credentials,
            connectivity, capabilities, and runtime remain unavailable here.
          </p>
        </div>
      )}
    </section>
  );
}
