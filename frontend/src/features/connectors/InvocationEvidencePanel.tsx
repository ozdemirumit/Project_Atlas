import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Archive, BadgeCheck, LogIn, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { ConnectorBoundedInvocationInventoryItem } from "../../api/boundedInvocations";
import { ApiRequestError } from "../../api/client";
import {
  createConnectorInvocationEvidence,
  getConnectorInvocationEvidence,
  getConnectorInvocationEvidenceOptions,
  type ConnectorInvocationEvidenceInventoryItem,
  type ConnectorInvocationEvidenceOption,
} from "../../api/invocationEvidence";

function optionKey(option: ConnectorInvocationEvidenceOption): string {
  return JSON.stringify([
    option.source_invocation_id,
    option.source_invocation_digest,
    option.ingestion_policy_digest,
    option.retention_policy_id,
  ]);
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiRequestError && error.status === status;
}

function assuranceLabel(
  level: ConnectorInvocationEvidenceOption["required_assurance_level"],
): string {
  if (level === "hardware_backed") return "hardware-backed step-up";
  if (level === "multi_factor") return "multi-factor step-up";
  return "username and password";
}

interface InvocationEvidencePanelProps {
  invocation: ConnectorBoundedInvocationInventoryItem;
  existingEvidence?: ConnectorInvocationEvidenceInventoryItem;
  onEvidenceCreated?: (evidence: ConnectorInvocationEvidenceInventoryItem) => void;
  onRequestEnterpriseLogin?: () => void;
  sessionScopeKey: string;
}

export function InvocationEvidencePanel({
  invocation,
  existingEvidence,
  onEvidenceCreated,
  onRequestEnterpriseLogin,
  sessionScopeKey,
}: InvocationEvidencePanelProps) {
  const queryClient = useQueryClient();
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [purpose, setPurpose] = useState(
    "Preserve the exact governed connector observations as immutable evidence.",
  );
  const [acknowledgedOptionKey, setAcknowledgedOptionKey] = useState("");
  const [preservationAttempted, setPreservationAttempted] = useState(false);
  const inventoryQueryKey = [
    "connector-invocation-evidence",
    sessionScopeKey,
    invocation.invocation_id,
  ];
  const inventoryQuery = useQuery({
    queryKey: inventoryQueryKey,
    queryFn: () => getConnectorInvocationEvidence({
      sourceInvocationId: invocation.invocation_id,
    }),
    initialData: existingEvidence ? [existingEvidence] : undefined,
  });
  const currentEvidence = inventoryQuery.isError ? undefined : inventoryQuery.data?.[0];
  const optionsQuery = useQuery({
    queryKey: [
      "connector-invocation-evidence-options",
      sessionScopeKey,
      invocation.invocation_id,
    ],
    queryFn: () => getConnectorInvocationEvidenceOptions(invocation.invocation_id),
    enabled: inventoryQuery.isSuccess && !currentEvidence,
  });
  const options = optionsQuery.isError ? [] : (optionsQuery.data ?? []);
  const selectedOption = selectedOptionKey
    ? options.find((option) => optionKey(option) === selectedOptionKey)
    : options[0];
  const effectiveSelectedOptionKey = selectedOption ? optionKey(selectedOption) : "";
  const mutation = useMutation({
    mutationFn: async (option: ConnectorInvocationEvidenceOption) => {
      setPreservationAttempted(true);
      const payload = await createConnectorInvocationEvidence({ invocation, option, purpose });
      onEvidenceCreated?.(payload.data);
      return payload.data;
    },
    onSuccess: (evidence) => {
      queryClient.setQueryData<ConnectorInvocationEvidenceInventoryItem[]>(
        inventoryQueryKey,
        [evidence],
      );
      setAcknowledgedOptionKey("");
    },
  });
  const evidence = inventoryQuery.isError ? undefined : currentEvidence;
  const canSubmit = acknowledgedOptionKey === effectiveSelectedOptionKey &&
    Boolean(selectedOption) && purpose.trim().length >= 20 &&
    !preservationAttempted && !inventoryQuery.isFetching && !optionsQuery.isFetching &&
    !mutation.isPending;
  const requestError = evidence
    ? undefined
    : (mutation.error ?? inventoryQuery.error ?? optionsQuery.error);
  const authenticationFailed = hasStatus(requestError, 401);
  const authorizationFailed = hasStatus(requestError, 403);
  const sourceMissing = hasStatus(requestError, 404);
  const conflict = hasStatus(requestError, 409) || hasStatus(requestError, 422);
  const uncertain = hasStatus(requestError, 503) ||
    (preservationAttempted && mutation.isError);
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
      className="target-configuration-panel invocation-evidence-panel"
      aria-labelledby="invocation-evidence-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">IMMUTABLE OPERATIONAL EVIDENCE</p>
          <h3 id="invocation-evidence-title">Evidence preservation</h3>
        </div>
        <Archive size={24} />
      </div>

      {inventoryQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Checking immutable evidence inventory...</span>
        </div>
      )}

      {!evidence && inventoryQuery.isSuccess && optionsQuery.isLoading && (
        <div className="installed-mcp-status" role="status">
          <RefreshCw className="spin" size={18} />
          <span>Loading compatible signed preservation options...</span>
        </div>
      )}

      {!evidence && optionsQuery.isSuccess && options.length === 0 && !uncertain && (
        <div className="installed-mcp-empty compact">
          <AlertTriangle size={20} />
          <div>
            <strong>No compatible evidence-preservation option</strong>
            <span>
              The invocation may already be claimed, too old or no longer match a current signed
              policy. Atlas cannot create or edit preservation governance in the browser.
            </span>
          </div>
        </div>
      )}

      {!evidence && selectedOption && !preservationAttempted && (
        <>
          <label>
            <span>Signed evidence-preservation option</span>
            <select
              aria-label="Signed evidence-preservation option"
              value={effectiveSelectedOptionKey}
              disabled={inventoryQuery.isFetching || optionsQuery.isFetching || mutation.isPending}
              onChange={(event) => {
                setSelectedOptionKey(event.target.value);
                setAcknowledgedOptionKey("");
              }}
            >
              {options.map((option) => (
                <option key={optionKey(option)} value={optionKey(option)}>
                  {option.capability_id} / {option.classification}
                </option>
              ))}
            </select>
          </label>
          <div className="mcp-builder-facts invocation-evidence-option-facts">
            <div><span>Classification</span><strong>{selectedOption.classification.replace("classification.", "")}</strong></div>
            <div><span>Retention</span><strong>{selectedOption.retention_policy_id}</strong></div>
            <div><span>Item limit</span><strong>{selectedOption.maximum_evidence_items}</strong></div>
            <div><span>Byte limit</span><strong>{selectedOption.maximum_evidence_bytes}</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Signed evidence-preservation boundary">
            <div><span>Ingestion policy</span><code>{selectedOption.ingestion_policy_id}</code></div>
            <div><span>Policy version</span><strong>{selectedOption.ingestion_policy_version}</strong></div>
            <div><span>Policy expires</span><strong>{new Date(selectedOption.ingestion_policy_expires_at).toLocaleString()}</strong></div>
            <div><span>Assurance</span><strong>{assuranceLabel(selectedOption.required_assurance_level)}</strong></div>
          </div>
          <label>
            <span>Preservation purpose</span>
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
              The invocation is claimed before preservation and cannot be released or retried if
              the outcome is uncertain. Only immutable operational evidence is created; no
              knowledge, retrieval, model context, graph, scheduling, workflow, execution,
              deployment or infrastructure mutation authority is granted.
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
              : <Archive size={16} />}
            {mutation.isPending ? "Preserving evidence..." : "Preserve evidence"}
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
                  ? "Evidence-preservation permission is required"
                  : uncertain
                    ? "Evidence-preservation outcome is uncertain"
                    : sourceMissing
                      ? "Bounded invocation is no longer current"
                      : conflict
                        ? "Invocation evidence changed"
                        : "Evidence preservation unavailable"}
            </h3>
            <p>
              {authenticationFailed
                ? "Sign in again with your username and password, then reload current evidence."
                : authorizationFailed
                  ? "This account is missing the required role or scope."
                  : uncertain
                    ? "The invocation may already be claimed. Do not retry; reload only the authoritative evidence inventory."
                    : sourceMissing
                      ? "Reload the bounded invocation and wait for current signed options."
                      : "Invocation lineage, signed policy, assurance, separation, storage or cleanup evidence failed."}
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

      {evidence && (
        <div className="package-signing-record invocation-evidence-record">
          <div className="section-heading">
            <div>
              <strong>Evidence preserved</strong>
              <code>{evidence.evidence_package_id}</code>
            </div>
            <span className="state-badge success">
              <BadgeCheck size={14} /> immutable
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Classification</span><strong>{evidence.classification.replace("classification.", "")}</strong></div>
            <div><span>Retention</span><strong>{evidence.retention_policy_id}</strong></div>
            <div><span>Items</span><strong>{evidence.evidence_item_count}</strong></div>
            <div><span>Size</span><strong>{evidence.evidence_bytes} bytes</strong></div>
          </div>
          <div className="runtime-trust-boundary" aria-label="Immutable invocation evidence">
            <div><span>Content digest</span><code>{evidence.evidence_content_digest}</code></div>
            <div><span>Metadata digest</span><code>{evidence.evidence_metadata_digest}</code></div>
            <div><span>Encryption</span><strong>at rest</strong></div>
            <div><span>Ingested</span><strong>{new Date(evidence.ingested_at).toLocaleString()}</strong></div>
          </div>
          <p className="muted-copy">
            The exact redacted result is preserved under fixed access and retention governance.
            It is not approved knowledge, retrieval content, model context, a workflow
            continuation or operational authority.
          </p>
        </div>
      )}
    </section>
  );
}
