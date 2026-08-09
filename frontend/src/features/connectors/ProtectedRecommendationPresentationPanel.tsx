import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileCheck2, RefreshCw, ShieldAlert } from "lucide-react";
import { useState } from "react";

import {
  createProtectedRecommendationPresentation,
  type PresentedRecommendationOption,
  type ProtectedRecommendationPresentationResult,
} from "../../api/protectedRecommendationPresentations";
import type { ProtectedRecommendationAdjudicationResult } from "../../api/protectedRecommendationAdjudications";
import { RecommendationPromotionPanel } from "./RecommendationPromotionPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "2717a01c5dd2d1f68aab405dbbb5fd76b1abb4ab87589d633de48ee9f68b4359",
};

const ROLE_LABELS: Record<PresentedRecommendationOption["role"], string> = {
  preferred: "Preferred",
  alternative: "Alternative",
  tied: "Equally supported",
  unsupported: "Not currently supportable",
};

function RecommendationOption({ option }: { option: PresentedRecommendationOption }) {
  return (
    <section className="recommendation-presentation-option" aria-label={option.title}>
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">{ROLE_LABELS[option.role]}</p>
          <h4>{option.title}</h4>
        </div>
        <span className={`state-badge ${option.role === "preferred" ? "success" : "neutral"}`}>
          {option.overall_risk} risk
        </span>
      </div>
      <p>{option.intended_outcome}</p>
      <p className="muted-copy">{option.rationale}</p>
      <div className="connector-capability-list" aria-label={`${option.title} estimates`}>
        <span className="connector-capability" data-state="available">
          Work {option.work_minimum_minutes}-{option.work_maximum_minutes} min
        </span>
        <span className="connector-capability" data-state="available">
          Interruption {option.interruption_minimum_minutes}-{option.interruption_maximum_minutes} min
        </span>
        <span className="connector-capability" data-state="available">
          Recovery {option.recovery_minimum_minutes}-{option.recovery_maximum_minutes} min
        </span>
        <span className="connector-capability" data-state="available">
          {option.technical_service_count} technical / {option.business_service_count} business services
        </span>
      </div>
      <ol className="recommendation-step-list">
        {option.steps.map((step) => (
          <li key={`${step.order}-${step.phase}`}>
            <strong>{step.phase}</strong>
            <span>{step.conceptual_action}</span>
            <small>{step.capability_class} read-only boundary</small>
          </li>
        ))}
      </ol>
      {(option.support_reasons.length > 0 || option.evidence_gaps.length > 0) && (
        <div className="recommendation-evidence-notice">
          <ShieldAlert size={18} />
          <div>
            {option.support_reasons.map((reason) => (
              <p key={reason}>{reason}</p>
            ))}
            {option.evidence_gaps.map((gap) => (
              <p key={gap}>{gap}</p>
            ))}
          </div>
        </div>
      )}
      <p className="muted-copy">
        {option.evidence_references.length} evidence references, {option.assumptions.length} assumptions, {" "}
        {option.unknowns.length} unknowns. Recovery: {option.recovery_feasibility}.
      </p>
    </section>
  );
}

export function ProtectedRecommendationPresentationPanel({
  adjudicationResult,
}: {
  adjudicationResult: ProtectedRecommendationAdjudicationResult;
}) {
  const adjudication = adjudicationResult.adjudication;
  const [policyId, setPolicyId] = useState(
    "protected-recommendation-presentation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[adjudication.environment_id] ?? "",
  );
  const [decisionSupportAcknowledged, setDecisionSupportAcknowledged] = useState(false);
  const [outcomeAcknowledged, setOutcomeAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedRecommendationPresentation });
  const result: ProtectedRecommendationPresentationResult | undefined = mutation.data?.data;
  const canSubmit =
    adjudication.recommendation_complete &&
    !adjudication.recommendation_presented &&
    decisionSupportAcknowledged &&
    outcomeAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="recommendation-presentation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">INERT DECISION SUPPORT</p>
          <h3 id="recommendation-presentation-title">Present recommendation</h3>
        </div>
        <FileCheck2 size={24} />
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
            <span>The presentation is decision support only, not approval.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={outcomeAcknowledged}
              onChange={(event) => setOutcomeAcknowledged(event.target.checked)}
            />
            <span>A tie or no supportable option will remain unresolved.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No review, workflow, execution, or infrastructure authority is granted.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ adjudicationResult, policyId, policyDigest })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <FileCheck2 size={16} />}
            Present recommendation
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Recommendation presentation unavailable</h3>
            <p>Adjudication lineage, signed policy, access, and protected sources must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="recommendation-presentation-result">
          <div className="correction-record">
            <strong>{result.recommendation.headline}</strong>
            <div className="connector-capability-list" aria-label="Presentation summary">
              <span className="connector-capability" data-state="available">
                {result.manifest.option_count} options
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.evidence_reference_count} evidence references
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.unknown_count} unknowns
              </span>
            </div>
            <p className="muted-copy">{result.recommendation.safety_notice}</p>
          </div>
          {result.recommendation.options.map((option) => (
            <RecommendationOption key={`${option.role}-${option.title}`} option={option} />
          ))}
          <RecommendationPromotionPanel presentationResult={result} />
        </div>
      )}
    </div>
  );
}
