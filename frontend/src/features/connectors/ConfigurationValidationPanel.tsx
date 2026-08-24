import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, LogIn, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorConfigurationValidation,
  getConnectorConfigurationValidationOptions,
  getConnectorConfigurationValidations,
  type ConnectorConfigurationValidation,
  type ConnectorConfigurationValidationInventoryItem,
  type ConnectorConfigurationValidationOption,
} from "../../api/configurationValidations";
import type {
  ConnectorCredentialAssignment,
  ConnectorCredentialAssignmentInventoryItem,
} from "../../api/credentialAssignments";

function optionKey(option: ConnectorConfigurationValidationOption): string {
  return JSON.stringify([
    option.evidence_id,
    option.evidence_digest,
    option.validation_policy_id,
    option.validation_policy_digest,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface ConfigurationValidationPanelProps {
  assignment: ConnectorCredentialAssignment | ConnectorCredentialAssignmentInventoryItem;
  existingValidation?: ConnectorConfigurationValidationInventoryItem;
  onValidationCreated?: (validation: ConnectorConfigurationValidation) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function ConfigurationValidationPanel({
  assignment,
  existingValidation,
  onValidationCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: ConfigurationValidationPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Verify signed bounded configuration evidence without secret, network, enablement, or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const validationQuery = useQuery({
    queryKey: ["connector-configuration-validations", sessionScopeKey, assignment.assignment_id],
    queryFn: () =>
      getConnectorConfigurationValidations({ sourceAssignmentId: assignment.assignment_id }),
    enabled: !existingValidation,
    initialData: existingValidation ? [existingValidation] : undefined,
  });
  const currentValidation = existingValidation ?? validationQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: ["connector-configuration-validation-options", sessionScopeKey, assignment.assignment_id],
    queryFn: () => getConnectorConfigurationValidationOptions(assignment.assignment_id),
    enabled: validationQuery.isSuccess && !currentValidation,
  });
  const options = optionsQuery.data ?? [];
  const selectedOption =
    options.find((option) => optionKey(option) === selectedOptionKey) ?? options[0];
  const mutation = useMutation({
    mutationFn: createConnectorConfigurationValidation,
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["connector-configuration-validations"] });
      onValidationCreated?.(payload.data);
    },
  });
  const validation = mutation.data?.data ?? currentValidation;
  const canSubmit =
    acknowledged && Boolean(selectedOption) && purpose.trim().length >= 20 && !mutation.isPending;
  const requestError = mutation.error ?? validationQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const recordMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const refresh = () => {
    mutation.reset();
    void validationQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section
      className="target-configuration-panel configuration-validation-panel"
      aria-labelledby="configuration-validation-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED READ-ONLY PROBE EVIDENCE</p>
          <h3 id="configuration-validation-title">Configuration validation</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {!existingValidation && validationQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current configuration validation...</span>
        </div>
      )}

      {!validation && validationQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed probe evidence...</span>
        </div>
      )}

      {!validation && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible signed probe evidence</strong>
            <span>
              An isolated probe authority must publish current, read-only evidence and policy for
              this exact assignment. Atlas does not run the probe or contact infrastructure.
            </span>
          </div>
        </div>
      )}

      {!validation && selectedOption && (
        <>
          <label>
            <span>Governed evidence and policy</span>
            <select
              aria-label="Governed evidence and policy"
              value={optionKey(selectedOption)}
              onChange={(event) => setSelectedOptionKey(event.target.value)}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.evidence_id} / {option.validation_policy_id}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts configuration-validation-option-facts">
            <div><span>Configuration</span><strong>{selectedOption.configuration_result}</strong></div>
            <div><span>Connectivity</span><strong>{selectedOption.connectivity_result}</strong></div>
            <div><span>TLS</span><strong>{selectedOption.tls_result}</strong></div>
            <div><span>Authorization</span><strong>{selectedOption.authorization_result}</strong></div>
            <div><span>Product identity</span><strong>{selectedOption.product_identity_result}</strong></div>
            <div><span>Observed</span><strong>{new Date(selectedOption.evidence_observed_at).toLocaleString()}</strong></div>
          </div>
          <label>
            <span>Validation purpose</span>
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
              Validation grants no target access, secret resolution, capability, enablement,
              runtime, execution, deployment, or mutation authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => {
              if (selectedOption) {
                mutation.mutate({ assignment, option: selectedOption, purpose });
              }
            }}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <ShieldCheck size={16} />}
            Verify signed evidence
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
                  ? "Configuration validation permission is required"
                  : recordMissing
                    ? "Governed validation source is no longer current"
                    : conflict
                      ? "Configuration validation evidence changed"
                      : "Configuration validation unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again, then reload the current validation evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : recordMissing
                    ? "Refresh the assignment and wait for current signed probe evidence."
                    : "Assignment lineage, evidence, policy, freshness, scope or separation failed."}
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

      {validation && (
        <div className="package-signing-record configuration-validation-record">
          <div className="section-heading">
            <div>
              <strong>{validation.configuration_result}</strong>
              <code>{validation.validation_id}</code>
            </div>
            <span className="state-badge neutral"><BadgeCheck size={14} /> verified</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Connectivity</span><strong>{validation.connectivity_result}</strong></div>
            <div><span>TLS</span><strong>{validation.tls_result}</strong></div>
            <div><span>Endpoint identity</span><strong>{validation.endpoint_identity_result}</strong></div>
            <div><span>Authentication</span><strong>{validation.authentication_result}</strong></div>
            <div><span>Authorization</span><strong>{validation.authorization_result}</strong></div>
            <div><span>Product identity</span><strong>{validation.product_identity_result}</strong></div>
            <div><span>Latency</span><strong>{validation.latency_band}</strong></div>
            <div><span>Observed</span><strong>{new Date(validation.evidence_observed_at).toLocaleString()}</strong></div>
          </div>
          <div className="credential-assignment-lineage">
            <span>Probe evidence</span>
            <strong>{validation.evidence_id}</strong>
            <span>Validation policy</span>
            <strong>{validation.validation_policy_id} / {validation.validation_policy_version}</strong>
          </div>
          <p className="muted-copy">
            Only signed bounded classifications were verified. Target coordinates, secret
            material, raw probe output, capability enablement and runtime remain unavailable.
          </p>
        </div>
      )}
    </section>
  );
}
