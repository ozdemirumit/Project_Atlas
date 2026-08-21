import {
  Activity,
  Blocks,
  Box,
  LogOut,
  Menu,
  MessageSquareText,
  PanelRightClose,
  ShieldCheck,
  ShieldX,
  X,
} from "lucide-react";

import type { WorkspaceId } from "./workspace";

const navigation: Array<{
  id: WorkspaceId;
  icon: typeof MessageSquareText;
}> = [
  { id: "Workspace", icon: MessageSquareText },
  { id: "Health", icon: Activity },
  { id: "Connectors", icon: Blocks },
];

function initials(displayName: string | undefined): string {
  if (!displayName) return "--";
  return displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

function statusLabel(status: string | undefined): string {
  if (!status) return "Connecting";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function AdvisoryBoundaryViolation() {
  return (
    <main className="advisory-boundary-violation" role="alert">
      <ShieldX size={28} aria-hidden="true" />
      <div>
        <p className="eyebrow">PLATFORM SAFETY</p>
        <h1>Advisory boundary unavailable</h1>
        <p>The operational workspace is blocked because its safety posture could not be verified.</p>
      </div>
    </main>
  );
}

interface ApplicationSidebarProps {
  activeWorkspace: WorkspaceId;
  authenticationMethod?: string;
  credentialKind?: "identity_provider" | "browser_session" | "api_token";
  displayName?: string;
  onClose: () => void;
  onNavigate: (workspace: WorkspaceId) => void;
  open: boolean;
  platformState?: string;
  platformMode?: "advisory_only";
}

export function ApplicationSidebar({
  activeWorkspace,
  authenticationMethod,
  credentialKind,
  displayName,
  onClose,
  onNavigate,
  open,
  platformState,
  platformMode,
}: ApplicationSidebarProps) {
  const identityLabel =
    credentialKind === "browser_session"
      ? "Signed in"
      : credentialKind === "api_token"
        ? "API token"
        : authenticationMethod
          ? `${authenticationMethod} identity`
          : "Sign-in required";

  return (
    <>
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
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
            onClick={onClose}
            aria-label="Close navigation"
            title="Close navigation"
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <nav aria-label="Primary navigation">
          <p className="nav-heading">OPERATE</p>
          {navigation.map(({ id, icon: Icon }) => (
            <button
              aria-current={activeWorkspace === id ? "page" : undefined}
              className={`nav-item ${activeWorkspace === id ? "active" : ""}`}
              type="button"
              key={id}
              onClick={() => onNavigate(id)}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{id}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${platformState ?? "loading"}`} />
            <div>
              <strong>{statusLabel(platformState)}</strong>
              <span>Platform status</span>
            </div>
          </div>
          {platformMode === "advisory_only" && (
            <div className="sidebar-posture" aria-label="Operational execution boundary">
              <ShieldCheck size={16} aria-hidden="true" />
              <div>
                <strong>Advisory only</strong>
                <span>Execution boundary</span>
              </div>
            </div>
          )}
          <div className="user-row">
            <div className="avatar">{initials(displayName)}</div>
            <div>
              <strong>{displayName ?? "Not authenticated"}</strong>
              <span>{identityLabel}</span>
            </div>
          </div>
        </div>
      </aside>

      {open && (
        <button className="scrim" aria-label="Close navigation" onClick={onClose} type="button" />
      )}
    </>
  );
}

interface ApplicationTopbarProps {
  inspectorOpen: boolean;
  logoutPending: boolean;
  onLogout: () => void;
  onOpenNavigation: () => void;
  onToggleInspector: () => void;
  showInspector: boolean;
  showLogout: boolean;
}

export function ApplicationTopbar({
  inspectorOpen,
  logoutPending,
  onLogout,
  onOpenNavigation,
  onToggleInspector,
  showInspector,
  showLogout,
}: ApplicationTopbarProps) {
  return (
    <header className="topbar">
      <button
        className="icon-button mobile-menu"
        onClick={onOpenNavigation}
        aria-label="Open navigation"
        title="Open navigation"
        type="button"
      >
        <Menu size={20} />
      </button>
      <div className="scope-select scope-select-static" aria-label="Current scope">
        <Box size={17} />
        <span>Enterprise estate</span>
      </div>
      <div className="topbar-actions">
        {showLogout && (
          <button
            className="icon-button"
            type="button"
            aria-label="Sign out"
            title="Sign out"
            disabled={logoutPending}
            onClick={onLogout}
          >
            <LogOut size={19} />
          </button>
        )}
        {showInspector && (
          <button
            className="icon-button"
            type="button"
            aria-label={inspectorOpen ? "Close context panel" : "Open context panel"}
            title={inspectorOpen ? "Close context panel" : "Open context panel"}
            onClick={onToggleInspector}
          >
            <PanelRightClose size={19} />
          </button>
        )}
      </div>
    </header>
  );
}
