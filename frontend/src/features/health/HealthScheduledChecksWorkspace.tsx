import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import type {
  HealthCheckDefinition,
  HealthCheckOverview,
  HealthCheckRun,
} from "../../api/healthChecks";

type HealthCheckSchedule = HealthCheckOverview["schedules"][number];

export interface HealthScheduledChecksWorkspaceProps {
  error: boolean;
  loading: boolean;
  onRunCheck: () => void;
  onSelectDefinition: (definitionId: string) => void;
  overview?: HealthCheckOverview;
  runError: boolean;
  runPending: boolean;
  selectedDefinition?: HealthCheckDefinition;
  selectedRun?: HealthCheckRun;
  selectedSchedule?: HealthCheckSchedule;
}

function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export default function HealthScheduledChecksWorkspace({
  error,
  loading,
  onRunCheck,
  onSelectDefinition,
  overview,
  runError,
  runPending,
  selectedDefinition,
  selectedRun,
  selectedSchedule,
}: HealthScheduledChecksWorkspaceProps) {
  const ready = Boolean(overview && selectedDefinition && selectedSchedule);

  return (
    <section className="workspace-section health-checks-section" aria-live="polite">
      <div className="section-heading health-check-heading">
        <div>
          <p className="eyebrow">SCHEDULED HEALTH CHECKS</p>
          <h2>Governed read-only checks</h2>
        </div>
        <span className="data-profile">
          <Clock3 size={14} /> {overview?.data_profile === "configured_hitachi_read_only"
            ? "Configured Hitachi / read-only"
            : "Deterministic schedule"}
        </span>
      </div>

      {loading && <p className="context-empty">Loading authorized health checks...</p>}
      {error && (
        <p className="inline-alert" role="alert">
          Authorized health-check context is unavailable.
        </p>
      )}
      {!loading && !error && !ready && (
        <div className="reasoning-empty">
          <Activity size={21} />
          <div>
            <strong>No runnable authorized health checks</strong>
            <p>A complete definition and deterministic schedule are required before a run.</p>
          </div>
        </div>
      )}

      {overview && selectedDefinition && selectedSchedule && (
        <>
          <div className="health-check-tabs" role="tablist" aria-label="Health checks">
            {overview.definitions.map((definition) => (
              <button
                key={definition.definition_id}
                type="button"
                role="tab"
                aria-selected={definition.definition_id === selectedDefinition.definition_id}
                className={
                  definition.definition_id === selectedDefinition.definition_id ? "active" : ""
                }
                onClick={() => onSelectDefinition(definition.definition_id)}
              >
                <Activity size={16} />
                <span>{definition.title}</span>
                <small>v{definition.version}</small>
              </button>
            ))}
          </div>

          <div className="health-check-toolbar">
            <div>
              <strong>{selectedDefinition.title}</strong>
              <span>{selectedDefinition.capability_id}</span>
            </div>
            <button
              className="run-check-button"
              type="button"
              disabled={!selectedDefinition.enabled || runPending}
              onClick={onRunCheck}
            >
              {runPending ? (
                <RefreshCw className="spin" size={16} />
              ) : (
                <Play size={16} />
              )}
              {runPending ? "Running" : "Run check"}
            </button>
          </div>

          <div className="health-check-summary">
            <div>
              <span>Schedule</span>
              <strong>Every {selectedSchedule.interval_minutes} min</strong>
              <small>Next {formatTimestamp(selectedSchedule.next_due_at)}</small>
            </div>
            <div>
              <span>Latest run</span>
              <strong className={`run-state ${selectedRun?.state ?? "unknown"}`}>
                {selectedRun?.state.replaceAll("_", " ") ?? "No run"}
              </strong>
              <small>{formatTimestamp(selectedRun?.completed_at)}</small>
            </div>
            <div>
              <span>Boundary</span>
              <strong>{selectedDefinition.capability_class} read-only</strong>
              <small>{selectedDefinition.limits.timeout_seconds}s timeout</small>
            </div>
            <div>
              <span>Evidence</span>
              <strong>{selectedRun?.evidence.length ?? 0} records</strong>
              <small>{selectedRun?.step_count ?? 0} bounded steps</small>
            </div>
          </div>

          {selectedRun && (
            <div className="health-check-detail-grid">
              <div className="health-observations">
                <h3>Latest observations</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Component</th>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>State</th>
                        <th>Freshness</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRun.observations.map((observation) => (
                        <tr key={observation.observation_id}>
                          <td>{observation.component}</td>
                          <td className="mono-cell">{observation.metric}</td>
                          <td>
                            {observation.value}
                            {observation.unit ? ` ${observation.unit}` : ""}
                          </td>
                          <td>
                            <span className={`observation-state ${observation.state}`}>
                              {observation.state === "normal" ? (
                                <CheckCircle2 size={14} />
                              ) : (
                                <AlertTriangle size={14} />
                              )}
                              {observation.state}
                            </span>
                          </td>
                          <td>
                            <span className={`freshness ${observation.freshness}`}>
                              {observation.freshness}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="health-check-findings">
                <h3>Findings and limits</h3>
                {selectedRun.findings.map((finding) => (
                  <article key={finding.finding_id}>
                    <span className={`severity-badge ${finding.severity}`}>
                      {finding.severity}
                    </span>
                    <strong>{finding.title}</strong>
                    <p>{finding.summary}</p>
                  </article>
                ))}
                {selectedRun.partial_reasons.map((reason, index) => (
                  <p className="health-limit-note" key={`partial-${index}-${reason}`}>
                    <CircleHelp size={15} /> {reason}
                  </p>
                ))}
                {selectedRun.unknowns.map((unknown, index) => (
                  <p className="health-unknown" key={`unknown-${index}-${unknown}`}>
                    {unknown}
                  </p>
                ))}
              </div>
            </div>
          )}

          {runError && (
            <p className="inline-alert" role="alert">
              The read-only health check could not run.
            </p>
          )}
          <div className="health-check-safety">
            <ShieldCheck size={16} />
            <span>{overview.safety_notice}</span>
          </div>
        </>
      )}
    </section>
  );
}
