import { Component, type ReactNode } from "react";
import { AlertTriangle, LoaderCircle, RefreshCw } from "lucide-react";

import type { WorkspaceId } from "./workspace";

export function WorkspaceRouteLoading({ workspace }: { workspace: WorkspaceId }) {
  return (
    <main className="workspace-route-state" aria-live="polite" aria-busy="true">
      <LoaderCircle className="workspace-route-spinner" size={24} aria-hidden="true" />
      <div>
        <h1>Loading {workspace}</h1>
        <p>Preparing the requested workspace.</p>
      </div>
    </main>
  );
}

interface WorkspaceLoadBoundaryProps {
  children: ReactNode;
  onReload?: () => void;
  resetKey: string;
  workspace: WorkspaceId;
}

interface WorkspaceLoadBoundaryState {
  failed: boolean;
}

export class WorkspaceLoadBoundary extends Component<
  WorkspaceLoadBoundaryProps,
  WorkspaceLoadBoundaryState
> {
  state: WorkspaceLoadBoundaryState = { failed: false };

  static getDerivedStateFromError(): WorkspaceLoadBoundaryState {
    return { failed: true };
  }

  componentDidCatch(): void {
    // The visible fail-closed state is authoritative; no chunk details are exposed.
  }

  componentDidUpdate(previous: WorkspaceLoadBoundaryProps): void {
    if (previous.resetKey !== this.props.resetKey && this.state.failed) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <main className="workspace-route-state workspace-route-error" role="alert">
        <AlertTriangle size={24} aria-hidden="true" />
        <div>
          <h1>{this.props.workspace} could not be loaded</h1>
          <p>No operational state or authority was inferred.</p>
          <button
            className="secondary-button"
            type="button"
            onClick={this.props.onReload ?? (() => window.location.reload())}
          >
            <RefreshCw size={16} /> Reload application
          </button>
        </div>
      </main>
    );
  }
}
