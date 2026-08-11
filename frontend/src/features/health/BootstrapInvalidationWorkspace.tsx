import { Scale } from "lucide-react";

import type { BootstrapInvalidationPreview } from "../../api/bootstrapInvalidation";

export interface BootstrapInvalidationWorkspaceProps {
  preview: BootstrapInvalidationPreview;
}

export default function BootstrapInvalidationWorkspace({
  preview,
}: BootstrapInvalidationWorkspaceProps) {
  return (
    <>
      <div className="section-heading bootstrap-invalidation-heading">
        <div>
          <p className="eyebrow">RESUME SAFETY</p>
          <h2>Checkpoint invalidation preview</h2>
          <p>Candidate inputs compared with the current run without changing it.</p>
        </div>
        <span className={`state-badge ${preview.state}`}>
          <Scale size={14} /> {preview.state}
        </span>
      </div>
      {preview.state === "empty" ? (
        <div className="bootstrap-state-empty">
          <Scale size={18} />
          <div>
            <strong>No current run is available for drift comparison.</strong>
            <p>Initialize governed checkpoint state before evaluating resume safety.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="bootstrap-invalidation-summary">
            <div>
              <span>Source revision</span>
              <strong>{preview.source_run_version}</strong>
            </div>
            <div>
              <span>Earliest boundary</span>
              <code>{preview.earliest_affected_phase_id ?? "none"}</code>
            </div>
            <div>
              <span>Reusable</span>
              <strong>{preview.reusable_checkpoint_phase_ids.length}</strong>
            </div>
            <div>
              <span>Invalidated</span>
              <strong>{preview.invalidated_checkpoint_phase_ids.length}</strong>
            </div>
          </div>
          {preview.changes.length > 0 && (
            <div className="bootstrap-change-list">
              {preview.changes.map((change, index) => (
                <article
                  key={`${change.reason_code}:${change.field}:${change.earliest_affected_phase_id}:${index}`}
                >
                  <div>
                    <code>{change.reason_code}</code>
                    <strong>{change.field.replaceAll("_", " ")}</strong>
                  </div>
                  <span>from {change.earliest_affected_phase_id}</span>
                </article>
              ))}
            </div>
          )}
          <div className="bootstrap-invalidation-columns">
            <div>
              <h3>Reusable checkpoints</h3>
              <p>{preview.reusable_checkpoint_phase_ids.join(", ") || "None"}</p>
            </div>
            <div>
              <h3>Invalidated checkpoints</h3>
              <p>{preview.invalidated_checkpoint_phase_ids.join(", ") || "None"}</p>
            </div>
            <div>
              <h3>Downstream review</h3>
              <p>{preview.downstream_phase_ids.join(", ") || "None"}</p>
            </div>
          </div>
        </>
      )}
    </>
  );
}
