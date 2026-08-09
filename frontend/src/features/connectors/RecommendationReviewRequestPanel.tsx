import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { RecommendationReadinessResult } from "../../api/recommendationReadiness";
import {
  createRecommendationReviewRequest,
  type RecommendationReviewRequestResult,
} from "../../api/recommendationReviewRequests";
import { RecommendationReviewerAssignmentPanel } from "./RecommendationReviewerAssignmentPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "e2061716d3d2ffb3e981ec66c9a38de40ac7787fa8fc5b2a52dac1a1ed0c70e9",
};

export function RecommendationReviewRequestPanel({
  readinessResult,
  recommendationDigest,
}: {
  readinessResult: RecommendationReadinessResult;
  recommendationDigest: string;
}) {
  const assessment = readinessResult.assessment;
  const [policyId, setPolicyId] = useState(
    "recommendation-review-request-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[assessment.environment_id] ?? "",
  );
  const [requestBoundaryAcknowledged, setRequestBoundaryAcknowledged] = useState(false);
  const [routingBoundaryAcknowledged, setRoutingBoundaryAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationReviewRequest });
  const result: RecommendationReviewRequestResult | undefined = mutation.data?.data;
  const canSubmit =
    assessment.state === "ready_for_review" &&
    assessment.recommendation_ready_for_review &&
    requestBoundaryAcknowledged &&
    routingBoundaryAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="recommendation-review-request-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">POLICY-ROUTED REVIEW</p>
          <h3 id="recommendation-review-request-title">Request human review</h3>
        </div>
        <Send size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Review-request policy ID</span>
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
              checked={requestBoundaryAcknowledged}
              onChange={(event) => setRequestBoundaryAcknowledged(event.target.checked)}
            />
            <span>Request creation is not reviewer assignment or human review.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={routingBoundaryAcknowledged}
              onChange={(event) => setRoutingBoundaryAcknowledged(event.target.checked)}
            />
            <span>Review tracks and queues are selected only by signed policy.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>
              No approval, workflow, ITSM, execution, deployment, or mutation authority is created.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ readinessResult, recommendationDigest, policyId, policyDigest })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Send size={16} />}
            Request human review
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Human-review request unavailable</h3>
            <p>Readiness lineage, signed policy, access, and browser binding must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <>
          <div className="correction-record" data-testid="recommendation-review-request-result">
            <div className="section-heading compact-heading">
              <div>
                <p className="eyebrow">REVIEW REQUESTED</p>
                <strong>Awaiting accountable reviewers</strong>
              </div>
              <span className="state-badge neutral">
                <ShieldCheck size={14} /> no authority granted
              </span>
            </div>
            <div className="connector-capability-list" aria-label="Review request summary">
              {result.manifest.track_statuses.map(([track, status]) => (
                <span className="connector-capability" data-state="available" key={track}>
                  {track.replace("review-track.", "").replaceAll("-", " ")}: {status.replaceAll("_", " ")}
                </span>
              ))}
              <span className="connector-capability" data-state="available">
                no reviewer assigned
              </span>
            </div>
          </div>
          <RecommendationReviewerAssignmentPanel reviewRequestResult={result} />
        </>
      )}
    </div>
  );
}
