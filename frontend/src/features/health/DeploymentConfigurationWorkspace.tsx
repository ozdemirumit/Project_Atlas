import { Settings, ShieldCheck } from "lucide-react";

import type { DeploymentConfigurationPreview } from "../../api/deploymentConfiguration";

export interface DeploymentConfigurationWorkspaceProps {
  preview: DeploymentConfigurationPreview;
}

export default function DeploymentConfigurationWorkspace({
  preview,
}: DeploymentConfigurationWorkspaceProps) {
  return (
    <section className="workspace-section deployment-configuration-section">
      <div className="section-heading deployment-configuration-heading">
        <div>
          <p className="eyebrow">CONFIGURATION CONTRACT</p>
          <h2>Versioned deployment preview</h2>
          <p>Deterministic, redacted settings resolved before any host mutation.</p>
        </div>
        <span className={`state-badge ${preview.state}`}>
          <Settings size={14} /> {preview.state}
        </span>
      </div>
      <div className="configuration-identity-strip">
        <div>
          <span>Profile</span>
          <strong>{preview.profile.replace("_", " ")}</strong>
        </div>
        <div>
          <span>Environment</span>
          <strong>{preview.environment_id}</strong>
        </div>
        <div>
          <span>Schema</span>
          <code>{preview.schema_version}</code>
        </div>
        <div>
          <span>Digest</span>
          <code>{preview.configuration_digest.slice(0, 20)}...</code>
        </div>
      </div>
      <div className="configuration-preview-grid">
        <div className="configuration-field-list">
          <h3>Effective fields</h3>
          {preview.fields.map((field) => (
            <div className="configuration-field" key={field.path}>
              <div>
                <code>{field.path}</code>
                <span>{field.source.replace("_", " ")}</span>
              </div>
              <strong>{field.display_value}</strong>
            </div>
          ))}
        </div>
        <div className="configuration-validation-list">
          <h3>Validation gates</h3>
          {preview.validations.map((validation) => (
            <div className="configuration-validation" key={validation.code}>
              <span className={`state-badge ${validation.state}`}>{validation.state}</span>
              <div>
                <code>{validation.code}</code>
                <strong>{validation.summary}</strong>
                {validation.remediation && <small>{validation.remediation}</small>}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="safety-notice">
        <ShieldCheck size={16} />
        <span>
          Preview only. No file write, secret provisioning, port change, installation, or service
          execution is authorized.
        </span>
      </div>
    </section>
  );
}
