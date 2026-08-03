import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Bell,
  Building2,
  Blocks,
  Box,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  Database,
  FileChartColumn,
  FileText,
  FlaskConical,
  GitBranch,
  HardDrive,
  Layers3,
  Menu,
  MessageSquareText,
  Monitor,
  Network,
  PanelRightClose,
  Search,
  Send,
  Server,
  Settings,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { useState } from "react";

import { getStorageImpact, type GraphEntity } from "./api/graph";
import { getCurrentIdentity } from "./api/identity";
import { getPlatformStatus } from "./api/platform";
import { getStorageOverview, type StorageAsset } from "./api/storage";

const navigation = [
  { label: "Workspace", icon: MessageSquareText },
  { label: "Infrastructure", icon: Server },
  { label: "Topology", icon: GitBranch },
  { label: "Health", icon: Activity, active: true },
  { label: "Connectors", icon: Blocks },
  { label: "Reports", icon: FileChartColumn },
];

function statusLabel(status: string | undefined): string {
  if (!status) return "Connecting";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function shouldOpenInspector(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(min-width: 821px)").matches
  );
}

function initials(displayName: string | undefined): string {
  if (!displayName) return "--";
  return displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
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

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(shouldOpenInspector);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const statusQuery = useQuery({
    queryKey: ["platform-status"],
    queryFn: getPlatformStatus,
    refetchInterval: 30_000,
    retry: 1,
  });
  const identityQuery = useQuery({
    queryKey: ["current-identity"],
    queryFn: getCurrentIdentity,
    retry: false,
  });
  const identity = identityQuery.data?.data;
  const storageQuery = useQuery({
    queryKey: ["storage-overview"],
    queryFn: getStorageOverview,
    enabled: Boolean(identity),
    retry: false,
  });
  const platform = statusQuery.data?.data;
  const overview = storageQuery.data?.data;
  const state = statusQuery.isError ? "unavailable" : platform?.status;
  const warningAsset = overview?.assets.find((asset) => asset.health !== "healthy");
  const selectedAsset =
    overview?.assets.find((asset) => asset.asset_id === selectedAssetId) ??
    warningAsset ??
    overview?.assets[0];
  const impactAssetId = selectedAsset?.asset_id;
  const impactQuery = useQuery({
    queryKey: ["storage-impact", impactAssetId],
    queryFn: () => getStorageImpact(impactAssetId ?? ""),
    enabled: Boolean(identity && impactAssetId),
    retry: false,
  });
  const impact = impactQuery.data?.data;
  const longestImpactPath = impact
    ? [...impact.paths].sort((left, right) => right.entity_ids.length - left.entity_ids.length)[0]
    : undefined;
  const selectedEvidence =
    overview?.evidence.filter((item) =>
      selectedAsset?.evidence_references.includes(item.reference),
    ) ?? [];
  const healthyCount =
    overview?.assets.filter((asset) => asset.health === "healthy").length ?? 0;

  return (
    <div className="app-frame">
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark" aria-hidden="true">
            A
          </div>
          <div>
            <strong>ATLAS</strong>
            <span>Operations</span>
          </div>
          <button
            className="icon-button sidebar-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <nav aria-label="Primary navigation">
          <p className="nav-heading">OPERATE</p>
          {navigation.map(({ label, icon: Icon, active }) => (
            <button
              className={`nav-item ${active ? "active" : ""}`}
              type="button"
              key={label}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </button>
          ))}
          <p className="nav-heading nav-heading-admin">ADMINISTER</p>
          <button className="nav-item" type="button">
            <ShieldCheck size={18} strokeWidth={1.8} />
            <span>Governance</span>
          </button>
          <button className="nav-item" type="button">
            <Settings size={18} strokeWidth={1.8} />
            <span>Settings</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${state ?? "loading"}`} />
            <div>
              <strong>{statusLabel(state)}</strong>
              <span>Platform status</span>
            </div>
          </div>
          <div className="user-row">
            <div className="avatar">{initials(identity?.display_name)}</div>
            <div>
              <strong>{identity?.display_name ?? "Not authenticated"}</strong>
              <span>
                {identity
                  ? `${identity.authentication.method} identity`
                  : "Sign-in required"}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {sidebarOpen && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="main-area">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
            type="button"
          >
            <Menu size={20} />
          </button>
          <button className="scope-select" type="button">
            <Box size={17} />
            <span>Enterprise estate</span>
            <ChevronDown size={15} />
          </button>
          <div className="topbar-actions">
            <button className="search-button" type="button">
              <Search size={17} />
              <span>Search infrastructure</span>
            </button>
            <button className="icon-button" type="button" aria-label="Notifications">
              <Bell size={19} />
            </button>
            <button className="icon-button" type="button" aria-label="Help">
              <CircleHelp size={19} />
            </button>
            <button
              className="icon-button"
              type="button"
              aria-label={inspectorOpen ? "Close context panel" : "Open context panel"}
              onClick={() => setInspectorOpen((open) => !open)}
            >
              <PanelRightClose size={19} />
            </button>
          </div>
        </header>

        <div className={`workspace-grid ${inspectorOpen ? "with-inspector" : ""}`}>
          <section className="conversation" aria-label="Storage health workspace">
            <div className="conversation-heading">
              <div>
                <p className="eyebrow">STORAGE HEALTH</p>
                <h1>Storage estate assessment</h1>
                <p>Evidence-linked inventory, findings, and provisional analysis.</p>
              </div>
              <span className="decision-badge">
                <ShieldCheck size={15} /> Human decision required
              </span>
            </div>

            <div className="operations-workspace">
              {!identityQuery.isLoading && !identity && (
                <div className="workspace-message error-state">
                  <ShieldCheck size={22} />
                  <div>
                    <h2>Authentication required</h2>
                    <p>Storage health data is hidden until an authorized identity is available.</p>
                  </div>
                </div>
              )}

              {(identityQuery.isLoading || storageQuery.isLoading) && (
                <div className="workspace-message">
                  <Clock3 size={22} />
                  <div>
                    <h2>Loading governed storage context</h2>
                    <p>Authorization and evidence scope are being evaluated.</p>
                  </div>
                </div>
              )}

              {storageQuery.isError && (
                <div className="workspace-message error-state">
                  <AlertTriangle size={22} />
                  <div>
                    <h2>Storage overview unavailable</h2>
                    <p>No infrastructure state is inferred when authorized evidence cannot be read.</p>
                  </div>
                </div>
              )}

              {overview && (
                <>
                  <section className="summary-strip" aria-label="Storage summary">
                    <div>
                      <span>Arrays</span>
                      <strong>{overview.assets.length}</strong>
                    </div>
                    <div>
                      <span>Healthy</span>
                      <strong className="healthy-text">{healthyCount}</strong>
                    </div>
                    <div>
                      <span>Open findings</span>
                      <strong className="warning-text">{overview.findings.length}</strong>
                    </div>
                    <div>
                      <span>Investigation</span>
                      <strong className="state-text">{overview.investigation.state}</strong>
                    </div>
                    <div>
                      <span>Evidence</span>
                      <strong>{overview.evidence.length}</strong>
                    </div>
                  </section>

                  <section className="workspace-section inventory-section">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">INVENTORY</p>
                        <h2>Storage systems</h2>
                      </div>
                      <span className="data-profile">
                        <FlaskConical size={14} /> Synthetic lab
                      </span>
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>System</th>
                            <th>Serial</th>
                            <th>Device ID</th>
                            <th>Health</th>
                            <th>Observed</th>
                          </tr>
                        </thead>
                        <tbody>
                          {overview.assets.map((asset) => (
                            <tr
                              key={asset.asset_id}
                              className={selectedAsset?.asset_id === asset.asset_id ? "selected" : ""}
                            >
                              <td>
                                <button
                                  className="asset-select"
                                  type="button"
                                  onClick={() => setSelectedAssetId(asset.asset_id)}
                                >
                                  <Database size={17} />
                                  <span>
                                    <strong>{asset.model}</strong>
                                    <small>{asset.vendor}</small>
                                  </span>
                                </button>
                              </td>
                              <td>{asset.serial_number}</td>
                              <td className="mono-cell">{asset.storage_device_id}</td>
                              <td>
                                <span className={`health-state ${asset.health}`}>
                                  {asset.health === "healthy" ? (
                                    <CheckCircle2 size={14} />
                                  ) : (
                                    <AlertTriangle size={14} />
                                  )}
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
                        <div>
                          <p className="eyebrow">ACTIVE FINDING</p>
                          <h2>Health observation</h2>
                        </div>
                        <span className="severity-badge warning">Warning</span>
                      </div>
                      {overview.findings.map((finding) => (
                        <div className="finding-body" key={finding.finding_id}>
                          <div className="finding-component">
                            <AlertTriangle size={19} />
                            <div>
                              <strong>{finding.component}</strong>
                              <span>{finding.status}</span>
                            </div>
                          </div>
                          <p>{finding.summary}</p>
                          <span className="evidence-count">
                            {finding.evidence_references.length} evidence reference
                          </span>
                        </div>
                      ))}
                    </section>

                    <section className="workspace-section investigation-section">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">INVESTIGATION</p>
                          <h2>{overview.investigation.title}</h2>
                        </div>
                        <span className="state-badge">{overview.investigation.state}</span>
                      </div>
                      <p className="investigation-summary">{overview.investigation.summary}</p>
                      {overview.investigation.hypotheses.map((hypothesis) => (
                        <div className="hypothesis" key={hypothesis.hypothesis_id}>
                          <span>Possible hypothesis</span>
                          <strong>{hypothesis.title}</strong>
                          <p>{hypothesis.rationale}</p>
                          <small>{hypothesis.confidence_basis}</small>
                        </div>
                      ))}
                      <div className="investigation-columns">
                        <div>
                          <h3>Unknowns</h3>
                          <ul>
                            {overview.investigation.unknowns.map((unknown) => (
                              <li key={unknown}>{unknown}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <h3>Next read-only checks</h3>
                          <ol>
                            {overview.investigation.next_checks.map((check) => (
                              <li key={check}>{check}</li>
                            ))}
                          </ol>
                        </div>
                      </div>
                    </section>
                  </div>

                  <section className="workspace-section impact-section">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">DEPENDENCY IMPACT</p>
                        <h2>Evidence-linked service path</h2>
                      </div>
                      {impact && (
                        <span className="impact-maturity">
                          <Network size={14} /> {impact.digital_twin_maturity}
                        </span>
                      )}
                    </div>

                    {impactQuery.isLoading && (
                      <div className="impact-message">
                        <Clock3 size={18} /> Evaluating authorized dependency paths
                      </div>
                    )}
                    {impactQuery.isError && (
                      <div className="impact-message impact-error">
                        <AlertTriangle size={18} /> Dependency impact is unavailable; no service
                        impact is inferred.
                      </div>
                    )}
                    {impact && longestImpactPath && (
                      <>
                        <div className="impact-summary" aria-label="Dependency impact summary">
                          <div>
                            <span>Direct dependencies</span>
                            <strong>{impact.direct_entity_ids.length}</strong>
                          </div>
                          <div>
                            <span>Possibly affected</span>
                            <strong>{impact.possible_entity_ids.length}</strong>
                          </div>
                          <div>
                            <span>Technical services</span>
                            <strong>{impact.technical_service_ids.length}</strong>
                          </div>
                          <div>
                            <span>Business services</span>
                            <strong>{impact.business_service_ids.length}</strong>
                          </div>
                        </div>

                        <div className="dependency-path" aria-label="Authorized dependency path">
                          {longestImpactPath.entity_ids.map((entityId, index) => {
                            const entity = impact.entities.find(
                              (candidate) => candidate.entity_id === entityId,
                            );
                            const relationship = impact.relationships.find(
                              (candidate) =>
                                candidate.relationship_id ===
                                longestImpactPath.relationship_ids[index],
                            );
                            if (!entity) return null;
                            return (
                              <div className="dependency-step" key={entity.entity_id}>
                                <div className={`dependency-node ${entity.entity_type}`}>
                                  {graphEntityIcon(entity.entity_type)}
                                  <span>
                                    <small>{entityTypeLabel(entity.entity_type)}</small>
                                    <strong>{entity.display_name}</strong>
                                  </span>
                                </div>
                                {relationship && (
                                  <div className="dependency-link">
                                    <span>{relationshipLabel(relationship.relationship_type)}</span>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>

                        <div className="impact-detail-grid">
                          <div>
                            <h3>Known gaps</h3>
                            <ul>
                              {impact.known_gaps.map((gap) => (
                                <li key={gap}>{gap}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h3>Impact boundary</h3>
                            <ul>
                              {impact.unknowns.map((unknown) => (
                                <li key={unknown}>{unknown}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                        <div className="impact-safety">
                          <ShieldCheck size={16} />
                          <span>{impact.safety_notice}</span>
                        </div>
                      </>
                    )}
                  </section>

                  <section className="workspace-section report-section">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">ASSESSMENT REPORT</p>
                        <h2>{overview.report.title}</h2>
                      </div>
                      <FileText size={19} />
                    </div>
                    <p className="report-summary">{overview.report.executive_summary}</p>
                    <div className="report-columns">
                      <div>
                        <h3>Confirmed facts</h3>
                        <ul>
                          {overview.report.confirmed_facts.map((fact) => (
                            <li key={fact}>{fact}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h3>Provisional findings</h3>
                        <ul>
                          {overview.report.provisional_findings.map((finding) => (
                            <li key={finding}>{finding}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h3>Unknowns</h3>
                        <ul>
                          {overview.report.unknowns.map((unknown) => (
                            <li key={unknown}>{unknown}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    <div className="safety-notice">
                      <ShieldCheck size={16} />
                      <span>{overview.report.safety_notice}</span>
                    </div>
                  </section>
                </>
              )}
            </div>

            <div className="composer-wrap">
              <div className="composer">
                <textarea
                  aria-label="Ask Atlas"
                  placeholder="Ask Atlas about this storage assessment..."
                  rows={2}
                  disabled
                />
                <div className="composer-footer">
                  <span>Conversational analysis is not enabled in this slice</span>
                  <button className="send-button" type="button" aria-label="Send message" disabled>
                    <Send size={17} />
                  </button>
                </div>
              </div>
            </div>
          </section>

          {inspectorOpen && (
            <aside className="inspector" aria-label="Current context">
              <div className="inspector-header">
                <div>
                  <p className="eyebrow">CURRENT CONTEXT</p>
                  <h2>{selectedAsset?.model ?? "Storage assessment"}</h2>
                </div>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="Close context panel"
                  onClick={() => setInspectorOpen(false)}
                >
                  <X size={18} />
                </button>
              </div>

              <section className="inspector-section">
                <h3>Runtime</h3>
                <dl className="status-list">
                  <div>
                    <dt>API</dt>
                    <dd>
                      <span className={`status-dot ${state ?? "loading"}`} />
                      {statusLabel(state)}
                    </dd>
                  </div>
                  <div>
                    <dt>Environment</dt>
                    <dd>{platform?.environment ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Version</dt>
                    <dd>{platform?.version ?? "--"}</dd>
                  </div>
                </dl>
                {statusQuery.isError && (
                  <p className="inline-alert">The API is not reachable.</p>
                )}
              </section>

              <section className="inspector-section">
                <h3>Data boundary</h3>
                <dl className="status-list context-list">
                  <div>
                    <dt>Profile</dt>
                    <dd className="synthetic-label">Synthetic lab</dd>
                  </div>
                  <div>
                    <dt>Scope</dt>
                    <dd>{overview?.site_id ?? "--"}</dd>
                  </div>
                  <div>
                    <dt>Target</dt>
                    <dd>{overview?.target_id ?? "--"}</dd>
                  </div>
                  <div>
                    <dt>Generated</dt>
                    <dd>{formatTimestamp(overview?.generated_at)}</dd>
                  </div>
                </dl>
              </section>

              <section className="inspector-section">
                <h3>Selected system</h3>
                {selectedAsset ? (
                  <dl className="status-list context-list">
                    <div>
                      <dt>Model</dt>
                      <dd>{selectedAsset.model}</dd>
                    </div>
                    <div>
                      <dt>Serial</dt>
                      <dd>{selectedAsset.serial_number}</dd>
                    </div>
                    <div>
                      <dt>Health</dt>
                      <dd className={`${selectedAsset.health}-text`}>
                        {healthLabel(selectedAsset.health)}
                      </dd>
                    </div>
                    <div>
                      <dt>Evidence</dt>
                      <dd>{selectedAsset.evidence_references.length} linked</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="context-empty">No authorized storage context is loaded.</p>
                )}
              </section>

              <section className="inspector-section">
                <h3>Graph context</h3>
                {impact ? (
                  <dl className="status-list context-list">
                    <div>
                      <dt>Snapshot</dt>
                      <dd>{impact.snapshot_id}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{impact.freshness}</dd>
                    </div>
                    <div>
                      <dt>Completeness</dt>
                      <dd>{impact.completeness}</dd>
                    </div>
                    <div>
                      <dt>Path evidence</dt>
                      <dd>{longestImpactPath?.evidence_references.length ?? 0} linked</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="context-empty">No authorized graph context is loaded.</p>
                )}
              </section>

              <section className="inspector-section evidence-section">
                <h3>Evidence</h3>
                {selectedEvidence.map((item) => (
                  <div className="evidence-record" key={item.reference}>
                    <div>
                      <span className={`freshness ${item.freshness}`}>{item.freshness}</span>
                      <strong>{item.source}</strong>
                    </div>
                    <p>{item.trust_basis}</p>
                    <small>{item.source_version}</small>
                  </div>
                ))}
              </section>
            </aside>
          )}
        </div>
      </main>
    </div>
  );
}
