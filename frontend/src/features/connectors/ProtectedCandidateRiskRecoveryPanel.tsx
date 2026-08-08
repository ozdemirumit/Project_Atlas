import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, ShieldAlert } from "lucide-react";
import { useState } from "react";

import {
  createProtectedCandidateRiskRecovery,
  type ProtectedCandidateRiskRecoveryResult,
} from "../../api/protectedCandidateRiskRecovery";
import type { ProtectedCandidateImpactResult } from "../../api/protectedCandidateImpacts";
import { ProtectedRecommendationAdjudicationPanel } from "./ProtectedRecommendationAdjudicationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "721168ca5fd267fb1117cab7bb8b135583febf7c8e0bf83b66a1a53a0d544efc",
};

export function ProtectedCandidateRiskRecoveryPanel({
  impactResult,
}: {
  impactResult: ProtectedCandidateImpactResult;
}) {
  const impact = impactResult.impact_analysis;
  const [policyId, setPolicyId] = useState(
    "protected-candidate-risk-recovery-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[impact.environment_id] ?? "",
  );
  const [estimatesAcknowledged, setEstimatesAcknowledged] = useState(false);
  const [unknownsAcknowledged, setUnknownsAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createProtectedCandidateRiskRecovery });
  const result: ProtectedCandidateRiskRecoveryResult | undefined = mutation.data?.data;
  const canSubmit =
    impact.service_impact_analyzed &&
    !impact.impact_complete &&
    estimatesAcknowledged &&
    unknownsAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="candidate-risk-recovery-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED COMPLETION</p>
          <h3 id="candidate-risk-recovery-title">Complete risk and recovery</h3>
        </div>
        <ShieldAlert size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Completion policy ID</span>
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
              checked={estimatesAcknowledged}
              onChange={(event) => setEstimatesAcknowledged(event.target.checked)}
            />
            <span>Risk, duration, and recovery estimates are evidence-bounded, not guarantees.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={unknownsAcknowledged}
              onChange={(event) => setUnknownsAcknowledged(event.target.checked)}
            />
            <span>Missing or unknown evidence cannot reduce the assessed risk.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>Completion creates no preference, workflow, approval, or operational authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ impactResult, policyId, policyDigest })}
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ShieldAlert size={16} />
            )}
            Complete assessment
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Risk and recovery completion unavailable</h3>
            <p>Impact lineage, operational evidence, policy, access, and protected artifacts must remain current.</p>
          </div>
        </div>
      )}
      {result && (
        <>
          <div className="correction-record">
            <strong>Risk and recovery assessment completed</strong>
            <code>{result.completion.completion_id}</code>
            <p className="muted-copy">
              Maximum risk: {result.manifest.maximum_risk}. Evidence is {result.manifest.evidence_freshness}
              {" "}and {result.manifest.evidence_completeness}.
            </p>
            <div className="connector-capability-list" aria-label="Risk assessment summary">
              <span className="connector-capability" data-state="available">
                {result.manifest.low_risk_count} low
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.moderate_risk_count} moderate
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.high_risk_count} high
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.critical_risk_count} critical
              </span>
              <span className="connector-capability" data-state="available">
                {result.manifest.unknown_risk_count} unknown
              </span>
            </div>
            <p className="muted-copy">
              Work estimate: {result.manifest.work_minimum_minutes}-{result.manifest.work_maximum_minutes}
              {" "}minutes. Interruption estimate: {result.manifest.interruption_minimum_minutes}-
              {result.manifest.interruption_maximum_minutes} minutes across {result.manifest.interruption_possible_count}
              {" "}candidates.
            </p>
            <p className="muted-copy">
              Recovery: {result.manifest.recovery_feasible_count} feasible, {result.manifest.recovery_unknown_count}
              {" "}unknown, {result.manifest.recovery_blocked_count} blocked; estimated {result.manifest.recovery_minimum_minutes}-
              {result.manifest.recovery_maximum_minutes} minutes. Evidence contains {result.manifest.gap_count}
              {" "}gaps and {result.manifest.unknown_count} unknowns.
            </p>
            <p className="muted-copy">{result.manifest.safety_notice}</p>
          </div>
          <ProtectedRecommendationAdjudicationPanel completionResult={result} />
        </>
      )}
    </div>
  );
}
