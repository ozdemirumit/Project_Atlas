import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import type { RecommendationFindingPresentation } from "../../api/recommendationFindingPresentations";
import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";
import type { RecommendationHumanReviewFinding } from "../../api/recommendationReviewFindings";
import {
  createRecommendationTrackReviewDecision,
  type RecommendationReviewDisposition,
} from "../../api/recommendationReviewDecisions";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "d3c8affc6491b472c26a156210f69209cd9c75d85ab08274925645ca525aa165",
};

const BASIS_CODES = {
  "review-track.technical": [
    "review-basis.recommendation-technical-correctness",
    "review-basis.evidence-grounding",
    "review-basis.action-safety",
    "review-basis.recovery-viability",
  ],
  "review-track.service-impact": [
    "review-basis.service-impact-scope",
    "review-basis.interruption-duration",
    "review-basis.dependency-risk",
    "review-basis.business-continuity",
  ],
} as const;

function label(value: string) {
  return value.split(".").at(-1)?.replaceAll("-", " ") ?? value;
}

export function RecommendationReviewDecisionPanel({
  lease,
  contentPresentation,
  finding,
  findingPresentation,
}: {
  lease: RecommendationProtectedInspection;
  contentPresentation: RecommendationProtectedContent;
  finding: RecommendationHumanReviewFinding;
  findingPresentation: RecommendationFindingPresentation;
}) {
  const [policyId, setPolicyId] = useState(
    "recommendation-track-review-decision-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[finding.environment_id] ?? "",
  );
  const [disposition, setDisposition] = useState<RecommendationReviewDisposition>(
    "review-disposition.changes-required",
  );
  const availableBasisCodes = useMemo(() => BASIS_CODES[finding.track_code], [finding.track_code]);
  const [basisCodes, setBasisCodes] = useState<string[]>([availableBasisCodes[0]]);
  const [purpose, setPurpose] = useState(
    "Record the accountable recommendation review decision for this exact finding packet.",
  );
  const [findingsAcknowledged, setFindingsAcknowledged] = useState(false);
  const [humanDecisionAcknowledged, setHumanDecisionAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationTrackReviewDecision });
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
    <div className="review-decision-panel" aria-labelledby="recommendation-review-decision-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">ACCOUNTABLE RECOMMENDATION REVIEW</p>
          <h3 id="recommendation-review-decision-title">Track review decision</h3>
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
                <span>{label(code)}</span>
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
            <span>I reviewed the exact sealed findings shown for this recommendation track.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={humanDecisionAcknowledged}
              onChange={(event) => setHumanDecisionAcknowledged(event.target.checked)}
            />
            <span>This is my accountable human recommendation track decision.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>This decision is not recommendation approval or operational authority.</span>
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
            <p>
              The exact assignee, recommendation lineage, lease, browser binding, track cookie,
              finding presentation, and signed policy must remain current.
            </p>
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
            <span className={`state-badge ${decision.correction_required ? "pending" : "approved"}`}>
              {decision.correction_required ? <RotateCcw size={14} /> : <CheckCircle2 size={14} />}
              {label(decision.disposition_code)}
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Track</span><strong>{label(decision.track_code)}</strong></div>
            <div><span>Attestation</span><strong>verified</strong></div>
            <div><span>Correction</span><strong>{decision.correction_required ? "required" : "not required"}</strong></div>
            <div><span>Recommendation approval</span><strong>not granted</strong></div>
          </div>
          <p className="muted-copy">
            {decision.all_tracks_decided
              ? decision.all_tracks_passed
                ? "Both accountable tracks passed. This is readiness evidence only and does not approve the recommendation."
                : "Both accountable tracks decided and at least one requires correction. No correction was created automatically."
              : "The other accountable review track remains independent and incomplete."}
          </p>
          <p className="muted-copy">
            This immutable decision grants no workflow, ITSM, execution, deployment, or
            infrastructure mutation authority.
          </p>
        </div>
      )}
    </div>
  );
}
