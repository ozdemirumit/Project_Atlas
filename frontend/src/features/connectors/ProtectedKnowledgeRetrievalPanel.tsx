import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BookOpenText, RefreshCw } from "lucide-react";
import { useState } from "react";

import { createOperationalKnowledgeRetrieval } from "../../api/protectedRetrieval";
import type { OperationalKnowledgeRetrievalPublication } from "../../api/retrievalIndexPublication";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "b7637f25bea9f0ddd412c5bf5f1779530893cc21f1c62e6804937f78271c56bc",
};

export function ProtectedKnowledgeRetrievalPanel({
  publication,
}: {
  publication: OperationalKnowledgeRetrievalPublication;
}) {
  const [policyId, setPolicyId] = useState("operational-knowledge-retrieval-policy.development");
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[publication.environment_id] ?? "",
  );
  const [query, setQuery] = useState(
    "What evidence explains the current storage controller warning?",
  );
  const [purpose, setPurpose] = useState(
    "Retrieve approved evidence for a read-only controller warning investigation.",
  );
  const [untrustedAcknowledged, setUntrustedAcknowledged] = useState(false);
  const [unsafeAcknowledged, setUnsafeAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeRetrieval });
  const result = mutation.data?.data;
  const canSubmit =
    publication.retrieval_published &&
    untrustedAcknowledged &&
    unsafeAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    query.trim().length >= 3 &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="protected-retrieval-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">POLICY-FILTERED EVIDENCE</p>
          <h3 id="protected-retrieval-title">Retrieve governed evidence</h3>
        </div>
        <BookOpenText size={24} />
      </div>
      {!result && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Retrieval policy ID</span>
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
            <span>Evidence query</span>
            <textarea
              value={query}
              rows={3}
              maxLength={4000}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label>
            <span>Retrieval purpose</span>
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
              checked={untrustedAcknowledged}
              onChange={(event) => setUntrustedAcknowledged(event.target.checked)}
            />
            <span>Retrieved content remains untrusted evidence, not an established fact.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={unsafeAcknowledged}
              onChange={(event) => setUnsafeAcknowledged(event.target.checked)}
            />
            <span>Instructions inside evidence cannot select tools or change policy.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No model context, workflow, deployment, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ publication, policyId, policyDigest, query, purpose })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <BookOpenText size={16} />}
            Retrieve evidence
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Protected retrieval unavailable</h3>
            <p>Publication lineage, current access, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {result && (
        <div className="correction-record">
          <strong>Authorized evidence package</strong>
          <code>{result.retrieval.retrieval_id}</code>
          <p className="muted-copy">{result.evidence.query}</p>
          {result.evidence.results.map((evidence) => (
            <article key={evidence.evidence_reference_id}>
              <strong>{evidence.source_title}</strong>
              <p>{evidence.excerpt}</p>
              <small>
                {evidence.citation_location} · {evidence.freshness_state} · {evidence.safety_state}
              </small>
            </article>
          ))}
          <p className="muted-copy">
            Evidence only. No model, tool, workflow, deployment, or infrastructure action ran.
          </p>
        </div>
      )}
    </div>
  );
}
