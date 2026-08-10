import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import type { SecurityExportOverview } from "../../api/securityExport";

export interface SecurityExportWorkspaceProps {
  error: boolean;
  loading: boolean;
  onSendTestEvent: () => void;
  overview?: SecurityExportOverview;
  testDelivered: boolean;
  testError: boolean;
  testPending: boolean;
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return "No handoff yet";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export default function SecurityExportWorkspace({
  error,
  loading,
  onSendTestEvent,
  overview,
  testDelivered,
  testError,
  testPending,
}: SecurityExportWorkspaceProps) {
  const destination = overview?.destinations[0];
  const health = overview?.health[0];
  const ready = Boolean(overview && destination && health);

  return (
    <section className="workspace-section security-export-section" aria-live="polite">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SECURITY EXPORT</p>
          <h2>Syslog and SIEM delivery</h2>
        </div>
        {destination && (
          <span className={`security-export-state ${health?.state ?? "active"}`}>
            <ShieldCheck size={14} /> {health?.state ?? "active"}
          </span>
        )}
      </div>

      {loading && (
        <div className="impact-message">
          <Clock3 size={18} /> Reading authorized export health
        </div>
      )}
      {error && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={18} /> Export health is unavailable; no delivery is inferred.
        </div>
      )}
      {!loading && !error && !ready && (
        <div className="impact-message impact-error" role="alert">
          <AlertTriangle size={18} /> A complete authorized destination and health record are
          required.
        </div>
      )}

      {overview && destination && health && (
        <>
          <div className="security-export-grid">
            <div className="security-destination">
              <span>Destination</span>
              <strong>{destination.name}</strong>
              <small>
                {destination.host}:{destination.port}
              </small>
            </div>
            <div>
              <span>Transport</span>
              <strong>TLS</strong>
              <small>Server and hostname verified</small>
            </div>
            <div>
              <span>Certificate</span>
              <strong>{health.certificate_days_remaining} days</strong>
              <small>Until expiry</small>
            </div>
            <div>
              <span>Queue</span>
              <strong>{health.queue_depth}</strong>
              <small>{health.retrying_count} retrying</small>
            </div>
            <div>
              <span>Transport handoffs</span>
              <strong>{health.delivered_count}</strong>
              <small>{health.dead_letter_count} dead-letter</small>
            </div>
          </div>

          <div className="security-export-detail">
            <div>
              <h3>RFC 5424 preview</h3>
              <p className="security-payload">{overview.preview_message.payload}</p>
              <small>
                {overview.mapping_version} Â· {overview.preview_message.payload_bytes} bytes Â· digest{" "}
                {overview.preview_message.content_digest.slice(0, 16)}â€¦
              </small>
            </div>
            <div className="security-export-action">
              <dl>
                <div>
                  <dt>Collector handoff</dt>
                  <dd>{formatTimestamp(health.last_transport_handoff_at)}</dd>
                </div>
                <div>
                  <dt>SIEM ingestion</dt>
                  <dd>Not confirmed</dd>
                </div>
              </dl>
              <button
                className="run-check-button"
                type="button"
                disabled={testPending}
                onClick={onSendTestEvent}
              >
                {testPending ? (
                  <RefreshCw className="spin" size={16} />
                ) : (
                  <Play size={16} />
                )}
                {testPending ? "Sending" : "Send test event"}
              </button>
            </div>
          </div>

          {testDelivered && (
            <div className="security-export-result" role="status">
              <CheckCircle2 size={16} />
              Transport handoff recorded. SIEM ingestion remains unconfirmed.
            </div>
          )}
          {testError && (
            <div className="security-export-result error-state" role="alert">
              <AlertTriangle size={16} /> Test event was not delivered.
            </div>
          )}
          {health.limitations.map((limitation, index) => (
            <p className="health-limit-note" key={`security-limit-${index}-${limitation}`}>
              {limitation}
            </p>
          ))}
          <div className="safety-notice">
            <ShieldCheck size={16} />
            <span>{overview.safety_notice}</span>
          </div>
        </>
      )}
    </section>
  );
}

