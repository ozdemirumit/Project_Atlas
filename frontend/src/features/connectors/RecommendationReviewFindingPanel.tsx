import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, FileWarning, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  createRecommendationHumanReviewFinding,
  type RecommendationFindingTrack,
  type RecommendationHumanReviewFindingItem,
} from "../../api/recommendationReviewFindings";
import type { RecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "39c89750405471d28f1161dc85f0d8b12685d43aaf06e61fd2ccaebb63e3875a",
};

const categories: Record<RecommendationFindingTrack, readonly { value: string; label: string }[]> = {
  "review-track.technical": [
    { value: "finding-category.technical-accuracy", label: "Technical accuracy" },
    { value: "finding-category.operational-safety", label: "Operational safety" },
    { value: "finding-category.evidence-conflict", label: "Evidence conflict" },
    { value: "finding-category.recovery-feasibility", label: "Recovery feasibility" },
    { value: "finding-category.implementation-assumption", label: "Implementation assumption" },
    { value: "finding-category.technical-unknown", label: "Technical unknown" },
  ],
  "review-track.service-impact": [
    { value: "finding-category.affected-service", label: "Affected service" },
    { value: "finding-category.interruption-estimate", label: "Interruption estimate" },
    { value: "finding-category.business-impact", label: "Business impact" },
    { value: "finding-category.communication-gap", label: "Communication gap" },
    { value: "finding-category.recovery-objective", label: "Recovery objective" },
    { value: "finding-category.dependency-uncertainty", label: "Dependency uncertainty" },
  ],
};

const severities = [
  { value: "finding-severity.observation", label: "Observation" },
  { value: "finding-severity.minor", label: "Minor" },
  { value: "finding-severity.material", label: "Material" },
  { value: "finding-severity.critical", label: "Critical" },
] as const;

function emptyFinding(track: RecommendationFindingTrack): RecommendationHumanReviewFindingItem {
  return {
    category_code:
      track === "review-track.technical"
        ? "finding-category.technical-accuracy"
        : "finding-category.affected-service",
    severity_code: severities[0].value,
    summary: "",
    detail: "",
  };
}

export function RecommendationReviewFindingPanel({
  lease,
  presentation,
}: {
  lease: RecommendationProtectedInspection;
  presentation: RecommendationProtectedContent;
}) {
  const [policyId, setPolicyId] = useState(
    "recommendation-human-review-finding-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[presentation.environment_id] ?? "");
  const [findings, setFindings] = useState<RecommendationHumanReviewFindingItem[]>([
    emptyFinding(presentation.track_code),
  ]);
  const [purpose, setPurpose] = useState(
    "Record bounded recommendation observations without creating a review decision.",
  );
  const [evidenceAcknowledged, setEvidenceAcknowledged] = useState(false);
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationHumanReviewFinding });
  const record = mutation.data?.data;
  const canSubmit =
    evidenceAcknowledged &&
    decisionAcknowledged &&
    findings.every(
      (finding) =>
        finding.summary.trim().length >= 10 &&
        finding.detail.trim().length >= 20 &&
        finding.summary.length <= 200 &&
        finding.detail.length <= 4000,
    ) &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  function updateFinding(index: number, patch: Partial<RecommendationHumanReviewFindingItem>) {
    setFindings((current) =>
      current.map((finding, findingIndex) =>
        findingIndex === index ? { ...finding, ...patch } : finding,
      ),
    );
  }

  return (
    <div className="review-finding-panel" aria-labelledby="recommendation-review-finding-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">RECOMMENDATION FINDINGS</p>
          <h3 id="recommendation-review-finding-title">Reviewer observations</h3>
        </div>
        <FileWarning size={24} />
      </div>
      {!record && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Finding policy ID</span>
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
          <div className="review-finding-list">
            {findings.map((finding, index) => (
              <fieldset className="review-finding-item" key={`recommendation-finding-${index + 1}`}>
                <legend>Finding {index + 1}</legend>
                <div className="mcp-builder-review-fields">
                  <label>
                    <span>Category</span>
                    <select
                      value={finding.category_code}
                      onChange={(event) =>
                        updateFinding(index, { category_code: event.target.value })
                      }
                    >
                      {categories[presentation.track_code].map((category) => (
                        <option key={category.value} value={category.value}>
                          {category.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Severity</span>
                    <select
                      value={finding.severity_code}
                      onChange={(event) =>
                        updateFinding(index, { severity_code: event.target.value })
                      }
                    >
                      {severities.map((severity) => (
                        <option key={severity.value} value={severity.value}>
                          {severity.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  <span>Summary</span>
                  <input
                    value={finding.summary}
                    minLength={10}
                    maxLength={200}
                    onChange={(event) => updateFinding(index, { summary: event.target.value })}
                  />
                </label>
                <label>
                  <span>Evidence and detail</span>
                  <textarea
                    value={finding.detail}
                    minLength={20}
                    rows={4}
                    maxLength={4000}
                    onChange={(event) => updateFinding(index, { detail: event.target.value })}
                  />
                </label>
                {findings.length > 1 && (
                  <button
                    className="icon-button"
                    type="button"
                    title={`Remove finding ${index + 1}`}
                    aria-label={`Remove finding ${index + 1}`}
                    onClick={() =>
                      setFindings((current) =>
                        current.filter((_, findingIndex) => findingIndex !== index),
                      )
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </fieldset>
            ))}
          </div>
          {findings.length < 20 && (
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                setFindings((current) => [...current, emptyFinding(presentation.track_code)])
              }
            >
              <Plus size={16} /> Add finding
            </button>
          )}
          <label>
            <span>Review purpose</span>
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
              checked={evidenceAcknowledged}
              onChange={(event) => setEvidenceAcknowledged(event.target.checked)}
            />
            <span>I reviewed the evidence presented for this exact recommendation and track.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={decisionAcknowledged}
              onChange={(event) => setDecisionAcknowledged(event.target.checked)}
            />
            <span>This finding packet is not a review decision, approval, or authority grant.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ lease, presentation, policyId, policyDigest, findings, purpose })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <FileWarning size={16} />}
            Record recommendation findings
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Recommendation findings unavailable</h3>
            <p>
              The exact reviewer, recommendation, track, lease, browser binding, and signed policy
              must remain current.
            </p>
          </div>
        </div>
      )}
      {record && (
        <div className="package-signing-record" data-testid="recommendation-review-finding-record">
          <div className="section-heading">
            <div>
              <strong>Recommendation finding packet sealed</strong>
              <code>{record.finding_packet_id}</code>
            </div>
            <span className="state-badge approved">
              <BadgeCheck size={14} /> immutable
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Track</span>
              <strong>{record.track_code.replace("review-track.", "").replaceAll("-", " ")}</strong>
            </div>
            <div>
              <span>Findings</span>
              <strong>{record.finding_count}</strong>
            </div>
            <div>
              <span>Storage</span>
              <strong>encrypted</strong>
            </div>
            <div>
              <span>Review decision</span>
              <strong>not recorded</strong>
            </div>
          </div>
          <p className="muted-copy">
            Finding plaintext is sealed outside the application record. Human review completion,
            recommendation approval, workflow, ITSM, and operational authority remain unavailable.
          </p>
        </div>
      )}
    </div>
  );
}
