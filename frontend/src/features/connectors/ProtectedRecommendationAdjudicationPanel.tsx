import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, Scale } from "lucide-react";
import { useState } from "react";

import {
  createProtectedRecommendationAdjudication,
  type ProtectedRecommendationAdjudicationResult,
} from "../../api/protectedRecommendationAdjudications";
import type { ProtectedCandidateRiskRecoveryResult } from "../../api/protectedCandidateRiskRecovery";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "1b95ec3b307ec9801f92944766ebcef79849eaa8d5bb3c16ae86ccee6db4c90d",
};

export function ProtectedRecommendationAdjudicationPanel({
  completionResult,
}: {
  completionResult: ProtectedCandidateRiskRecoveryResult;
}) {
  const completion = completionResult.completion;
  const [policyId, setPolicyId] = useState(
    "protected-recommendation-adjudication-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[completion.environment_id] ?? "",
  );
  const [preferenceAcknowledged, setPreferenceAcknowledged] = useState(false);
  const [tieAcknowledged, setTieAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedRecommendationAdjudication });
  const result: ProtectedRecommendationAdjudicationResult | undefined = mutation.data?.data;
  const canSubmit =
    completion.risk_completed &&
    completion.recovery_completed &&
    !completion.recommendation_complete &&
    preferenceAcknowledged &&
    tieAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;
  const outcome = result?.manifest.no_supportable_candidate
    ? "No supportable candidate"
    : result?.manifest.tie
      ? "Protected tie preserved"
      : "Protected preference established";

  return (
    <div className="final-resolution-panel" aria-labelledby="recommendation-adjudication-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">DETERMINISTIC ADJUDICATION</p>
          <h3 id="recommendation-adjudication-title">Adjudicate recommendations</h3>
        </div>
        <Scale size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Adjudication policy ID</span>
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
              checked={preferenceAcknowledged}
              onChange={(event) => setPreferenceAcknowledged(event.target.checked)}
            />
            <span>A protected preference is decision support, not approval.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={tieAcknowledged}
              onChange={(event) => setTieAcknowledged(event.target.checked)}
            />
            <span>A tie or no supportable candidate is a valid governed outcome.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>Adjudication creates no presentation, workflow, approval, or authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ completionResult, policyId, policyDigest })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Scale size={16} />}
            Adjudicate candidates
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Recommendation adjudication unavailable</h3>
            <p>Completion lineage, signed policy, access, and protected artifacts must remain current.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="correction-record">
          <strong>{outcome}</strong>
          <code>{result.adjudication.adjudication_id}</code>
          <div className="connector-capability-list" aria-label="Adjudication summary">
            <span className="connector-capability" data-state="available">
              {result.manifest.eligible_count} eligible
            </span>
            <span className="connector-capability" data-state="available">
              {result.manifest.excluded_count} excluded
            </span>
            <span className="connector-capability" data-state="available">
              {result.manifest.preferred_count} preferred
            </span>
            <span className="connector-capability" data-state="available">
              {result.manifest.alternative_count} alternatives
            </span>
          </div>
          <p className="muted-copy">
            {result.manifest.candidate_count} candidates were evaluated across{" "}
            {result.manifest.dimension_count} ordered policy dimensions. Maximum risk remains{" "}
            {result.manifest.maximum_risk}.
          </p>
          <p className="muted-copy">
            Evidence contains {result.manifest.gap_count} gaps and {result.manifest.unknown_count}{" "}
            unknowns. No candidate identity or protected comparison content is presented here.
          </p>
          <p className="muted-copy">{result.manifest.safety_notice}</p>
        </div>
      )}
    </div>
  );
}
