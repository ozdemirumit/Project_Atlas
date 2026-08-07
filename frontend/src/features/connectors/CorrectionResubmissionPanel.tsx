import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FilePenLine, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createOperationalKnowledgeCorrection } from "../../api/correctionResubmissions";
import type { OperationalKnowledgeTrackReviewDecision } from "../../api/reviewDecisions";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "bf82889bfba836f13350b88151d2c78af6b1807c72aa6c7c85750132637d2f13",
};

export function CorrectionResubmissionPanel({
  decision,
}: {
  decision: OperationalKnowledgeTrackReviewDecision;
}) {
  const [submissionId, setSubmissionId] = useState("");
  const [submissionDigest, setSubmissionDigest] = useState("");
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-correction-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[decision.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Create a corrected immutable draft and a fresh independent review generation.",
  );
  const [requirementsAcknowledged, setRequirementsAcknowledged] = useState(false);
  const [generationAcknowledged, setGenerationAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeCorrection });
  const correction = mutation.data?.data;
  const canSubmit =
    decision.all_tracks_decided &&
    decision.any_correction_required &&
    requirementsAcknowledged &&
    generationAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(submissionId) &&
    /^[a-f0-9]{64}$/.test(submissionDigest) &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="correction-resubmission-panel" aria-labelledby="correction-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">GOVERNED CORRECTION</p>
          <h3 id="correction-title">Correct and resubmit</h3>
        </div>
        <FilePenLine size={24} />
      </div>
      {!correction && (
        <>
          <div className="correction-lineage" aria-label="Review generation status">
            {decision.track_decisions.map((item) => (
              <div key={item.track_code}>
                <span>{item.track_code.replace("review-track.", "")} track</span>
                <strong>{item.disposition_code.replace("review-disposition.", "").replace("-", " ")}</strong>
              </div>
            ))}
          </div>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Trusted correction submission ID</span>
              <input value={submissionId} onChange={(event) => setSubmissionId(event.target.value)} />
            </label>
            <label>
              <span>Submission digest</span>
              <input
                value={submissionDigest}
                onChange={(event) => setSubmissionDigest(event.target.value)}
                spellCheck={false}
              />
            </label>
            <label>
              <span>Correction policy ID</span>
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
            <span>Correction purpose</span>
            <textarea
              value={purpose}
              rows={3}
              maxLength={1000}
              onChange={(event) => setPurpose(event.target.value)}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={requirementsAcknowledged}
              onChange={(event) => setRequirementsAcknowledged(event.target.checked)}
            />
            <span>The trusted submission addresses the exact review requirements.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={generationAcknowledged}
              onChange={(event) => setGenerationAcknowledged(event.target.checked)}
            />
            <span>A new immutable draft and independent review generation will be created.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>This correction grants no approval, publication, or operational authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                decision,
                correctionSubmissionId: submissionId,
                correctionSubmissionDigest: submissionDigest,
                policyId,
                policyDigest,
                purpose,
              })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <RotateCcw size={16} />}
            Create new review generation
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Correction unavailable</h3>
            <p>Both track decisions, exact curator authority, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {correction && (
        <div className="correction-record">
          <div className="section-heading">
            <div>
              <strong>Review generation resubmitted</strong>
              <code>{correction.correction_id}</code>
            </div>
            <span className="state-badge neutral"><ShieldCheck size={14} /> generation {correction.review_generation}</span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>New draft</span><strong>immutable</strong></div>
            <div><span>Domain review</span><strong>awaiting reviewer</strong></div>
            <div><span>Security review</span><strong>awaiting reviewer</strong></div>
            <div><span>Knowledge approval</span><strong>not granted</strong></div>
          </div>
          <p className="muted-copy">
            Prior draft, findings, and decisions remain immutable. The new generation grants no
            publication, retrieval, workflow, execution, deployment, or mutation authority.
          </p>
        </div>
      )}
    </div>
  );
}
