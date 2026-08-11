import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useState } from "react";

import { getCurrentIdentity } from "./api/identity";
import {
  WorkspaceLoadBoundary,
  WorkspaceRouteLoading,
} from "./features/shell/WorkspaceLoadBoundary";
import {
  healthViewFromHash,
  healthViewHash,
  type HealthViewId,
  isKnownWorkspaceHash,
  type WorkspaceId,
  workspaceFromHash,
  workspaceHash,
} from "./features/shell/workspace";
import { WorkspaceLanding } from "./features/workspace/WorkspaceLanding";

const OperationalApplication = lazy(() =>
  import("./OperationalApplication").then((module) => ({
    default: module.OperationalApplication,
  })),
);

function workspaceFromLocation(): WorkspaceId {
  if (new URLSearchParams(window.location.search).has("approval_request_id")) return "Health";
  const workspace = workspaceFromHash(window.location.hash);
  if (window.location.hash && !isKnownWorkspaceHash(window.location.hash)) {
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}#/workspace`,
    );
    return "Workspace";
  }
  return workspace;
}

function healthViewFromLocation(): HealthViewId {
  if (window.location.hash.toLowerCase().startsWith("#/health/")) {
    return healthViewFromHash(window.location.hash);
  }
  if (new URLSearchParams(window.location.search).has("approval_request_id")) {
    return "investigate";
  }
  return healthViewFromHash(window.location.hash);
}

function operationalWorkspace(
  workspace: WorkspaceId,
): Exclude<WorkspaceId, "Workspace"> {
  return workspace === "Connectors" ? "Connectors" : "Health";
}

function IdentityVerificationFailure({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="workspace-route-state workspace-route-error" role="alert">
      <div>
        <h1>Identity could not be verified</h1>
        <p>The Workspace remains unavailable until identity verification succeeds.</p>
        <button className="secondary-button" type="button" onClick={onRetry}>
          Retry identity check
        </button>
      </div>
    </main>
  );
}

export function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>(workspaceFromLocation);
  const [activeHealthView, setActiveHealthView] = useState<HealthViewId>(healthViewFromLocation);
  const [lastOperationalWorkspace, setLastOperationalWorkspace] = useState<
    Exclude<WorkspaceId, "Workspace">
  >(() => operationalWorkspace(workspaceFromLocation()));
  const [operationalActivated, setOperationalActivated] = useState(
    () => workspaceFromLocation() !== "Workspace",
  );
  const identityQuery = useQuery({
    queryKey: ["current-identity"],
    queryFn: getCurrentIdentity,
    retry: false,
  });

  useEffect(() => {
    const syncWorkspace = () => {
      const workspace = workspaceFromLocation();
      setActiveHealthView(healthViewFromLocation());
      if (workspace !== "Workspace") {
        setLastOperationalWorkspace(workspace);
        setOperationalActivated(true);
      }
      setActiveWorkspace(workspace);
    };

    window.addEventListener("hashchange", syncWorkspace);
    window.addEventListener("popstate", syncWorkspace);
    return () => {
      window.removeEventListener("hashchange", syncWorkspace);
      window.removeEventListener("popstate", syncWorkspace);
    };
  }, []);

  const navigateToWorkspace = (workspace: WorkspaceId) => {
    if (workspace !== "Workspace") {
      setLastOperationalWorkspace(workspace);
      setOperationalActivated(true);
    }
    setActiveWorkspace(workspace);
    if (workspace === "Health") setActiveHealthView("overview");
    const nextHash = workspaceHash(workspace);
    if (window.location.hash !== nextHash) {
      window.history.pushState(
        null,
        "",
        `${window.location.pathname}${window.location.search}${nextHash}`,
      );
    }
  };

  const navigateToHealthView = (view: HealthViewId) => {
    setActiveWorkspace("Health");
    setLastOperationalWorkspace("Health");
    setOperationalActivated(true);
    setActiveHealthView(view);
    const nextHash = healthViewHash(view);
    if (window.location.hash !== nextHash) {
      window.history.pushState(
        null,
        "",
        `${window.location.pathname}${window.location.search}${nextHash}`,
      );
    }
  };

  if (
    activeWorkspace === "Workspace" &&
    identityQuery.isLoading &&
    !operationalActivated
  ) {
    return <WorkspaceRouteLoading workspace="Workspace" />;
  }

  if (
    activeWorkspace === "Workspace" &&
    identityQuery.isError &&
    !operationalActivated
  ) {
    return (
      <IdentityVerificationFailure onRetry={() => void identityQuery.refetch()} />
    );
  }

  const identity = identityQuery.data?.data;
  const showWorkspace = activeWorkspace === "Workspace" && Boolean(identity);
  const mountOperational =
    operationalActivated ||
    activeWorkspace !== "Workspace" ||
    identityQuery.data === null;
  return (
    <>
      {showWorkspace && identity && (
        <WorkspaceLanding identity={identity} onNavigate={navigateToWorkspace} />
      )}
      {activeWorkspace === "Workspace" && identityQuery.isLoading && (
        <WorkspaceRouteLoading workspace="Workspace" />
      )}
      {activeWorkspace === "Workspace" && identityQuery.isError && (
        <IdentityVerificationFailure onRetry={() => void identityQuery.refetch()} />
      )}
      {mountOperational && (
        <div
          className="workspace-route-cache"
          hidden={activeWorkspace === "Workspace" && identityQuery.data !== null}
        >
          <WorkspaceLoadBoundary
            resetKey={lastOperationalWorkspace}
            workspace={lastOperationalWorkspace}
          >
            <Suspense
              fallback={<WorkspaceRouteLoading workspace={lastOperationalWorkspace} />}
            >
              <OperationalApplication
                activeHealthView={activeHealthView}
                activeWorkspace={lastOperationalWorkspace}
                onNavigateHealthView={navigateToHealthView}
                onNavigate={navigateToWorkspace}
              />
            </Suspense>
          </WorkspaceLoadBoundary>
        </div>
      )}
    </>
  );
}
