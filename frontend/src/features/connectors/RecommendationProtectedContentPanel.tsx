import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileLock2, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createRecommendationProtectedContent } from "../../api/recommendationProtectedContent";
import type { RecommendationProtectedInspection } from "../../api/recommendationProtectedInspections";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "42b9ea4db8ff1f29994c124011a97c3d2702f46b0db8a1c1535f76aa3032ae9a",
};

export function RecommendationProtectedContentPanel({
  lease,
}: {
  lease: RecommendationProtectedInspection;
}) {
  const [policyId, setPolicyId] = useState(
    "recommendation-protected-content-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[lease.environment_id] ?? "");
  const [purpose, setPurpose] = useState(
    "Inspect the exact assigned-track recommendation snapshot inside a read-only review boundary.",
  );
  const [contentAcknowledged, setContentAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createRecommendationProtectedContent });
  const presentation = mutation.data?.data;
  const canSubmit =
    contentAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section
      className="target-configuration-panel"
      aria-labelledby="recommendation-protected-content-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED RECOMMENDATION</p>
          <h3 id="recommendation-protected-content-title">Read-only recommendation snapshot</h3>
        </div>
        <FileLock2 size={24} />
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
            <span>Inspection purpose</span>
            <textarea
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              rows={3}
              maxLength={1000}
            />
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={contentAcknowledged}
              onChange={(event) => setContentAcknowledged(event.target.checked)}
            />
            <span>Sensitive redacted recommendation content is displayed as read-only text.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>
              Presentation records no finding, decision, approval, workflow, ITSM record, or
              operational authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ lease, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <FileLock2 size={16} />}
            Present protected recommendation
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Protected recommendation unavailable</h3>
            <p>
              The exact lease, assignee, browser session, track cookie, source lineage, and signed
              presentation policy must remain current.
            </p>
          </div>
        </div>
      )}
      {presentation && (
        <div className="protected-content-record" data-testid="recommendation-protected-content">
          <div className="section-heading">
            <div>
              <strong>Governed recommendation snapshot</strong>
              <code>{presentation.presentation_id}</code>
            </div>
            <span className="state-badge approved">
              <ShieldCheck size={14} /> read-only
            </span>
          </div>
          <div className="mcp-builder-facts" aria-label="Protected recommendation summary">
            <div>
              <span>Track</span>
              <strong>{presentation.track_code.replace("review-track.", "").replaceAll("-", " ")}</strong>
            </div>
            <div>
              <span>Redaction</span>
              <strong>applied</strong>
            </div>
            <div>
              <span>Content</span>
              <strong>{presentation.protected_content_bytes_returned} bytes</strong>
            </div>
            <div>
              <span>Review authority</span>
              <strong>not granted</strong>
            </div>
          </div>
          <pre className="protected-content-text">{presentation.content}</pre>
          <p className="muted-copy">
            Content remains only in this page memory. Atlas renders it as text and does not persist
            plaintext in the presentation record.
          </p>
        </div>
      )}
    </section>
  );
}
