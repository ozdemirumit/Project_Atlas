import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Eye, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import {
  createRecommendationFindingPresentation,
  type RecommendationPresentedFinding,
} from "../../api/recommendationFindingPresentations";
import type { RecommendationHumanReviewFinding } from "../../api/recommendationReviewFindings";
import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "9fc389887f614977d27f12829da145fabd5d7412173994b0b807ed7fdeb0aabf",
};

function label(value: string) {
  return value.split(".").at(-1)?.replaceAll("-", " ") ?? value;
}

function Finding({ finding, index }: { finding: RecommendationPresentedFinding; index: number }) {
  return (
    <article className="review-finding-item">
      <div className="section-heading">
        <strong>Finding {index + 1}</strong>
        <span className="state-badge neutral">{label(finding.severity_code)}</span>
      </div>
      <span className="eyebrow">{label(finding.category_code)}</span>
      <h4>{finding.summary}</h4>
      <p>{finding.detail}</p>
    </article>
  );
}

export function RecommendationFindingPresentationPanel({
  lease,
  presentation,
  finding,
}: {
  lease: RecommendationProtectedInspection;
  presentation: RecommendationProtectedContent;
  finding: RecommendationHumanReviewFinding;
}) {
  const [policyId, setPolicyId] = useState(
    "recommendation-finding-presentation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[finding.environment_id] ?? "");
  const [purpose, setPurpose] = useState(
    "Present sealed recommendation observations without recording a review decision.",
  );
  const [sensitiveAcknowledged, setSensitiveAcknowledged] = useState(false);
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationFindingPresentation });
  const result = mutation.data?.data;
  const canSubmit =
    sensitiveAcknowledged &&
    decisionAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="finding-presentation-panel" aria-labelledby="recommendation-finding-present-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED FINDING BOUNDARY</p>
          <h3 id="recommendation-finding-present-title">Inspect sealed findings</h3>
        </div>
        <Eye size={24} />
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
          <label>
            <span>Inspection purpose</span>
            <textarea
              value={purpose}
              rows={3}
              maxLength={1000}
              onChange={(event) => setPurpose(event.target.value)}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={sensitiveAcknowledged}
              onChange={(event) => setSensitiveAcknowledged(event.target.checked)}
            />
            <span>These reviewer observations contain sensitive infrastructure information.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={decisionAcknowledged}
              onChange={(event) => setDecisionAcknowledged(event.target.checked)}
            />
            <span>Viewing findings does not complete review or grant approval or authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ lease, presentation, finding, policyId, policyDigest, purpose })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Eye size={16} />}
            Present sealed findings
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Finding presentation unavailable</h3>
            <p>
              The exact reviewer, recommendation lineage, lease, browser binding, track, artifact,
              and signed policy must remain current.
            </p>
          </div>
        </div>
      )}
      {result && (
        <div data-testid="recommendation-finding-presentation">
          <div className="package-signing-record">
            <div className="section-heading">
              <div>
                <strong>Sealed findings presented</strong>
                <code>{result.finding_presentation_id}</code>
              </div>
              <span className="state-badge approved">
                <ShieldCheck size={14} /> read only
              </span>
            </div>
            <p className="muted-copy">
              {result.finding_count} exact {label(result.track_code)} findings. No review decision,
              recommendation approval, workflow, ITSM record, or operational action exists.
            </p>
          </div>
          <div className="review-finding-list" aria-label="Presented recommendation findings">
            {result.findings.map((item, index) => (
              <Finding
                finding={item}
                index={index}
                key={`${item.category_code}-${item.severity_code}-${index}`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
