import { LockKeyhole } from "lucide-react";

import type { BootstrapState } from "../../api/bootstrapState";

export interface BootstrapCheckpointWorkspaceProps {
  formatTimestamp: (timestamp: string | undefined) => string;
  state: BootstrapState;
}

function leaseLabel(state: BootstrapState): string {
  if (state.lease_available) return "Available";
  return state.lease_held_by_current_actor
    ? "Held by this session"
    : "Held by another operator";
}

export default function BootstrapCheckpointWorkspace({
  formatTimestamp,
  state,
}: BootstrapCheckpointWorkspaceProps) {
  const run = state.run;

  return (
    <>
      <div className="section-heading bootstrap-state-heading">
        <div>
          <p className="eyebrow">BOOTSTRAP CHECKPOINTS</p>
          <h2>Resume and lease state</h2>
          <p>Coordination metadata only; loading this view never claims a lease.</p>
        </div>
        <span className={`state-badge ${state.durable ? "ready" : "warning"}`}>
          <LockKeyhole size={14} />
          {state.durable ? "durable" : "development memory"}
        </span>
      </div>
      {run ? (
        <>
          <div className="bootstrap-state-summary">
            <div>
              <span>Run</span>
              <code>{run.run_id}</code>
            </div>
            <div>
              <span>Revision</span>
              <strong>{run.version}</strong>
            </div>
            <div>
              <span>Completed</span>
              <strong>
                {run.completed_phase_ids.length}/{run.phase_ids.length}
              </strong>
            </div>
            <div>
              <span>Lease</span>
              <strong>{leaseLabel(state)}</strong>
            </div>
          </div>
          <div className="bootstrap-checkpoint-grid" aria-label="Bootstrap checkpoint progress">
            {run.phase_ids.map((phaseId, index) => {
              const checkpoint = run.checkpoints.find((item) => item.phase_id === phaseId);
              const phaseState =
                checkpoint?.state ?? (run.current_phase_id === phaseId ? "current" : "pending");
              return (
                <div className={`bootstrap-checkpoint ${phaseState}`} key={phaseId}>
                  <span>{index + 1}</span>
                  <div>
                    <code>{phaseId}</code>
                    <strong>{phaseState}</strong>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="bootstrap-state-detail">
            <div>
              <span>Plan digest</span>
              <code>{run.plan_digest.slice(0, 20)}...</code>
            </div>
            <div>
              <span>Lease expiry</span>
              <strong>{formatTimestamp(run.lease_expires_at ?? undefined)}</strong>
            </div>
          </div>
        </>
      ) : (
        <div className="bootstrap-state-empty">
          <LockKeyhole size={18} />
          <div>
            <strong>No checkpoint state has been initialized.</strong>
            <p>The approved plan remains read-only and no lease is held.</p>
          </div>
        </div>
      )}
    </>
  );
}
