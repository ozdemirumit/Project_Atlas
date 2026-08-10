import { PackageCheck, ShieldCheck } from "lucide-react";

import type {
  ReleasePreflight,
  ReleasePreflightMode,
  ReleasePreflightProfile,
} from "../../api/releasePreflight";

export interface ReleasePreflightWorkspaceProps {
  mode: ReleasePreflightMode;
  onModeChange: (mode: ReleasePreflightMode) => void;
  onProfileChange: (profile: ReleasePreflightProfile) => void;
  preflight: ReleasePreflight;
  profile: ReleasePreflightProfile;
}

export default function ReleasePreflightWorkspace({
  mode,
  onModeChange,
  onProfileChange,
  preflight,
  profile,
}: ReleasePreflightWorkspaceProps) {
  return (
    <section className="workspace-section release-preflight-section">
      <div className="section-heading release-preflight-heading">
        <div>
          <p className="eyebrow">RELEASE READINESS</p>
          <h2>Read-only deployment preflight</h2>
          <p>Immutable artifact and host checks before any installation activity.</p>
        </div>
        <span className={`state-badge ${preflight.state}`}>
          <PackageCheck size={14} /> {preflight.state}
        </span>
      </div>
      <div className="release-preflight-controls">
        <label>
          <span>Acquisition mode</span>
          <select
            aria-label="Release acquisition mode"
            value={mode}
            onChange={(event) => onModeChange(event.target.value as ReleasePreflightMode)}
          >
            <option value="connected">Connected</option>
            <option value="mirrored">Mirrored</option>
            <option value="offline">Offline</option>
          </select>
        </label>
        <label>
          <span>Deployment profile</span>
          <select
            aria-label="Release deployment profile"
            value={profile}
            onChange={(event) => onProfileChange(event.target.value as ReleasePreflightProfile)}
          >
            <option value="developer">Developer</option>
            <option value="linux_lab">Linux lab</option>
          </select>
        </label>
        <div className="release-identity">
          <span>Release</span>
          <strong>{preflight.release_version}</strong>
          <code>{preflight.build_id}</code>
        </div>
        <div className="release-identity">
          <span>Manifest</span>
          <strong>{preflight.checks.length} checks</strong>
          <code>{preflight.manifest_digest.slice(0, 16)}...</code>
        </div>
      </div>
      <div className="release-check-grid">
        {preflight.checks.map((check) => (
          <article className="release-check" key={check.code}>
            <div>
              <span className={`state-badge ${check.state}`}>{check.state}</span>
              <code>{check.code}</code>
            </div>
            <strong>{check.summary}</strong>
            <p>{check.evidence}</p>
            {check.remediation && <small>{check.remediation}</small>}
          </article>
        ))}
      </div>
      <div className="safety-notice">
        <ShieldCheck size={16} />
        <span>
          Read-only evidence only. No installation, mutation, deployment, or execution is
          authorized.
        </span>
      </div>
    </section>
  );
}

