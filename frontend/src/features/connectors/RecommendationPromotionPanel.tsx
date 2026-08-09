import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileArchive, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import {
  createRecommendationPromotion,
  type RecommendationPromotionResult,
} from "../../api/recommendationPromotions";
import type { ProtectedRecommendationPresentationResult } from "../../api/protectedRecommendationPresentations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "3cdaecd1ad423ea8d2ec1c7c06f9910a01e5637e4b182341dafb1e2d9c391c87",
};

export function RecommendationPromotionPanel({
  presentationResult,
}: {
  presentationResult: ProtectedRecommendationPresentationResult;
}) {
  const presentation = presentationResult.presentation;
  const [policyId, setPolicyId] = useState("recommendation-promotion-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[presentation.environment_id] ?? "",
  );
  const [draftAcknowledged, setDraftAcknowledged] = useState(false);
  const [reviewAcknowledged, setReviewAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationPromotion });
  const result: RecommendationPromotionResult | undefined = mutation.data?.data;
  const canSubmit =
    presentation.recommendation_presented &&
    !presentation.recommendation_ready_for_review &&
    draftAcknowledged &&
    reviewAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="recommendation-promotion-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">IMMUTABLE DOMAIN DRAFT</p>
          <h3 id="recommendation-promotion-title">Promote recommendation</h3>
        </div>
        <FileArchive size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Promotion policy ID</span>
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
              checked={draftAcknowledged}
              onChange={(event) => setDraftAcknowledged(event.target.checked)}
            />
            <span>Promotion creates an immutable draft only.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={reviewAcknowledged}
              onChange={(event) => setReviewAcknowledged(event.target.checked)}
            />
            <span>The draft is not ready for review and is not approved.</span>
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
            onClick={() => mutation.mutate({ presentationResult, policyId, policyDigest })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <FileArchive size={16} />}
            Promote to draft
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Recommendation promotion unavailable</h3>
            <p>Presentation lineage, signed policy, access, and protected sources must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="correction-record" data-testid="recommendation-promotion-result">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">DRAFT</p>
              <strong>{result.recommendation.headline}</strong>
            </div>
            <span className="state-badge neutral">
              <ShieldCheck size={14} /> {result.recommendation.state}
            </span>
          </div>
          <div className="connector-capability-list" aria-label="Promoted recommendation summary">
            <span className="connector-capability" data-state="available">
              {result.manifest.option_count} options
            </span>
            <span className="connector-capability" data-state="available">
              {result.manifest.preferred_count} preferred
            </span>
            <span className="connector-capability" data-state="available">
              {result.recommendation.outcome.replace("_", " ")}
            </span>
          </div>
          <p className="muted-copy">{result.recommendation.safety_notice}</p>
        </div>
      )}
    </div>
  );
}
