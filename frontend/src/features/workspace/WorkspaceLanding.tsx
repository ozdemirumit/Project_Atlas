import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { CurrentIdentity } from "../../api/identity";
import { getPlatformStatus, PlatformPostureViolationError } from "../../api/platform";
import { logoutBrowserSession } from "../../api/sessions";
import {
  AdvisoryBoundaryViolation,
  ApplicationSidebar,
  ApplicationTopbar,
} from "../shell/ApplicationShell";
import type {
  WorkspaceCapabilityDestination,
  WorkspaceId,
  WorkspaceViewId,
} from "../shell/workspace";
import OperationsConversationWorkspace from "./OperationsConversationWorkspace";
import WorkflowPlanningWorkspace from "./WorkflowPlanningWorkspace";
import { WorkspaceOverview } from "./WorkspaceOverview";
import { useState } from "react";

interface WorkspaceLandingProps {
  activeView: WorkspaceViewId;
  identity: CurrentIdentity;
  onNavigate: (workspace: WorkspaceId) => void;
  onNavigateCapability: (destination: WorkspaceCapabilityDestination) => void;
  onNavigateView: (view: WorkspaceViewId) => void;
}

export function WorkspaceLanding({
  activeView,
  identity,
  onNavigate,
  onNavigateCapability,
  onNavigateView,
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

  function navigateConversationContext(input: {
    destination: "inventory" | "topology";
    targetId: string;
    conversationId: string | null;
  }) {
    const url = new URL(window.location.href);
    if (input.targetId) url.searchParams.set("target_id", input.targetId);
    else url.searchParams.delete("target_id");
    if (input.conversationId) url.searchParams.set("conversation_id", input.conversationId);
    else url.searchParams.delete("conversation_id");
    window.history.replaceState(window.history.state, "", url);
    onNavigateCapability(
      input.destination === "inventory"
        ? { workspace: "Connectors", view: "inventory" }
        : { workspace: "Health", view: "overview" },
    );
  }

  if (statusQuery.error instanceof PlatformPostureViolationError) {
    return <AdvisoryBoundaryViolation />;
  }

  return (
    <div className="app-frame">
      <ApplicationSidebar
        activeWorkspace="Workspace"
        authenticationMethod={identity.authentication.method}
        credentialKind={identity.credential_kind}
        displayName={identity.display_name}
        onClose={() => setSidebarOpen(false)}
        onNavigate={(workspace) => {
          setSidebarOpen(false);
          onNavigate(workspace);
        }}
        open={sidebarOpen}
        platformState={platformState}
        platformMode={statusQuery.data?.data.operational_posture.platform_mode}
      />

      <main className="main-area">
        <ApplicationTopbar
          inspectorOpen={false}
          logoutPending={logoutMutation.isPending}
          onLogout={() => logoutMutation.mutate()}
          onOpenNavigation={() => setSidebarOpen(true)}
          onToggleInspector={() => undefined}
          showInspector={false}
          showLogout={identity.credential_kind === "browser_session"}
        />

        <div className="workspace-grid">
          <section
            className={`conversation ${activeView === "workflows" ? "workflow-planning-route" : ""}`}
            aria-label="Workspace workspace"
          >
            {logoutMutation.isError && (
              <div className="workspace-message error-state" role="alert">
                Sign-out was not completed. Your current session remains authoritative.
              </div>
            )}
            {activeView === "home" ? (
              <>
                <OperationsConversationWorkspace
                  organizationId={identity.organization_id}
                  environmentId={identity.scope.environment_id}
                  siteId={identity.scope.site_id}
                  ownerSubjectId={identity.subject_id}
                  governedSessionAvailable
                  onRequestEnterpriseLogin={() => {
                    queryClient.removeQueries({ queryKey: ["operational-conversation"] });
                    queryClient.removeQueries({ queryKey: ["operational-conversations"] });
                    void queryClient.invalidateQueries({ queryKey: ["current-identity"] });
                  }}
                  onNavigateContext={navigateConversationContext}
                />
                <div className="workspace-capability-directory">
                  <div className="workspace-capability-directory-heading">
                    <p className="eyebrow">OPERATION DIRECTORY</p>
                    <h2>Platform capabilities</h2>
                  </div>
                  <WorkspaceOverview onNavigate={onNavigateCapability} />
                </div>
              </>
            ) : (
              <WorkflowPlanningWorkspace
                environmentId={identity.scope.environment_id}
                onBack={() => onNavigateView("home")}
                organizationId={identity.organization_id}
                ownerSubjectId={identity.subject_id}
                siteId={identity.scope.site_id}
              />
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
