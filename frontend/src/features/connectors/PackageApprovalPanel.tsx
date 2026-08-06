import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  UserX,
} from "lucide-react";
import { useState } from "react";

import {
  createConnectorPackageApprovalRequest,
  decideConnectorPackageApproval,
  type ConnectorPackageApprovalOutcome,
  type ConnectorPackageFinalValidation,
} from "../../api/connectors";
import { PublisherAttestationPanel } from "./PublisherAttestationPanel";

const OUTCOMES: Array<{ value: ConnectorPackageApprovalOutcome; label: string }> = [
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
  { value: "needs_evidence", label: "Request evidence" },
  { value: "defer", label: "Defer" },
];

const DEVELOPMENT_POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "7c2b227494a4b93aa1539887880783543e3ae05c898931c01028111a68a10dde",
  "environment.test": "0669bec01eadf9a5f97d7e3cbb8d6d03ec6895338132ac657613bd39111890d5",
};

type Props = {
  source: ConnectorPackageFinalValidation;
  subjectId: string;
};

export function PackageApprovalPanel({ source, subjectId }: Props) {
  const [policyId, setPolicyId] = useState("connector-package-approval-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    DEVELOPMENT_POLICY_DIGESTS[source.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Approve this exact validated package for publisher governance review.",
  );
  const [requestAcknowledged, setRequestAcknowledged] = useState(false);
  const [selectedOutcome, setSelectedOutcome] =
    useState<ConnectorPackageApprovalOutcome | null>(null);
  const [rationale, setRationale] = useState("");
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const requestMutation = useMutation({
    mutationFn: createConnectorPackageApprovalRequest,
    onSuccess: () => setRequestAcknowledged(false),
  });
  const decisionMutation = useMutation({
    mutationFn: decideConnectorPackageApproval,
    onSuccess: () => setDecisionAcknowledged(false),
  });
  const record = decisionMutation.data?.data ?? requestMutation.data?.data;
  const requesterIsCurrentSubject = record?.request.requested_by === subjectId;
  const pending = record?.state === "pending" && record.decision === null;
  const canRequest =
    requestAcknowledged &&
    purpose.trim().length >= 20 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !requestMutation.isPending;
  const canDecide =
    pending &&
    !requesterIsCurrentSubject &&
    selectedOutcome !== null &&
    rationale.trim().length >= 20 &&
    decisionAcknowledged &&
    !decisionMutation.isPending;

  return (
    <section className="package-approval-panel" aria-labelledby="package-approval-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">HUMAN APPROVAL</p>
          <h3 id="package-approval-title">Connector package decision</h3>
        </div>
        <ShieldCheck size={24} />
      </div>

      {!record && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Approval policy ID</span>
              <input value={policyId} onChange={(event) => setPolicyId(event.target.value)} />
            </label>
            <label>
              <span>Signed policy digest</span>
              <input
                value={policyDigest}
                onChange={(event) => setPolicyDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
          </div>
          <label>
            <span>Purpose</span>
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
              checked={requestAcknowledged}
              onChange={(event) => setRequestAcknowledged(event.target.checked)}
            />
            <span>This request is not an approval and grants no connector authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canRequest}
            onClick={() =>
              requestMutation.mutate({ source, policyId, policyDigest, purpose })
            }
          >
            {requestMutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <UserCheck size={16} />
            )}
            Submit approval request
          </button>
        </>
      )}

      {requestMutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Approval request unavailable</h3>
            <p>Exact evidence, policy, scope, freshness, or integrity did not reconcile.</p>
          </div>
        </div>
      )}

      {record && (
        <div className="package-approval-record">
          <div className="section-heading">
            <div>
              <strong>{record.request.request_id}</strong>
              <code>{record.request.canonical_digest}</code>
            </div>
            <span className={`state-badge ${record.approval_valid ? "healthy" : "warning"}`}>
              {record.approval_valid ? <CheckCircle2 size={14} /> : <Clock3 size={14} />}
              {record.state}
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Requester</span>
              <strong>{record.request.requested_by}</strong>
            </div>
            <div>
              <span>Policy</span>
              <strong>{record.request.approval_policy_version}</strong>
            </div>
            <div>
              <span>Stages</span>
              <strong>{`${record.request.passed_stage_count}/${record.request.stage_count}`}</strong>
            </div>
            <div>
              <span>Expires</span>
              <strong>{new Date(record.request.expires_at).toLocaleString()}</strong>
            </div>
          </div>

          {pending && requesterIsCurrentSubject && (
            <div className="workspace-message error-state" role="status">
              <UserX size={20} />
              <div>
                <h3>Independent approver required</h3>
                <p>{record.request.requested_by} cannot decide this request.</p>
              </div>
            </div>
          )}

          {pending && !requesterIsCurrentSubject && (
            <div className="package-approval-decision">
              <div className="package-approval-outcomes" role="group" aria-label="Decision">
                {OUTCOMES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    aria-pressed={selectedOutcome === item.value}
                    onClick={() => setSelectedOutcome(item.value)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <label>
                <span>Rationale</span>
                <textarea
                  value={rationale}
                  onChange={(event) => setRationale(event.target.value)}
                  rows={4}
                  maxLength={1000}
                />
              </label>
              <label className="approval-check">
                <input
                  type="checkbox"
                  checked={decisionAcknowledged}
                  onChange={(event) => setDecisionAcknowledged(event.target.checked)}
                />
                <span>This decision grants no signing, installation, runtime, or execution authority.</span>
              </label>
              <button
                className="primary-button"
                type="button"
                disabled={!canDecide}
                onClick={() => {
                  if (record && selectedOutcome) {
                    decisionMutation.mutate({ record, outcome: selectedOutcome, rationale });
                  }
                }}
              >
                {decisionMutation.isPending ? (
                  <RefreshCw className="spin" size={16} />
                ) : (
                  <UserCheck size={16} />
                )}
                Record decision
              </button>
            </div>
          )}

          {decisionMutation.isError && (
            <div className="workspace-message error-state" role="alert">
              <AlertTriangle size={20} />
              <div>
                <h3>Decision unavailable</h3>
                <p>Packet binding, actor separation, policy, or expiry validation failed.</p>
              </div>
            </div>
          )}

          {record.decision && (
            <div className="package-approval-decision-result">
              <strong>{record.decision.outcome}</strong>
              <span>{record.decision.decided_by}</span>
              <p>{record.decision.rationale}</p>
            </div>
          )}

          {record.approval_valid && record.eligible_for_publisher_governance && (
            <PublisherAttestationPanel approval={record} />
          )}
        </div>
      )}
    </section>
  );
}
