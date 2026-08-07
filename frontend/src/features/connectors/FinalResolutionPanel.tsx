import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Gavel, RefreshCw, XCircle } from "lucide-react";
import { useState } from "react";

import { createOperationalKnowledgeFinalResolution } from "../../api/finalResolutions";
import type { OperationalKnowledgeTrackReviewDecision } from "../../api/reviewDecisions";
import { PublicationPreparationPanel } from "./PublicationPreparationPanel";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "47a0ab94067d3767933d9f6115c373dfdbfe98049d854d58688724c5135e7590",
};

export function FinalResolutionPanel({
  decision,
}: {
  decision: OperationalKnowledgeTrackReviewDecision;
}) {
  const [disposition, setDisposition] = useState<
    "final-resolution.approved" | "final-resolution.rejected"
  >("final-resolution.approved");
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-final-resolution-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[decision.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Record the accountable final resolution for this exact passed review generation.",
  );
  const [generationAcknowledged, setGenerationAcknowledged] = useState(false);
  const [readinessAcknowledged, setReadinessAcknowledged] = useState(false);
  const [authorityAcknowledged, setAuthorityAcknowledged] = useState(false);
  const mutation = useMutation({ mutationFn: createOperationalKnowledgeFinalResolution });
  const resolution = mutation.data?.data;
  const canSubmit =
    decision.all_tracks_passed &&
    !decision.any_correction_required &&
    generationAcknowledged &&
    readinessAcknowledged &&
    authorityAcknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <div className="final-resolution-panel" aria-labelledby="final-resolution-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">FINAL KNOWLEDGE REVIEW</p>
          <h3 id="final-resolution-title">Resolve passed generation</h3>
        </div>
        <Gavel size={24} />
      </div>
      {!resolution && (
        <>
          <div className="segmented-control" aria-label="Final resolution">
            <button
              type="button"
              className={disposition === "final-resolution.approved" ? "active" : ""}
              onClick={() => setDisposition("final-resolution.approved")}
            >
              <CheckCircle2 size={16} /> Approve
            </button>
            <button
              type="button"
              className={disposition === "final-resolution.rejected" ? "active" : ""}
              onClick={() => setDisposition("final-resolution.rejected")}
            >
              <XCircle size={16} /> Reject
            </button>
          </div>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Final resolution policy ID</span>
              <input value={policyId} onChange={(event) => setPolicyId(event.target.value)} />
            </label>
            <label>
              <span>Signed policy digest</span>
              <input value={policyDigest} onChange={(event) => setPolicyDigest(event.target.value)} spellCheck={false} />
            </label>
          </div>
          <label>
            <span>Resolution purpose</span>
            <textarea value={purpose} rows={3} maxLength={1000} onChange={(event) => setPurpose(event.target.value)} />
          </label>
          <label className="approval-check">
            <input type="checkbox" checked={generationAcknowledged} onChange={(event) => setGenerationAcknowledged(event.target.checked)} />
            <span>The exact passed review generation is immutable.</span>
          </label>
          <label className="approval-check">
            <input type="checkbox" checked={readinessAcknowledged} onChange={(event) => setReadinessAcknowledged(event.target.checked)} />
            <span>Approval establishes publication readiness only.</span>
          </label>
          <label className="approval-check">
            <input type="checkbox" checked={authorityAcknowledged} onChange={(event) => setAuthorityAcknowledged(event.target.checked)} />
            <span>No publication, retrieval, workflow, or operational authority is granted.</span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({
                decision,
                dispositionCode: disposition,
                basisCodes: [
                  "final-basis.domain-and-security-passed",
                  disposition === "final-resolution.approved"
                    ? "final-basis.governance-scope-accepted"
                    : "final-basis.governance-scope-rejected",
                ],
                policyId,
                policyDigest,
                purpose,
              })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Gavel size={16} />}
            Record final resolution
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Final resolution unavailable</h3>
            <p>Both passed tracks, independent approver authority, browser binding, and policy must remain valid.</p>
          </div>
        </div>
      )}
      {resolution && (
        <>
          <div className="correction-record">
            <strong>{resolution.knowledge_approved ? "Knowledge approved" : "Generation rejected"}</strong>
            <code>{resolution.resolution_id}</code>
            <p className="muted-copy">
              {resolution.publication_ready
                ? "Ready for a separate publication process. Nothing was published or indexed."
                : "Rejected for this exact generation. No correction or replacement was created."}
            </p>
          </div>
          {resolution.knowledge_approved && resolution.publication_ready && (
            <PublicationPreparationPanel resolution={resolution} />
          )}
        </>
      )}
    </div>
  );
}
