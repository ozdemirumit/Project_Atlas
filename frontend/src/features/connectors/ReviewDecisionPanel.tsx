import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import type { OperationalKnowledgeFindingPresentation } from "../../api/findingPresentations";
import type { OperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import type { OperationalKnowledgeReviewFinding } from "../../api/reviewFindings";
import {
  createOperationalKnowledgeTrackReviewDecision,
  type ReviewDisposition,
} from "../../api/reviewDecisions";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "881c16aedab87adda50e0abc0879a8f6a568f9e40e442673aad7f63dcc0c33ab",
};

const BASIS_CODES = {
  "review-track.domain": [
    "review-basis.technical-accuracy",
    "review-basis.applicability",
    "review-basis.operational-safety",
    "review-basis.evidence-quality",
  ],
  "review-track.security": [
    "review-basis.access-control",
    "review-basis.sensitive-data",
    "review-basis.unsafe-instruction",
    "review-basis.policy-compliance",
  ],
} as const;

export function ReviewDecisionPanel({
  lease,
  contentPresentation,
  finding,
  findingPresentation,
}: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  contentPresentation: OperationalKnowledgeProtectedContent;
  finding: OperationalKnowledgeReviewFinding;
  findingPresentation: OperationalKnowledgeFindingPresentation;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-track-review-decision-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[finding.environment_id] ?? "",
  );
  const [disposition, setDisposition] = useState<ReviewDisposition>(
    "review-disposition.changes-required",
  );
  const availableBasisCodes = useMemo(() => BASIS_CODES[finding.track_code], [finding.track_code]);
  const [basisCodes, setBasisCodes] = useState<string[]>([availableBasisCodes[0]]);
  const [purpose, setPurpose] = useState(
    "Record the accountable track decision for this exact presented finding packet.",
  );
  const [findingsAcknowledged, setFindingsAcknowledged] = useState(false);
  const [humanDecisionAcknowledged, setHumanDecisionAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeTrackReviewDecision });
  const decision = mutation.data?.data;
  const canSubmit =
    findingsAcknowledged &&
    humanDecisionAcknowledged &&
    authorityAcknowledged &&
    basisCodes.length >= 1 &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="review-decision-panel" aria-labelledby="review-decision-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">ACCOUNTABLE REVIEW</p>
          <h3 id="review-decision-title">Track review decision</h3>
        </div>
        <ShieldCheck size={24} />
      </div>
      {!decision && (
        <>
          <div className="review-decision-segment" role="group" aria-label="Review disposition">
            <button
              type="button"
              aria-pressed={disposition === "review-disposition.passed"}
              onClick={() => setDisposition("review-disposition.passed")}
            >
              <CheckCircle2 size={16} /> Passed
            </button>
            <button
              type="button"
              aria-pressed={disposition === "review-disposition.changes-required"}
              onClick={() => setDisposition("review-disposition.changes-required")}
            >
              <RotateCcw size={16} /> Changes required
            </button>
          </div>
          <fieldset className="review-decision-basis">
            <legend>Decision basis</legend>
            {availableBasisCodes.map((code) => (
              <label key={code}>
                <input
                  type="checkbox"
                  checked={basisCodes.includes(code)}
                  onChange={(event) =>
                    setBasisCodes((current) =>
                      event.target.checked
                        ? [...new Set([...current, code])]
                        : current.filter((item) => item !== code),
                    )
                  }
                />
                <span>{code.replace("review-basis.", "").replaceAll("-", " ")}</span>
              </label>
            ))}
          </fieldset>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Decision policy ID</span>
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
            <span>Decision purpose</span>
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
              checked={findingsAcknowledged}
              onChange={(event) => setFindingsAcknowledged(event.target.checked)}
            />
            <span>I reviewed the exact sealed findings shown for this track.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={humanDecisionAcknowledged}
              onChange={(event) => setHumanDecisionAcknowledged(event.target.checked)}
            />
            <span>This is my accountable human track decision.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>This decision is not knowledge approval or operational authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                lease,
                contentPresentation,
                finding,
                findingPresentation,
                policyId,
                policyDigest,
                disposition,
                basisCodes,
                purpose,
              })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : disposition === "review-disposition.passed" ? (
              <CheckCircle2 size={16} />
            ) : (
              <RotateCcw size={16} />
            )}
            Record track decision
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Review decision unavailable</h3>
            <p>The exact assignee, lease, browser binding, track cookie, and policy must remain current.</p>
          </div>
        </div>
      )}
      {decision && (
        <div className="review-decision-record">
          <div className="section-heading">
            <div>
              <strong>Track decision attested</strong>
              <code>{decision.decision_id}</code>
            </div>
            <span
              className={`state-badge ${decision.correction_required ? "pending" : "approved"}`}
            >
              {decision.correction_required ? <RotateCcw size={14} /> : <CheckCircle2 size={14} />}
              {decision.disposition_code.replace("review-disposition.", "").replace("-", " ")}
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Track</span><strong>{decision.track_code.replace("review-track.", "")}</strong></div>
            <div><span>Attestation</span><strong>verified</strong></div>
            <div><span>Correction</span><strong>{decision.correction_required ? "required" : "not required"}</strong></div>
            <div><span>Knowledge approval</span><strong>not granted</strong></div>
          </div>
          <p className="muted-copy">
            This immutable track decision grants no publication, retrieval, workflow, execution,
            deployment, or infrastructure mutation authority.
          </p>
        </div>
      )}
    </div>
  );
}
