import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import {
  createRecommendationReadiness,
  type RecommendationReadinessResult,
} from "../../api/recommendationReadiness";
import type { RecommendationPromotionResult } from "../../api/recommendationPromotions";
import { RecommendationReviewRequestPanel } from "./RecommendationReviewRequestPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "1d949fe80158748690b942fc31fc2f9443797469ea71486eb6b14ed80e4f5aa5",
};

export function RecommendationReadinessPanel({
  promotionResult,
}: {
  promotionResult: RecommendationPromotionResult;
}) {
  const recommendation = promotionResult.recommendation;
  const [policyId, setPolicyId] = useState("recommendation-readiness-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[recommendation.environment_id] ?? "",
  );
  const [reviewBoundaryAcknowledged, setReviewBoundaryAcknowledged] = useState(false);
  const [blockedBoundaryAcknowledged, setBlockedBoundaryAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationReadiness });
  const result: RecommendationReadinessResult | undefined = mutation.data?.data;
  const canSubmit =
    recommendation.state === "draft" &&
    !recommendation.recommendation_ready_for_review &&
    reviewBoundaryAcknowledged &&
    blockedBoundaryAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="recommendation-readiness-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">DETERMINISTIC READINESS</p>
          <h3 id="recommendation-readiness-title">Assess review readiness</h3>
        </div>
        <ClipboardCheck size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Readiness policy ID</span>
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
          <label className="approval-check">
            <input
              type="checkbox"
              checked={reviewBoundaryAcknowledged}
              onChange={(event) => setReviewBoundaryAcknowledged(event.target.checked)}
            />
            <span>Readiness is not human review or approval.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={blockedBoundaryAcknowledged}
              onChange={(event) => setBlockedBoundaryAcknowledged(event.target.checked)}
            />
            <span>A blocked assessment requires a new recommendation version.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No workflow, ITSM, execution, deployment, or mutation authority is created.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ promotionResult, policyId, policyDigest })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ClipboardCheck size={16} />
            )}
            Assess readiness
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Review-readiness assessment unavailable</h3>
            <p>Draft lineage, signed policy, access, and safety evidence must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <>
          <div className="correction-record" data-testid="recommendation-readiness-result">
            <div className="section-heading compact-heading">
              <div>
                <p className="eyebrow">{result.assessment.evaluation_outcome.toUpperCase()}</p>
                <strong>
                  {result.assessment.recommendation_ready_for_review
                    ? "Ready for human review"
                    : "Blocked before human review"}
                </strong>
              </div>
              <span className="state-badge neutral">
                <ShieldCheck size={14} /> {result.assessment.state.replaceAll("_", " ")}
              </span>
            </div>
            <div className="connector-capability-list" aria-label="Readiness summary">
              <span className="connector-capability" data-state="available">
                {result.manifest.passed_check_count}/{result.manifest.check_count} checks
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.option_count} options
              </span>
              <span className="connector-capability" data-state="available">
                no operational authority
              </span>
            </div>
            {result.manifest.reason_codes.length > 0 && (
              <p className="muted-copy">{result.manifest.reason_codes.join(", ")}</p>
            )}
          </div>
          {result.assessment.recommendation_ready_for_review && (
            <RecommendationReviewRequestPanel
              readinessResult={result}
              recommendationDigest={recommendation.canonical_digest}
            />
          )}
        </>
      )}
    </div>
  );
}
