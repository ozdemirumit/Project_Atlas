import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, FileWarning, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  createOperationalKnowledgeReviewFinding,
  type OperationalKnowledgeReviewFindingItem,
  type ReviewFindingTrack,
} from "../../api/reviewFindings";
import type { OperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import { FindingPresentationPanel } from "./FindingPresentationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "a75b0d4793e099271c6ae1ccdb56bc279babe4489855488c9bc93dcf80947552",
};

const categories: Record<ReviewFindingTrack, readonly { value: string; label: string }[]> = {
  "review-track.domain": [
    { value: "finding-category.accuracy", label: "Accuracy" },
    { value: "finding-category.completeness", label: "Completeness" },
    { value: "finding-category.applicability", label: "Applicability" },
    { value: "finding-category.operational-safety", label: "Operational safety" },
    { value: "finding-category.evidence-conflict", label: "Evidence conflict" },
    { value: "finding-category.clarity", label: "Clarity" },
  ],
  "review-track.security": [
    { value: "finding-category.data-exposure", label: "Data exposure" },
    { value: "finding-category.privilege", label: "Privilege" },
    { value: "finding-category.prompt-injection", label: "Prompt injection" },
    { value: "finding-category.malware", label: "Malware" },
    { value: "finding-category.supply-chain", label: "Supply chain" },
    { value: "finding-category.policy-compliance", label: "Policy compliance" },
  ],
};

const severities = [
  { value: "finding-severity.observation", label: "Observation" },
  { value: "finding-severity.minor", label: "Minor" },
  { value: "finding-severity.material", label: "Material" },
  { value: "finding-severity.critical", label: "Critical" },
] as const;

function emptyFinding(track: ReviewFindingTrack): OperationalKnowledgeReviewFindingItem {
  return {
    category_code:
      track === "review-track.domain"
        ? "finding-category.accuracy"
        : "finding-category.data-exposure",
    severity_code: severities[0].value,
    summary: "",
    detail: "",
  };
}

export function ReviewFindingPanel({
  lease,
  presentation,
}: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  presentation: OperationalKnowledgeProtectedContent;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-review-finding-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[presentation.environment_id] ?? "");
  const [findings, setFindings] = useState<OperationalKnowledgeReviewFindingItem[]>([
    emptyFinding(presentation.track_code),
  ]);
  const [purpose, setPurpose] = useState(
    "Record bounded reviewer observations without creating a review decision.",
  );
  const [evidenceAcknowledged, setEvidenceAcknowledged] = useState(false);
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeReviewFinding });
  const record = mutation.data?.data;
  const canSubmit =
    evidenceAcknowledged &&
    decisionAcknowledged &&
    findings.every(
      (finding) =>
        finding.summary.trim().length > 0 &&
        finding.detail.trim().length > 0 &&
        finding.summary.length <= 200 &&
        finding.detail.length <= 4000,
    ) &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  function updateFinding(index: number, patch: Partial<OperationalKnowledgeReviewFindingItem>) {
    setFindings((current) =>
      current.map((finding, findingIndex) =>
        findingIndex === index ? { ...finding, ...patch } : finding,
      ),
    );
  }

  return (
    <div className="review-finding-panel" aria-labelledby="review-finding-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">TRACK FINDINGS</p>
          <h3 id="review-finding-title">Reviewer observations</h3>
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
              <fieldset className="review-finding-item" key={`finding-${index + 1}`}>
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
                    maxLength={200}
                    onChange={(event) => updateFinding(index, { summary: event.target.value })}
                  />
                </label>
                <label>
                  <span>Evidence and detail</span>
                  <textarea
                    value={finding.detail}
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
            <span>I reviewed the evidence presented for this exact track and lease.</span>
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
            Record findings
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Review finding unavailable</h3>
            <p>The exact reviewer, track, lease, browser binding, and signed policy must remain current.</p>
          </div>
        </div>
      )}
      {record && (
        <>
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>Finding packet sealed</strong>
              <code>{record.finding_packet_id}</code>
            </div>
            <span className="state-badge approved">
              <BadgeCheck size={14} /> immutable
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div><span>Track</span><strong>{record.track_code.replace("review-track.", "")}</strong></div>
            <div><span>Findings</span><strong>{record.finding_count}</strong></div>
            <div><span>Storage</span><strong>encrypted</strong></div>
            <div><span>Review decision</span><strong>not recorded</strong></div>
          </div>
          <p className="muted-copy">
            Finding text remains sealed until a separately governed protected presentation.
            Decision, approval, publication, workflow, and operational authority remain
            unavailable.
          </p>
        </div>
        <FindingPresentationPanel
          lease={lease}
          contentPresentation={presentation}
          finding={record}
        />
        </>
      )}
    </div>
  );
}
