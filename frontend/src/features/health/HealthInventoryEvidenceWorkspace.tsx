import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  FlaskConical,
  HardDrive,
  Layers3,
  Monitor,
  Network,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import type { GraphEntity, StorageImpact } from "../../api/graph";
import type { EvidenceRecord, StorageAsset, StorageOverview } from "../../api/storage";

export interface HealthInventoryEvidenceWorkspaceProps {
  impact?: StorageImpact;
  impactError: boolean;
  impactLoading: boolean;
  onSelectAsset: (assetId: string) => void;
  overview: StorageOverview;
  selectedAsset?: StorageAsset;
  selectedEvidence: EvidenceRecord[];
}

function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function healthLabel(health: StorageAsset["health"]): string {
  return health.charAt(0).toUpperCase() + health.slice(1);
}

function entityTypeLabel(entityType: GraphEntity["entity_type"]): string {
  return entityType.replaceAll("_", " ");
}

function relationshipLabel(relationshipType: string | undefined): string {
  return (
    {
      backed_by: "backs",
      uses: "supports",
      runs_on: "hosts",
      depends_on: "supports",
    }[relationshipType ?? ""] ?? "relates to"
  );
}

function graphEntityIcon(entityType: GraphEntity["entity_type"]) {
  const props = { size: 18, strokeWidth: 1.8 };
  if (entityType === "storage_system") return <HardDrive {...props} />;
  if (entityType === "volume") return <Layers3 {...props} />;
  if (entityType === "datastore") return <Database {...props} />;
  if (entityType === "virtual_machine") return <Monitor {...props} />;
  if (entityType === "technical_service") return <Workflow {...props} />;
  return <Building2 {...props} />;
}

export default function HealthInventoryEvidenceWorkspace({
  impact,
  impactError,
  impactLoading,
  onSelectAsset,
  overview,
  selectedAsset,
  selectedEvidence,
}: HealthInventoryEvidenceWorkspaceProps) {
  const healthyCount = overview.assets.filter((asset) => asset.health === "healthy").length;
  const longestImpactPath = impact
    ? [...impact.paths].sort((left, right) => right.entity_ids.length - left.entity_ids.length)[0]
    : undefined;

  return (
    <div className="health-core-workspace" aria-label="Health inventory and evidence">
      <section className="summary-strip" aria-label="Storage summary">
        <div><span>Arrays</span><strong>{overview.assets.length}</strong></div>
        <div><span>Healthy</span><strong className="healthy-text">{healthyCount}</strong></div>
        <div>
          <span>Open findings</span>
          <strong className="warning-text">{overview.findings.length}</strong>
        </div>
        <div>
          <span>Investigation</span>
          <strong className="state-text">{overview.investigation.state}</strong>
        </div>
        <div><span>Evidence</span><strong>{overview.evidence.length}</strong></div>
      </section>

      <section className="workspace-section inventory-section">
        <div className="section-heading">
          <div><p className="eyebrow">INVENTORY</p><h2>Storage systems</h2></div>
          <span className="data-profile">
            <FlaskConical size={14} /> {overview.data_profile.replaceAll("_", " ")}
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>System</th><th>Serial</th><th>Device ID</th><th>Health</th><th>Observed</th></tr></thead>
            <tbody>
              {overview.assets.map((asset) => (
                <tr key={asset.asset_id} className={selectedAsset?.asset_id === asset.asset_id ? "selected" : ""}>
                  <td>
                    <button className="asset-select" type="button" onClick={() => onSelectAsset(asset.asset_id)}>
                      <Database size={17} />
                      <span><strong>{asset.model}</strong><small>{asset.vendor}</small></span>
                    </button>
                  </td>
                  <td>{asset.serial_number}</td>
                  <td className="mono-cell">{asset.storage_device_id}</td>
                  <td>
                    <span className={`health-state ${asset.health}`}>
                      {asset.health === "healthy" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                      {healthLabel(asset.health)}
                    </span>
                  </td>
                  <td>{formatTimestamp(asset.observed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="analysis-grid">
        <section className="workspace-section finding-section">
          <div className="section-heading">
            <div><p className="eyebrow">ACTIVE FINDINGS</p><h2>Health observations</h2></div>
            <span className="severity-badge warning">Evidence bounded</span>
          </div>
          {overview.findings.length === 0 ? (
            <p className="context-empty">No authorized open findings are present in this snapshot.</p>
          ) : overview.findings.map((finding) => (
            <div className="finding-body" key={finding.finding_id}>
              <div className="finding-component">
                <AlertTriangle size={19} />
                <div><strong>{finding.component}</strong><span>{finding.status}</span></div>
              </div>
              <p>{finding.summary}</p>
              <span className="evidence-count">{finding.evidence_references.length} evidence references</span>
            </div>
          ))}
        </section>

        <section className="workspace-section investigation-section">
          <div className="section-heading">
            <div><p className="eyebrow">INVESTIGATION</p><h2>{overview.investigation.title}</h2></div>
            <span className="state-badge">{overview.investigation.state}</span>
          </div>
          <p className="investigation-summary">{overview.investigation.summary}</p>
          {overview.investigation.hypotheses.map((hypothesis) => (
            <div className="hypothesis" key={hypothesis.hypothesis_id}>
              <span>Possible hypothesis</span><strong>{hypothesis.title}</strong>
              <p>{hypothesis.rationale}</p><small>{hypothesis.confidence_basis}</small>
            </div>
          ))}
          <div className="investigation-columns">
            <div><h3>Unknowns</h3><ul>{overview.investigation.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><h3>Next read-only checks</h3><ol>{overview.investigation.next_checks.map((item) => <li key={item}>{item}</li>)}</ol></div>
          </div>
        </section>
      </div>

      <section className="workspace-section health-evidence-section">
        <div className="section-heading">
          <div><p className="eyebrow">SELECTED SYSTEM EVIDENCE</p><h2>{selectedAsset?.model ?? "No storage system selected"}</h2></div>
          <span className="data-profile"><ShieldCheck size={14} /> Authorized records only</span>
        </div>
        {selectedEvidence.length === 0 ? (
          <p className="context-empty">No linked evidence is available for the selected authorized system.</p>
        ) : (
          <div className="health-evidence-list">
            {selectedEvidence.map((item) => (
              <article className="evidence-record" key={item.reference}>
                <div><span className={`freshness ${item.freshness}`}>{item.freshness}</span><strong>{item.source}</strong></div>
                <p>{item.trust_basis}</p>
                <small>{item.source_version} | {formatTimestamp(item.observed_at)}</small>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="workspace-section impact-section">
        <div className="section-heading">
          <div><p className="eyebrow">DEPENDENCY IMPACT</p><h2>Evidence-linked service path</h2></div>
          {impact && <span className="impact-maturity"><Network size={14} /> {impact.digital_twin_maturity}</span>}
        </div>
        {impactLoading && <div className="impact-message"><Clock3 size={18} /> Evaluating authorized dependency paths</div>}
        {impactError && (
          <div className="impact-message impact-error" role="alert">
            <AlertTriangle size={18} /> Dependency impact is unavailable; no service impact is inferred.
          </div>
        )}
        {!impactLoading && !impactError && !impact && <p className="context-empty">No authorized dependency context is available.</p>}
        {impact && longestImpactPath && (
          <>
            <div className="impact-summary" aria-label="Dependency impact summary">
              <div><span>Direct dependencies</span><strong>{impact.direct_entity_ids.length}</strong></div>
              <div><span>Possibly affected</span><strong>{impact.possible_entity_ids.length}</strong></div>
              <div><span>Technical services</span><strong>{impact.technical_service_ids.length}</strong></div>
              <div><span>Business services</span><strong>{impact.business_service_ids.length}</strong></div>
            </div>
            <div className="dependency-path" aria-label="Authorized dependency path">
              {longestImpactPath.entity_ids.map((entityId, index) => {
                const entity = impact.entities.find((candidate) => candidate.entity_id === entityId);
                const relationship = impact.relationships.find((candidate) => candidate.relationship_id === longestImpactPath.relationship_ids[index]);
                if (!entity) return null;
                return (
                  <div className="dependency-step" key={entity.entity_id}>
                    <div className={`dependency-node ${entity.entity_type}`}>
                      {graphEntityIcon(entity.entity_type)}
                      <span><small>{entityTypeLabel(entity.entity_type)}</small><strong>{entity.display_name}</strong></span>
                    </div>
                    {relationship && <div className="dependency-link"><span>{relationshipLabel(relationship.relationship_type)}</span></div>}
                  </div>
                );
              })}
            </div>
            <div className="impact-detail-grid">
              <div><h3>Known gaps</h3><ul>{impact.known_gaps.map((item) => <li key={item}>{item}</li>)}</ul></div>
              <div><h3>Impact boundary</h3><ul>{impact.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></div>
            </div>
            <div className="impact-safety"><ShieldCheck size={16} /><span>{impact.safety_notice}</span></div>
          </>
        )}
      </section>

      <section className="workspace-section report-section">
        <div className="section-heading">
          <div><p className="eyebrow">ASSESSMENT REPORT</p><h2>{overview.report.title}</h2></div>
          <FileText size={19} />
        </div>
        <p className="report-summary">{overview.report.executive_summary}</p>
        <div className="report-columns">
          <div><h3>Confirmed facts</h3><ul>{overview.report.confirmed_facts.map((item) => <li key={item}>{item}</li>)}</ul></div>
          <div><h3>Provisional findings</h3><ul>{overview.report.provisional_findings.map((item) => <li key={item}>{item}</li>)}</ul></div>
          <div><h3>Unknowns</h3><ul>{overview.report.unknowns.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </div>
        <div className="safety-notice"><ShieldCheck size={16} /><span>{overview.report.safety_notice}</span></div>
      </section>
    </div>
  );
}
