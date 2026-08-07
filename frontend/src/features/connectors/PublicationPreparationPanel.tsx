import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileCheck2, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { OperationalKnowledgeFinalResolution } from "../../api/finalResolutions";
import { createOperationalKnowledgePublicationPreparation } from "../../api/publicationPreparations";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "deb001adcf98b8ab646ec839dcfaa1f3cfbf7e26a9b775596b95853d9fc218ea",
};

export function PublicationPreparationPanel({
  resolution,
}: {
  resolution: OperationalKnowledgeFinalResolution;
}) {
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-publication-preparation-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[resolution.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Prepare immutable metadata for the exact approved knowledge generation.",
  );
  const [generationAcknowledged, setGenerationAcknowledged] = useState(false);
  const [metadataOnlyAcknowledged, setMetadataOnlyAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({
    mutationFn: createOperationalKnowledgePublicationPreparation,
  });
  const preparation = mutation.data?.data;
  const canSubmit =
    resolution.knowledge_approved &&
    resolution.publication_ready &&
    generationAcknowledged &&
    metadataOnlyAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="publication-preparation-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PUBLICATION PREPARATION</p>
          <h3 id="publication-preparation-title">Bind metadata-only plan</h3>
        </div>
        <FileCheck2 size={24} />
      </div>
      {!preparation && (
        <>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Preparation policy ID</span>
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
            <span>Preparation purpose</span>
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
              checked={generationAcknowledged}
              onChange={(event) => setGenerationAcknowledged(event.target.checked)}
            />
            <span>The exact approved generation is immutable.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={metadataOnlyAcknowledged}
              onChange={(event) => setMetadataOnlyAcknowledged(event.target.checked)}
            />
            <span>This step creates signed metadata only.</span>
          </label>
          <label className="approval-check">
            <input
              type="checkbox"
              checked={authorityAcknowledged}
              onChange={(event) => setAuthorityAcknowledged(event.target.checked)}
            />
            <span>No chunking, embedding, indexing, retrieval, workflow, or operation is authorized.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ resolution, policyId, policyDigest, purpose })
            }
          >
            {mutation.isPending ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <FileCheck2 size={16} />
            )}
            Prepare publication metadata
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Publication preparation unavailable</h3>
            <p>Approval lineage, steward separation, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {preparation && (
        <div className="correction-record">
          <strong>Publication metadata prepared</strong>
          <code>{preparation.preparation_id}</code>
          <p className="muted-copy">
            Signed profiles are bound. No content was chunked, embedded, indexed, or published.
          </p>
        </div>
      )}
    </div>
  );
}
