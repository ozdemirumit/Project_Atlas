import { ShieldCheck, Workflow } from "lucide-react";

import type { BootstrapPlan } from "../../api/bootstrapPlan";

export interface BootstrapPlanWorkspaceProps {
  plan: BootstrapPlan;
}

export default function BootstrapPlanWorkspace({ plan }: BootstrapPlanWorkspaceProps) {
  return (
    <section className="workspace-section bootstrap-plan-section">
      <div className="section-heading bootstrap-plan-heading">
        <div>
          <p className="eyebrow">BOOTSTRAP PLAN</p>
          <h2>Ordered deployment phases</h2>
          <p>Exact-input readiness and resume boundaries without execution.</p>
        </div>
        <span className={`state-badge ${plan.state}`}>
          <Workflow size={14} /> {plan.state}
        </span>
      </div>
      <div className="bootstrap-plan-identity">
        <div>
          <span>Plan digest</span>
          <code>{plan.plan_digest.slice(0, 20)}...</code>
        </div>
        <div>
          <span>Resume key</span>
          <code>{plan.resume_key}</code>
        </div>
        <div>
          <span>Phases</span>
          <strong>{plan.phases.length}</strong>
        </div>
      </div>
      <ol className="bootstrap-phase-list">
        {plan.phases.map((phase) => (
          <li key={phase.phase_id}>
            <span className="bootstrap-phase-number">{phase.sequence}</span>
            <div>
              <div className="bootstrap-phase-title">
                <strong>{phase.title}</strong>
                <span className={`state-badge ${phase.state}`}>{phase.state}</span>
              </div>
              <code>{phase.phase_id}</code>
              <p>
                {phase.dependencies.length
                  ? `After ${phase.dependencies.join(", ")}`
                  : "No phase dependency"}
              </p>
              <small>{phase.stop_guidance}</small>
            </div>
          </li>
        ))}
      </ol>
      <div className="safety-notice">
        <ShieldCheck size={16} />
        <span>
          Planning evidence only. No phase, command, rollback, or infrastructure mutation is
          authorized.
        </span>
      </div>
    </section>
  );
}
