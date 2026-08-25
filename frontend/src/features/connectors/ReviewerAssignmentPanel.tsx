import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, ShieldCheck, UserRoundCheck } from "lucide-react";
import { useState } from "react";

import {
  createOperationalKnowledgeReviewerAssignment,
  type OperationalKnowledgeReviewerAssignmentSource,
} from "../../api/reviewerAssignments";
import { ProtectedInspectionLeasePanel } from "./ProtectedInspectionLeasePanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "caa0be534d5b205f4f5184da47a75e961aa9871e986e7392aa75d9bfb289cc58",
  "environment.test": "0c4a3437b5100b47edf7f7d9169f564d65d9d5410500ee5c40c98247fded7d95",
};

export function ReviewerAssignmentPanel({
  reviewRequest,
}: {
  reviewRequest: OperationalKnowledgeReviewerAssignmentSource;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-reviewer-assignment-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[reviewRequest.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Assign distinct eligible domain and security reviewers without exposing identity.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeReviewerAssignment });
  const assignment = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section className="target-configuration-panel" aria-labelledby="reviewer-assignment-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">REVIEW GOVERNANCE</p>
          <h3 id="reviewer-assignment-title">Reviewer assignment</h3>
        </div>
        <UserRoundCheck size={24} />
      </div>
      {!assignment && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Assignment policy ID</span>
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
              This assigns distinct eligible reviewers by policy. It does not reveal identity,
              open content, record a decision, approve, publish, or grant operational authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ reviewRequest, policyId, policyDigest, purpose })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <UserRoundCheck size={16} />
            )}
            Assign reviewers
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Reviewer assignment unavailable</h3>
            <p>
              Directory freshness, eligibility, separation of duties, or receipt integrity failed.
              A claimed uncertain attempt is not retried automatically.
            </p>
          </div>
        </div>
      )}
      {assignment && (
        <>
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{assignment.title}</strong>
              <code>{assignment.assignment_set_id}</code>
            </div>
            <span className="state-badge approved">
              <ShieldCheck size={14} /> reviewers assigned
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Domain reviewer</span>
              <strong>assigned</strong>
            </div>
            <div>
              <span>Security reviewer</span>
              <strong>assigned</strong>
            </div>
            <div>
              <span>Identity</span>
              <strong>protected</strong>
            </div>
            <div>
              <span>Content</span>
              <strong>locked</strong>
            </div>
          </div>
          <p className="muted-copy">
            <ShieldCheck size={14} /> Assignment references are encrypted and only salted subject
            digests are exposed. Protected inspection and review decisions remain separate stages.
          </p>
        </div>
        <ProtectedInspectionLeasePanel assignment={assignment} />
        </>
      )}
    </section>
  );
}
