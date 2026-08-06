import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileLock2, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { createOperationalKnowledgeProtectedContent } from "../../api/protectedContent";
import type { OperationalKnowledgeProtectedInspectionLease } from "../../api/protectedInspections";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "c00b22d070bd43ce544ba714bd67beabfc4b6f1c6e9b582a1ded0c019e0023c4",
};

export function ProtectedContentPanel({
  lease,
}: {
  lease: OperationalKnowledgeProtectedInspectionLease;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-protected-content-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(POLICY_DIGESTS[lease.environment_id] ?? "");
  const [purpose, setPurpose] = useState(
    "Inspect the exact assigned-track operational knowledge snapshot in a read-only boundary.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeProtectedContent });
  const presentation = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section className="target-configuration-panel" aria-labelledby="protected-content-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED CONTENT</p>
          <h3 id="protected-content-title">Read-only snapshot</h3>
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
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>
              This displays sensitive redacted content as read-only text. It records no finding,
              decision, approval, publication, workflow, or operational authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ lease, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <FileLock2 size={16} />}
            Present protected content
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Protected content unavailable</h3>
            <p>
              The exact lease, assignee, browser session, track cookie, and artifact must remain
              current.
            </p>
          </div>
        </div>
      )}
      {presentation && (
        <div className="protected-content-record">
          <div className="section-heading">
            <div>
              <strong>{presentation.title}</strong>
              <code>{presentation.presentation_id}</code>
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
              <span>Redaction</span>
              <strong>applied</strong>
            </div>
            <div>
              <span>Content</span>
              <strong>{presentation.content_bytes} bytes</strong>
            </div>
            <div>
              <span>Review decision</span>
              <strong>not recorded</strong>
            </div>
          </div>
          <pre className="protected-content-text">{presentation.content}</pre>
          <p className="muted-copy">
            Content is held only in this page memory and is not rendered as HTML or persisted by
            Atlas.
          </p>
        </div>
      )}
    </section>
  );
}
