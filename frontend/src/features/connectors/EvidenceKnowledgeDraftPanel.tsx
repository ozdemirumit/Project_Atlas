import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BookMarked, FileCheck2, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  createOperationalEvidenceKnowledgeDraft,
} from "../../api/evidenceDrafts";
import type { ConnectorInvocationEvidence } from "../../api/invocationEvidence";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "f2c502a3c820e5f239ac5230137bde9c4817957a340d44ad36e8fd4e880168e8",
  "environment.test": "6d8306c449bd4b5528a52d5f5c7d3cfaa9730ac0bdc662f715b658f9adc1232e",
};

export function EvidenceKnowledgeDraftPanel({
  evidence,
}: {
  evidence: ConnectorInvocationEvidence;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-evidence-knowledge-draft-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[evidence.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Create a governed review-only draft from exact operational evidence.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalEvidenceKnowledgeDraft });
  const draft = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section
      className="target-configuration-panel evidence-knowledge-draft-panel"
      aria-labelledby="evidence-knowledge-draft-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">KNOWLEDGE CURATION</p>
          <h3 id="evidence-knowledge-draft-title">Knowledge draft curation</h3>
        </div>
        <BookMarked size={24} />
      </div>
      {!draft && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Curation policy ID</span>
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
            <span>Curation purpose</span>
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
              The result is an unapproved, non-retrievable draft. It is not reviewed, indexed,
              model context, published knowledge, a workflow continuation, or operational authority.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() => mutation.mutate({ evidence, policyId, policyDigest, purpose })}
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <BookMarked size={16} />}
            Create review draft
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Draft curation unavailable</h3>
            <p>
              Evidence lineage, inherited governance, draft integrity, or cleanup validation failed.
              A claimed uncertain attempt is not retried automatically.
            </p>
          </div>
        </div>
      )}
      {draft && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{draft.title}</strong>
              <code>{draft.knowledge_item_id}</code>
            </div>
            <span className="state-badge neutral">
              <FileCheck2 size={14} />draft
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Lifecycle</span>
              <strong>draft</strong>
            </div>
            <div>
              <span>Classification</span>
              <strong>{draft.classification.replace("classification.", "")}</strong>
            </div>
            <div>
              <span>Review</span>
              <strong>pending</strong>
            </div>
            <div>
              <span>Retrieval</span>
              <strong>not published</strong>
            </div>
          </div>
          <p className="muted-copy">
            Draft governance is inherited from the evidence package. Content review, approval,
            indexing, retrieval publication, and model use remain separate controlled stages.
          </p>
        </div>
      )}
    </section>
  );
}
