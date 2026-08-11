import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { CurrentIdentity } from "../../api/identity";
import { getPlatformStatus } from "../../api/platform";
import { logoutBrowserSession } from "../../api/sessions";
import {
  ApplicationSidebar,
  ApplicationTopbar,
} from "../shell/ApplicationShell";
import type { WorkspaceCapabilityDestination, WorkspaceId } from "../shell/workspace";
import { WorkspaceOverview } from "./WorkspaceOverview";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";

interface WorkspaceLandingProps {
  identity: CurrentIdentity;
  onNavigate: (workspace: WorkspaceId) => void;
  onNavigateCapability: (destination: WorkspaceCapabilityDestination) => void;
}

export function WorkspaceLanding({
  identity,
  onNavigate,
  onNavigateCapability,
}: WorkspaceLandingProps) {
  const queryClient = useQueryClient();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const statusQuery = useQuery({
    queryKey: ["platform-status"],
    queryFn: getPlatformStatus,
    refetchInterval: 30_000,
    retry: 1,
  });
  const logoutMutation = useMutation({
    mutationFn: logoutBrowserSession,
    onSuccess: async () => {
      queryClient.removeQueries({
        predicate: (query) => {
          const rootKey = query.queryKey[0];
          return rootKey !== "current-identity" && rootKey !== "platform-status";
        },
      });
      await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
    },
  });
  const platformState = statusQuery.isError
    ? "unavailable"
    : statusQuery.data?.data.status;

  return (
    <div className="app-frame">
      <ApplicationSidebar
        activeWorkspace="Workspace"
        authenticationMethod={identity.authentication.method}
        displayName={identity.display_name}
        onClose={() => setSidebarOpen(false)}
        onNavigate={(workspace) => {
          setSidebarOpen(false);
          onNavigate(workspace);
        }}
        open={sidebarOpen}
        platformState={platformState}
      />

      <main className="main-area">
        <ApplicationTopbar
          inspectorOpen={false}
          logoutPending={logoutMutation.isPending}
          onLogout={() => logoutMutation.mutate()}
          onOpenNavigation={() => setSidebarOpen(true)}
          onToggleInspector={() => undefined}
          showInspector={false}
          showLogout={identity.authentication.method !== "development"}
        />

        <div className="workspace-grid">
          <section className="conversation" aria-label="Workspace workspace">
            <div className="conversation-heading">
              <div>
                <p className="eyebrow">OPERATIONS WORKSPACE</p>
                <h1>Enterprise operations</h1>
                <p>Available operational capabilities by control domain.</p>
              </div>
              <span className="decision-badge">
                <ShieldCheck size={15} /> Human-controlled operations
              </span>
            </div>

            {logoutMutation.isError && (
              <div className="workspace-message error-state" role="alert">
                Sign-out was not completed. Your current session remains authoritative.
              </div>
            )}
            <WorkspaceOverview onNavigate={onNavigateCapability} />
          </section>
        </div>
      </main>
    </div>
  );
}
