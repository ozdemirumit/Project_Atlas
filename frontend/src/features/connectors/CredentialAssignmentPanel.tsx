import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, KeyRound, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "../../api/client";
import {
  createConnectorCredentialAssignment,
  getConnectorCredentialAssignmentOptions,
  getConnectorCredentialAssignments,
  type ConnectorCredentialAssignment,
  type ConnectorCredentialAssignmentInventoryItem,
  type ConnectorCredentialAssignmentOption,
} from "../../api/credentialAssignments";
import type { ConnectorTargetConfigurationBinding } from "../../api/targetConfigurations";

function optionKey(option: ConnectorCredentialAssignmentOption): string {
  return JSON.stringify([option.credential_profile_id, option.credential_policy_id]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

interface CredentialAssignmentPanelProps {
  binding: ConnectorTargetConfigurationBinding;
  existingAssignment?: ConnectorCredentialAssignmentInventoryItem;
  onAssignmentCreated?: (assignment: ConnectorCredentialAssignment) => void;
  onRequestEnterpriseLogin?: () => void;
}

export function CredentialAssignmentPanel({
  binding,
  existingAssignment,
  onAssignmentCreated,
  onRequestEnterpriseLogin,
}: CredentialAssignmentPanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Assign governed credential metadata without secret access, enablement, or runtime authority.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const assignmentQuery = useQuery({
    queryKey: ["connector-credential-assignments", binding.binding_id],
    queryFn: () =>
      getConnectorCredentialAssignments({ sourceTargetBindingId: binding.binding_id }),
    enabled: !existingAssignment,
    initialData: existingAssignment ? [existingAssignment] : undefined,
  });
  const currentAssignment = existingAssignment ?? assignmentQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: ["connector-credential-assignment-options", binding.binding_id],
    queryFn: () => getConnectorCredentialAssignmentOptions(binding.binding_id),
    enabled: assignmentQuery.isSuccess && !currentAssignment,
  });
  const options = optionsQuery.data ?? [];
  const selectedOption =
    options.find((option) => optionKey(option) === selectedOptionKey) ?? options[0];
  const mutation = useMutation({
    mutationFn: createConnectorCredentialAssignment,
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["connector-credential-assignments"] });
      onAssignmentCreated?.(payload.data);
    },
  });
  const assignment = mutation.data?.data ?? currentAssignment;
  const canSubmit =
    acknowledged && Boolean(selectedOption) && purpose.trim().length >= 20 && !mutation.isPending;
  const requestError = mutation.error ?? assignmentQuery.error ?? optionsQuery.error;
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const recordMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409);
  const refresh = () => {
    mutation.reset();
    void assignmentQuery.refetch();
    void optionsQuery.refetch();
  };

  return (
    <section
      className="target-configuration-panel credential-assignment-panel"
      aria-labelledby="credential-assignment-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">SIGNED CREDENTIAL PROFILE</p>
          <h3 id="credential-assignment-title">Governed credential assignment</h3>
        </div>
        <KeyRound size={24} />
      </div>

      {!existingAssignment && assignmentQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking current credential assignment...</span>
        </div>
      )}

      {!assignment && assignmentQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible governed credential profiles...</span>
        </div>
      )}

      {!assignment && optionsQuery.isSuccess && options.length === 0 && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible governed credential profile</strong>
            <span>
              Credential governance must publish a current signed profile and policy for this
              target binding, connector, scope, and account.
            </span>
          </div>
        </div>
      )}

      {!assignment && selectedOption && (
        <>
          <label>
            <span>Governed credential profile</span>
            <select
              value={optionKey(selectedOption)}
              onChange={(event) => setSelectedOptionKey(event.target.value)}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.credential_class} / {option.vendor_role} / {option.privilege_class}
                </option>
              ))}
            </select>
          </label>
          <div
            className="target-configuration-option-facts"
            aria-label="Selected credential evidence"
          >
            <div>
              <span>Authentication</span>
              <strong>{selectedOption.authentication_method}</strong>
            </div>
            <div>
              <span>Profile</span>
              <code>{selectedOption.credential_profile_id}</code>
            </div>
            <div>
              <span>Policy</span>
              <code>{selectedOption.credential_policy_id}</code>
            </div>
            <div>
              <span>Resulting state</span>
              <strong>Disabled / credentials assigned</strong>
            </div>
          </div>
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
              Assignment grants no secret access, credential resolution, capability, enablement,
              runtime, execution, or deployment authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                binding,
                credentialProfileId: selectedOption.credential_profile_id,
                credentialProfileDigest: selectedOption.credential_profile_digest,
                policyId: selectedOption.credential_policy_id,
                policyDigest: selectedOption.credential_policy_digest,
                purpose,
              })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <KeyRound size={16} />
            )}
            Assign credential profile
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
                  ? "Credential assignment permission is required"
                  : recordMissing
                    ? "Credential assignment evidence is unavailable"
                    : conflict
                      ? "Credential assignment changed"
                      : "Credential assignment unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again before managing credential metadata."
                : authorizationFailed
                  ? "This account is missing the required role, scope, or separation."
                  : recordMissing
                    ? "Refresh the MCP inventory and confirm that the target binding still exists."
                    : conflict
                      ? "Refresh the authoritative assignment and compatible-profile inventory."
                      : "Target lineage, signed credential evidence, policy, scope, rotation, or freshness failed."}
            </p>
          </div>
          {authenticationFailed && onRequestEnterpriseLogin ? (
            <button type="button" onClick={onRequestEnterpriseLogin}>
              <LogIn size={15} /> Sign in again
            </button>
          ) : conflict || recordMissing ? (
            <button type="button" onClick={refresh}>
              <RefreshCw size={15} /> Refresh credential data
            </button>
          ) : null}
        </div>
      )}

      {assignment && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{assignment.credential_class}</strong>
              <code>{assignment.assignment_id}</code>
            </div>
            <span className="state-badge neutral">
              <BadgeCheck size={14} /> assigned
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Authentication</span>
              <strong>{assignment.authentication_method}</strong>
            </div>
            <div>
              <span>Privilege</span>
              <strong>{assignment.privilege_class}</strong>
            </div>
            <div>
              <span>Rotation</span>
              <strong>{assignment.rotation_state}</strong>
            </div>
            <div>
              <span>State</span>
              <strong>Disabled / credentials assigned</strong>
            </div>
          </div>
          <p className="muted-copy">
            Only governed credential metadata is assigned. Secret internals, values, credential
            resolution, connectivity validation, capabilities, and runtime remain unavailable here.
          </p>
        </div>
      )}
    </section>
  );
}
