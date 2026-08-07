import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Eye, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createOperationalKnowledgeFindingPresentation } from "../../api/findingPresentations";
import type { OperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";
import type { OperationalKnowledgeReviewFinding } from "../../api/reviewFindings";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "84b3f45594737cfb3218e4f51bb3e873174cdc2c34d84ce070073113d44fd168",
};

export function FindingPresentationPanel({
  lease,
  contentPresentation,
  finding,
}: {
  lease: OperationalKnowledgeProtectedInspectionLease;
  contentPresentation: OperationalKnowledgeProtectedContent;
  finding: OperationalKnowledgeReviewFinding;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-finding-presentation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[finding.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Inspect the exact sealed findings before recording a track decision.",
  );
  const [sensitiveAcknowledged, setSensitiveAcknowledged] = useState(false);
  const [decisionAcknowledged, setDecisionAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeFindingPresentation });
  const presentation = mutation.data?.data;
  const canSubmit =
    sensitiveAcknowledged &&
    decisionAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="finding-presentation-panel" aria-labelledby="finding-presentation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SEALED FINDINGS</p>
          <h3 id="finding-presentation-title">Protected finding presentation</h3>
        </div>
        <Eye size={24} />
      </div>
      {!presentation && (
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
            <span>Presentation purpose</span>
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
            <span>These sealed reviewer observations are sensitive and read-only.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={decisionAcknowledged}
              onChange={(event) => setDecisionAcknowledged(event.target.checked)}
            />
            <span>Presenting findings does not record a decision, approval, or authority.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                lease,
                contentPresentation,
                finding,
                policyId,
                policyDigest,
                purpose,
              })
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
            <p>The exact reviewer, lease, browser binding, track cookie, and artifact must remain current.</p>
          </div>
        </div>
      )}
      {presentation && (
        <div className="finding-presentation-record">
          <div className="section-heading">
            <div>
              <strong>Exact finding packet presented</strong>
              <code>{presentation.finding_presentation_id}</code>
            </div>
            <span className="state-badge approved">
              <ShieldCheck size={14} /> read-only
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Track</span>
              <strong>{presentation.track_code.replace("review-track.", "")}</strong>
            </div>
            <div>
              <span>Findings</span>
              <strong>{presentation.finding_count}</strong>
            </div>
            <div>
              <span>Integrity</span>
              <strong>verified</strong>
            </div>
            <div>
              <span>Review decision</span>
              <strong>not recorded</strong>
            </div>
          </div>
          <div className="presented-finding-list">
            {presentation.findings.map((item, index) => (
              <article className="presented-finding" key={`${item.category_code}-${index + 1}`}>
                <div className="presented-finding-heading">
                  <strong>Finding {index + 1}</strong>
                  <span>{item.severity_code.replace("finding-severity.", "")}</span>
                </div>
                <span className="presented-finding-category">
                  {item.category_code.replace("finding-category.", "")}
                </span>
                <h4>{item.summary}</h4>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <p className="muted-copy">
            Finding text exists only in this protected response and page memory. Decision,
            approval, publication, workflow, and operational authority remain unavailable.
          </p>
        </div>
      )}
    </div>
  );
}
