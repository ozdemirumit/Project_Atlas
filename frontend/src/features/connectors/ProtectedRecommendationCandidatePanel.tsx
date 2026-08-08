import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, ListChecks, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  createProtectedRecommendationCandidates,
  type ProtectedRecommendationCandidateResult,
} from "../../api/protectedRecommendationCandidates";
import type { ProtectedAnswerPresentationResult } from "../../api/protectedAnswerPresentation";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "941956953434177e9b22dae20a95db10aa0d3739f938ee2939048b81757c0c7d",
};

const CATEGORY_LABELS: Record<string, string> = {
  "recommendation-category.investigate": "Investigate",
  "recommendation-category.escalate": "Escalate",
  "recommendation-category.defer-no-action": "Defer or take no action",
};

export function ProtectedRecommendationCandidatePanel({
  presentationResult,
}: {
  presentationResult: ProtectedAnswerPresentationResult;
}) {
  const presentation = presentationResult.presentation;
  const [policyId, setPolicyId] = useState(
    "protected-recommendation-candidate-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[presentation.environment_id] ?? "",
  );
  const [incompleteAcknowledged, setIncompleteAcknowledged] = useState(false);
  const [impactAcknowledged, setImpactAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedRecommendationCandidates });
  const result: ProtectedRecommendationCandidateResult | undefined = mutation.data?.data;
  const canSubmit =
    presentation.answer_presented &&
    !presentation.recommendation_generated &&
    incompleteAcknowledged &&
    impactAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="recommendation-candidate-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED CANDIDATE BOUNDARY</p>
          <h3 id="recommendation-candidate-title">Generate grounded candidates</h3>
        </div>
        <ListChecks size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Candidate policy ID</span>
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
              checked={incompleteAcknowledged}
              onChange={(event) => setIncompleteAcknowledged(event.target.checked)}
            />
            <span>Candidates are incomplete inputs, not final recommendations.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={impactAcknowledged}
              onChange={(event) => setImpactAcknowledged(event.target.checked)}
            />
            <span>Service impact, risk, duration, and recovery remain unverified.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>Generation grants no recommendation, workflow, tool, or operational authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ presentationResult, policyId, policyDigest })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ListChecks size={16} />
            )}
            Generate candidates
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Candidate generation unavailable</h3>
            <p>Presentation lineage, access, policy, browser, and protected artifacts must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="correction-record">
          <strong>Grounded candidate set generated</strong>
          <code>{result.candidate_set.candidate_set_id}</code>
          <p className="muted-copy">
            {result.manifest.candidate_count} candidates across {result.manifest.step_count} bounded,
            non-executable steps. Maximum capability class: {result.manifest.maximum_capability_class}.
          </p>
          <div className="connector-capability-list" aria-label="Candidate categories">
            {result.manifest.candidate_categories.map((category) => (
              <span className="connector-capability" data-state="available" key={category}>
                {CATEGORY_LABELS[category] ?? category}
              </span>
            ))}
          </div>
          <p className="muted-copy">
            Candidate content remains protected. No impact analysis, preference, recommendation,
            workflow, tool, or infrastructure action ran.
          </p>
        </div>
      )}
    </div>
  );
}
