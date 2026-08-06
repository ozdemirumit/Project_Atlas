import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, LockKeyhole, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { OperationalEvidenceKnowledgeDraft } from "../../api/evidenceDrafts";
import { createOperationalKnowledgeReviewRequest } from "../../api/knowledgeReviewRequests";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "370a20b5f82bfdc82efdf3ae1036663761094475b66cd562e0aa75bc112d0dd1",
  "environment.test": "5b2a963ed906e0dd1ea9c3968dc3feda84acf1b30e65490acfcb2dd5f2a4b060",
};

export function KnowledgeDraftReviewRequestPanel({
  draft,
}: {
  draft: OperationalEvidenceKnowledgeDraft;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-review-request-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[draft.environment_id] ?? "");
  const [purpose, setPurpose] = useState(
    "Request independent domain and security review for this exact immutable draft.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeReviewRequest });
  const reviewRequest = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section className="target-configuration-panel" aria-labelledby="knowledge-review-request-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">REVIEW ORCHESTRATION</p>
          <h3 id="knowledge-review-request-title">Knowledge review request</h3>
        </div>
        <ClipboardCheck size={24} />
      </div>
      {!reviewRequest && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Review policy ID</span>
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
            <span>Review purpose</span>
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
              This creates unassigned domain and security review work only. It does not expose
              content, record a decision, approve, publish, index, or grant operational authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ draft, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ClipboardCheck size={16} />
            )}
            Submit for review
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Review request unavailable</h3>
            <p>
              Draft lineage, inherited governance, review routing, manifest integrity, or cleanup
              validation failed. A claimed uncertain attempt is not retried automatically.
            </p>
          </div>
        </div>
      )}
      {reviewRequest && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{reviewRequest.title}</strong>
              <code>{reviewRequest.review_request_id}</code>
            </div>
            <span className="state-badge pending">
              <ClipboardCheck size={14} /> awaiting reviewers
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Domain review</span>
              <strong>awaiting reviewer</strong>
            </div>
            <div>
              <span>Security review</span>
              <strong>awaiting reviewer</strong>
            </div>
            <div>
              <span>Assignment</span>
              <strong>policy controlled</strong>
            </div>
            <div>
              <span>Content access</span>
              <strong>locked</strong>
            </div>
          </div>
          <p className="muted-copy">
            <LockKeyhole size={14} /> The request contains routing metadata only. Protected
            inspection, decisions, correction, approval, indexing, retrieval, and model use remain
            separate controlled stages.
          </p>
        </div>
      )}
    </section>
  );
}
