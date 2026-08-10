import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, ShieldCheck, UserRoundCheck } from "lucide-react";
import { useState } from "react";

import type { RecommendationReviewRequestResult } from "../../api/recommendationReviewRequests";
import { createRecommendationReviewerAssignment } from "../../api/recommendationReviewerAssignments";
import { RecommendationProtectedInspectionPanel } from "./RecommendationProtectedInspectionPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "f7e53c158cc7a82669395d5c40e869863da0fddb49637487ae7e76c3ff600969",
};

export function RecommendationReviewerAssignmentPanel({
  reviewRequestResult,
}: {
  reviewRequestResult: RecommendationReviewRequestResult;
}) {
  const request = reviewRequestResult.request;
  const [policyId, setPolicyId] = useState(
    "recommendation-reviewer-assignment-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[request.environment_id] ?? "",
  );
  const [selectionBoundaryAcknowledged, setSelectionBoundaryAcknowledged] = useState(false);
  const [separationAcknowledged, setSeparationAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationReviewerAssignment });
  const result = mutation.data?.data;
  const canSubmit =
    selectionBoundaryAcknowledged &&
    separationAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <section
      className="target-configuration-panel"
      aria-labelledby="recommendation-reviewer-assignment-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">SEPARATION OF DUTIES</p>
          <h3 id="recommendation-reviewer-assignment-title">Assign accountable reviewers</h3>
        </div>
        <UserRoundCheck size={24} />
      </div>
      {!result && (
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
          <label className="approval-check">
            <input
              type="checkbox"
              checked={selectionBoundaryAcknowledged}
              onChange={(event) => setSelectionBoundaryAcknowledged(event.target.checked)}
            />
            <span>Reviewer identities, tracks, queues, and directory queries are policy-owned.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={separationAcknowledged}
              onChange={(event) => setSeparationAcknowledged(event.target.checked)}
            />
            <span>Technical and service-impact review require two distinct eligible humans.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>
              Assignment opens no content and grants no decision, approval, or operational
              authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ reviewRequestResult, policyId, policyDigest })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <UserRoundCheck size={16} />
            )}
            Assign accountable reviewers
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Reviewer assignment unavailable</h3>
            <p>Directory, eligibility, separation, source lineage, and receipt must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <>
        <div className="package-signing-record" data-testid="recommendation-reviewer-assignment">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">REVIEWERS ASSIGNED</p>
              <strong>Independent review tracks are ready</strong>
            </div>
            <span className="state-badge approved">
              <ShieldCheck size={14} /> identity protected
            </span>
          </div>
          <div className="mcp-builder-facts" aria-label="Reviewer assignment summary">
            {result.manifest.track_assignments.map(
              ([track, , assignmentId, reviewerDigest, status]) => (
                <div key={track}>
                  <span>{track.replace("review-track.", "").replaceAll("-", " ")}</span>
                  <strong>{status}</strong>
                  <code title={assignmentId}>{reviewerDigest.slice(0, 12)}...</code>
                </div>
              ),
            )}
          </div>
          <p className="muted-copy">
            <ShieldCheck size={14} /> Only salted reviewer digests are shown. Content inspection,
            findings, decisions, approvals, and operations remain separate governed stages.
          </p>
        </div>
        <RecommendationProtectedInspectionPanel assignmentResult={result} />
        </>
      )}
    </section>
  );
}
