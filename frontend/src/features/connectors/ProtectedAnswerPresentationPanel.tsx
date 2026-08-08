import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, MessageSquareText, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createProtectedAnswerPresentation } from "../../api/protectedAnswerPresentation";
import type { ProtectedDraftAdjudicationResult } from "../../api/protectedDraftAdjudication";
import { ProtectedRecommendationCandidatePanel } from "./ProtectedRecommendationCandidatePanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "769b1a7f3ab14d9dbdf7c47924c942eeb37aeb1e07961a608d08560ddf29c986",
};

export function ProtectedAnswerPresentationPanel({
  adjudicationResult,
}: {
  adjudicationResult: ProtectedDraftAdjudicationResult;
}) {
  const adjudication = adjudicationResult.adjudication;
  const [policyId, setPolicyId] = useState("protected-answer-presentation-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[adjudication.environment_id] ?? "",
  );
  const [decisionSupportAcknowledged, setDecisionSupportAcknowledged] = useState(false);
  const [evidenceAcknowledged, setEvidenceAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedAnswerPresentation });
  const result = mutation.data?.data;
  const canSubmit =
    adjudication.outcome === "adjudication-outcome.eligible" &&
    adjudication.model_draft_adjudicated &&
    !adjudication.answer_generated &&
    decisionSupportAcknowledged &&
    evidenceAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="answer-presentation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED ANSWER BOUNDARY</p>
          <h3 id="answer-presentation-title">Present adjudicated answer</h3>
        </div>
        <MessageSquareText size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Presentation policy ID</span>
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
              checked={decisionSupportAcknowledged}
              onChange={(event) => setDecisionSupportAcknowledged(event.target.checked)}
            />
            <span>The answer is bounded decision support, not established truth.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={evidenceAcknowledged}
              onChange={(event) => setEvidenceAcknowledged(event.target.checked)}
            />
            <span>Citation references and explicit unknowns remain material.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>Presentation grants no recommendation, workflow, tool, or operational authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ adjudicationResult, policyId, policyDigest })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <MessageSquareText size={16} />
            )}
            Present answer
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Answer presentation unavailable</h3>
            <p>Eligibility, access, policy, browser, retention, and protected artifacts must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <>
          <div className="correction-record">
            <strong>Adjudicated answer</strong>
            <p>{result.answer.summary}</p>
            <h4>Citation references</h4>
            <ul>
              {result.answer.citation_references.map((reference) => (
                <li key={reference}><code>{reference}</code></li>
              ))}
            </ul>
            <h4>Explicit unknowns</h4>
            <ul>
              {result.answer.unknowns.map((unknown) => <li key={unknown}>{unknown}</li>)}
            </ul>
            <p className="muted-copy">
              Decision support only. No recommendation, workflow, tool, or infrastructure action ran.
            </p>
          </div>
          <ProtectedRecommendationCandidatePanel presentationResult={result} />
        </>
      )}
    </div>
  );
}
