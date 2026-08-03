import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bell,
  Blocks,
  Bot,
  Box,
  ChevronDown,
  CircleHelp,
  FileChartColumn,
  GitBranch,
  Menu,
  MessageSquareText,
  PanelRightClose,
  Search,
  Send,
  Server,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState } from "react";

import { getCurrentIdentity } from "./api/identity";
import { getPlatformStatus } from "./api/platform";

const navigation = [
  { label: "Workspace", icon: MessageSquareText, active: true },
  { label: "Infrastructure", icon: Server },
  { label: "Topology", icon: GitBranch },
  { label: "Health", icon: Activity },
  { label: "Connectors", icon: Blocks },
  { label: "Reports", icon: FileChartColumn },
];

function statusLabel(status: string | undefined): string {
  if (!status) return "Connecting";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function shouldOpenInspector(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(min-width: 821px)").matches;
}

function initials(displayName: string | undefined): string {
  if (!displayName) return "--";
  return displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(shouldOpenInspector);
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
  const platform = statusQuery.data?.data;
  const identity = identityQuery.data?.data;
  const state = statusQuery.isError ? "unavailable" : platform?.status;

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
            <button className={`nav-item ${active ? "active" : ""}`} type="button" key={label}>
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

      {sidebarOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation" type="button">
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
          <section className="conversation" aria-label="AI operations workspace">
            <div className="conversation-heading">
              <div>
                <p className="eyebrow">AI OPERATIONS WORKSPACE</p>
                <h1>Infrastructure investigation</h1>
                <p>Analyze evidence, understand impact, and prepare governed recommendations.</p>
              </div>
              <span className="decision-badge">
                <ShieldCheck size={15} /> Human decision required
              </span>
            </div>

            <div className="empty-workspace">
              <div className="assistant-symbol">
                <Bot size={26} strokeWidth={1.7} />
              </div>
              <h2>What should we investigate?</h2>
              <p>Ask about infrastructure health, topology, capacity, incidents, or operational risk.</p>
              <div className="prompt-grid">
                <button type="button">Summarize platform health</button>
                <button type="button">Review active infrastructure risks</button>
                <button type="button">Prepare a capacity assessment</button>
              </div>
            </div>

            <div className="composer-wrap">
              <div className="composer">
                <textarea aria-label="Ask Atlas" placeholder="Ask Atlas about your infrastructure..." rows={2} />
                <div className="composer-footer">
                  <span>Evidence-backed analysis only</span>
                  <button className="send-button" type="button" aria-label="Send message" disabled>
                    <Send size={17} />
                  </button>
                </div>
              </div>
              <p className="composer-note">Atlas provides decision support and does not execute infrastructure changes autonomously.</p>
            </div>
          </section>

          {inspectorOpen && (
            <aside className="inspector" aria-label="Current context">
              <div className="inspector-header">
                <div>
                  <p className="eyebrow">CURRENT CONTEXT</p>
                  <h2>Platform foundation</h2>
                </div>
                <button className="icon-button" type="button" aria-label="Close context panel" onClick={() => setInspectorOpen(false)}>
                  <X size={18} />
                </button>
              </div>

              <section className="inspector-section">
                <h3>Runtime</h3>
                <dl className="status-list">
                  <div>
                    <dt>API</dt>
                    <dd><span className={`status-dot ${state ?? "loading"}`} />{statusLabel(state)}</dd>
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
                {statusQuery.isError && <p className="inline-alert">The API is not reachable. Start the backend to restore platform status.</p>}
              </section>

              <section className="inspector-section">
                <h3>Connected capabilities</h3>
                <div className="capability-empty">
                  <Blocks size={20} />
                  <p>No infrastructure connectors are configured.</p>
                </div>
              </section>

              <section className="inspector-section evidence-section">
                <h3>Evidence policy</h3>
                <p>Recommendations must include source evidence, confidence, impact, risk, and rollback guidance.</p>
              </section>
            </aside>
          )}
        </div>
      </main>
    </div>
  );
}
