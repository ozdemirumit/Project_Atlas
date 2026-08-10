import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Eye, LockKeyhole, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  createRecommendationProtectedInspection,
  type RecommendationInspectionTrack,
} from "../../api/recommendationProtectedInspections";
import type { RecommendationReviewerAssignmentResult } from "../../api/recommendationReviewerAssignments";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "6245171bd90d87d0faa11cd7972959bb32ca06201d23d882813aeb9e1dd28c9f",
};

export function RecommendationProtectedInspectionPanel({
  assignmentResult,
}: {
  assignmentResult: RecommendationReviewerAssignmentResult;
}) {
  const assignment = assignmentResult.assignment;
  const [trackCode, setTrackCode] = useState<RecommendationInspectionTrack>(
    "review-track.technical",
  );
  const [policyId, setPolicyId] = useState(
    "recommendation-protected-inspection-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[assignment.environment_id] ?? "",
  );
  const [assigneeAcknowledged, setAssigneeAcknowledged] = useState(false);
  const [secretBoundaryAcknowledged, setSecretBoundaryAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationProtectedInspection });
  const lease = mutation.data?.data;
  const canSubmit =
    assigneeAcknowledged &&
    secretBoundaryAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section
      className="target-configuration-panel"
      aria-labelledby="recommendation-inspection-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">ASSIGNEE-BOUND ACCESS</p>
          <h3 id="recommendation-inspection-title">Recommendation inspection lease</h3>
        </div>
        <Eye size={24} />
      </div>
      {!lease && (
        <>
          <div className="segmented-control" role="group" aria-label="Recommendation review track">
            <button
              type="button"
              className={trackCode === "review-track.technical" ? "active" : ""}
              aria-pressed={trackCode === "review-track.technical"}
              onClick={() => setTrackCode("review-track.technical")}
            >
              Technical
            </button>
            <button
              type="button"
              className={trackCode === "review-track.service-impact" ? "active" : ""}
              aria-pressed={trackCode === "review-track.service-impact"}
              onClick={() => setTrackCode("review-track.service-impact")}
            >
              Service impact
            </button>
          </div>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Inspection policy ID</span>
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
              checked={assigneeAcknowledged}
              onChange={(event) => setAssigneeAcknowledged(event.target.checked)}
            />
            <span>Only the exact assigned reviewer may open the selected review track.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={secretBoundaryAcknowledged}
              onChange={(event) => setSecretBoundaryAcknowledged(event.target.checked)}
            />
            <span>The short-lived lease returns no content or secret in JSON.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>The lease records no finding, decision, approval, workflow, or operation.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ assignmentResult, trackCode, policyId, policyDigest })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Eye size={16} />}
            Open assigned inspection lease
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Assigned inspection unavailable</h3>
            <p>
              The signed-in identity must be this track&apos;s exact unexpired assignee with recent
              hardware MFA. Access cannot be delegated or refreshed.
            </p>
          </div>
        </div>
      )}
      {lease && (
        <div className="package-signing-record" data-testid="recommendation-inspection-lease">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">INSPECTION OPENED</p>
              <strong>Protected review channel is active</strong>
            </div>
            <span className="state-badge approved">
              <LockKeyhole size={14} /> browser bound
            </span>
          </div>
          <div className="mcp-builder-facts" aria-label="Recommendation inspection summary">
            <div>
              <span>Track</span>
              <strong>{lease.track_code.replace("review-track.", "").replaceAll("-", " ")}</strong>
            </div>
            <div>
              <span>Expires</span>
              <strong>{new Date(lease.expires_at).toLocaleTimeString()}</strong>
            </div>
            <div>
              <span>Content disclosed</span>
              <strong>none</strong>
            </div>
            <div>
              <span>Operational authority</span>
              <strong>none</strong>
            </div>
          </div>
          <p className="muted-copy">
            <LockKeyhole size={14} /> The lease secret is held only in an HttpOnly browser cookie.
            Content retrieval and reviewer findings remain separate governed stages.
          </p>
        </div>
      )}
    </section>
  );
}
