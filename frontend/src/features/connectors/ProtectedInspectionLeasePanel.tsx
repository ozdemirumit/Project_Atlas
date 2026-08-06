import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Eye, LockKeyhole, RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  createOperationalKnowledgeProtectedInspectionLease,
  type InspectionTrack,
} from "../../api/protectedInspections";
import type { OperationalKnowledgeReviewerAssignment } from "../../api/reviewerAssignments";

const POLICY_DIGESTS: Record<string, string> = {
  "environment.development":
    "94ab5739197fe27b5714035c7fba489ccc618a7c7808c7866fdbc799a080a8ed",
  "environment.test": "a6ac813e2dfa0abd709694549bedff52d21a40eb2a1ca87371350b20b6394fc5",
};

export function ProtectedInspectionLeasePanel({
  assignment,
}: {
  assignment: OperationalKnowledgeReviewerAssignment;
}) {
  const [trackCode, setTrackCode] = useState<InspectionTrack>("review-track.domain");
  const [policyId, setPolicyId] = useState(
    "operational-knowledge-protected-inspection-policy.development",
  );
  const [policyDigest, setPolicyDigest] = useState(
    POLICY_DIGESTS[assignment.environment_id] ?? "",
  );
  const [purpose, setPurpose] = useState(
    "Open one short-lived assigned-track inspection boundary without returning content.",
  );
  const [acknowledged, setAcknowledged] = useState(false);
  const mutation = useMutation({
    mutationFn: createOperationalKnowledgeProtectedInspectionLease,
  });
  const lease = mutation.data?.data;
  const canSubmit =
    acknowledged &&
    /^[a-z][a-z0-9_.:-]{2,127}$/.test(policyId) &&
    /^[a-f0-9]{64}$/.test(policyDigest) &&
    purpose.trim().length >= 20 &&
    !mutation.isPending;

  return (
    <section className="target-configuration-panel" aria-labelledby="inspection-lease-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PROTECTED INSPECTION</p>
          <h3 id="inspection-lease-title">Inspection lease</h3>
        </div>
        <Eye size={24} />
      </div>
      {!lease && (
        <>
          <div className="segmented-control" role="group" aria-label="Inspection track">
            <button
              type="button"
              className={trackCode === "review-track.domain" ? "active" : ""}
              aria-pressed={trackCode === "review-track.domain"}
              onClick={() => setTrackCode("review-track.domain")}
            >
              Domain
            </button>
            <button
              type="button"
              className={trackCode === "review-track.security" ? "active" : ""}
              aria-pressed={trackCode === "review-track.security"}
              onClick={() => setTrackCode("review-track.security")}
            >
              Security
            </button>
          </div>
          <div className="mcp-builder-review-fields">
            <label>
              <span>Inspection policy ID</span>
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
              This opens a short-lived browser-bound channel for the exact assigned reviewer. It
              returns no content or secret in JSON and records no finding, decision, or approval.
            </span>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate({ assignment, trackCode, policyId, policyDigest, purpose })
            }
          >
            {mutation.isPending ? <RefreshCw className="spin" size={16} /> : <Eye size={16} />}
            Open inspection lease
          </button>
        </>
      )}
      {mutation.isError && (
        <div className="workspace-message error-state" role="alert">
          <AlertTriangle size={20} />
          <div>
            <h3>Inspection lease unavailable</h3>
            <p>
              The current identity must be the exact unexpired assignee for this track with recent
              hardware MFA. Claimed uncertain attempts are not retried automatically.
            </p>
          </div>
        </div>
      )}
      {lease && (
        <div className="package-signing-record">
          <div className="section-heading">
            <div>
              <strong>{lease.title}</strong>
              <code>{lease.lease_id}</code>
            </div>
            <span className="state-badge approved">
              <LockKeyhole size={14} /> lease active
            </span>
          </div>
          <div className="mcp-builder-facts">
            <div>
              <span>Track</span>
              <strong>{lease.track_code.replace("review-track.", "")}</strong>
            </div>
            <div>
              <span>Browser binding</span>
              <strong>verified</strong>
            </div>
            <div>
              <span>Content disclosed</span>
              <strong>none</strong>
            </div>
            <div>
              <span>Review decision</span>
              <strong>not recorded</strong>
            </div>
          </div>
          <p className="muted-copy">
            <LockKeyhole size={14} /> The lease secret is held in a protected browser cookie.
            Content presentation and review decisions remain separate controlled stages.
          </p>
        </div>
      )}
    </section>
  );
}
