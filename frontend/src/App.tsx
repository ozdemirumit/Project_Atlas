import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Bell,
  BrainCircuit,
  Building2,
  Blocks,
  Box,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  Copy,
  Database,
  Download,
  FileChartColumn,
  FileText,
  FlaskConical,
  GitBranch,
  HardDrive,
  Layers3,
  KeyRound,
  LogIn,
  LogOut,
  Menu,
  MessageSquareText,
  Monitor,
  PackageCheck,
  Network,
  PanelRightClose,
  Play,
  RefreshCw,
  Search,
  Send,
  Server,
  Settings,
  ShieldCheck,
  LockKeyhole,
  Trash2,
  Scale,
  Workflow,
  UserCheck,
  UserX,
  X,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import {
  createApiCredential,
  getApiCredentials,
  revokeApiCredential,
} from "./api/apiCredentials";
import { getAuditExportOverview, retryAuditExport } from "./api/auditExport";
import {
  acquireBootstrapArtifacts,
  type BootstrapArtifactAcquisitionResult,
} from "./api/bootstrapArtifactAcquisition";
import {
  initializeBootstrapData,
  previewBootstrapDataPlan,
  type BootstrapDataInitializationResult,
} from "./api/bootstrapData";
import {
  renderBootstrapConfiguration,
  type BootstrapConfigurationRenderingResult,
} from "./api/bootstrapConfigurationRendering";
import { claimBootstrapLease, type BootstrapClaimResult } from "./api/bootstrapClaim";
import { getBootstrapPlan } from "./api/bootstrapPlan";
import { previewBootstrapInvalidation } from "./api/bootstrapInvalidation";
import { rebaseBootstrapPlan, type BootstrapRebaseResult } from "./api/bootstrapRebase";
import { getBootstrapState } from "./api/bootstrapState";
import {
  previewBootstrapTrustPlan,
  provisionBootstrapTrust,
  type BootstrapTrustProvisioningResult,
} from "./api/bootstrapTrust";
import { previewDeploymentConfiguration } from "./api/deploymentConfiguration";
import { getStorageImpact, type GraphEntity } from "./api/graph";
import {
  createApprovalRequest,
  decideApprovalRequest,
  getApprovalRequest,
} from "./api/approvals";
import { getHealthCheckOverview, runHealthCheck } from "./api/healthChecks";
import { getCurrentIdentity } from "./api/identity";
import {
  disableGovernedIdentity,
  getIdentityGovernance,
  revokeGovernedApiCredential,
  revokeGovernedSession,
} from "./api/identityGovernance";
import { createStorageInvestigation } from "./api/investigations";
import { getPlatformStatus } from "./api/platform";
import { createStorageRca } from "./api/rca";
import { createStorageRecommendation } from "./api/recommendations";
import {
  getReleasePreflight,
  type ReleasePreflightMode,
  type ReleasePreflightProfile,
} from "./api/releasePreflight";
import { createStorageTechnicalReport } from "./api/reports";
import {
  createBrowserSession,
  getBrowserSessions,
  logoutBrowserSession,
  revokeBrowserSession,
} from "./api/sessions";
import {
  getSecurityExportOverview,
  sendSecurityExportTestEvent,
} from "./api/securityExport";
import { getStorageOverview, type StorageAsset } from "./api/storage";
import {
  createWorkloadIdentity,
  getWorkloadIdentities,
  revokeWorkloadCredential,
  rotateWorkloadCredential,
} from "./api/workloadIdentities";

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

function apiGrantLabel(permissionId: string): string {
  return (
    {
      "identity.self.read": "Identity profile",
      "storage.overview.read": "Storage overview",
      "graph.storage-impact.read": "Dependency impact",
      "health-check.overview.read": "Health check overview",
      "approval.request.read": "Approval packet",
    }[permissionId] ?? permissionId
  );
}

function governanceIdempotencyKey(
  resource: "identity" | "session" | "token" | "workload-create" | "workload-rotate" | "workload-revoke",
  version: number,
): string {
  const nonce =
    typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}`;
  return `governance-${resource}-${version}-${nonce}`;
}

type PendingWorkloadAction =
  | { kind: "create" }
  | { kind: "rotate"; identityId: string; version: number }
  | { kind: "revoke"; credentialId: string; version: number };

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

function downloadMarkdown(filename: string, content: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function App() {
  const queryClient = useQueryClient();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(shouldOpenInspector);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedHealthCheckId, setSelectedHealthCheckId] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [approvalRequestId, setApprovalRequestId] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).get("approval_request_id"),
  );
  const [approvalRationale, setApprovalRationale] = useState("");
  const [apiCredentialName, setApiCredentialName] = useState("");
  const [apiCredentialPurpose, setApiCredentialPurpose] = useState("");
  const [apiCredentialLifetime, setApiCredentialLifetime] = useState(30);
  const [selectedApiGrants, setSelectedApiGrants] = useState<string[]>([]);
  const [issuedApiToken, setIssuedApiToken] = useState<string | null>(null);
  const [governanceSearch, setGovernanceSearch] = useState("");
  const [governanceReason, setGovernanceReason] = useState("");
  const [workloadSearch, setWorkloadSearch] = useState("");
  const [workloadReason, setWorkloadReason] = useState("");
  const [workloadIdentityId, setWorkloadIdentityId] = useState(
    "workload.atlas.health.scheduler",
  );
  const [workloadDisplayName, setWorkloadDisplayName] = useState("Health scheduler");
  const [workloadServiceId, setWorkloadServiceId] = useState("service.health-scheduler");
  const [workloadInstanceId, setWorkloadInstanceId] = useState(
    "instance.health-scheduler.local-01",
  );
  const [workloadOwnerId, setWorkloadOwnerId] = useState(
    "subject.enterprise.platform-owner",
  );
  const [workloadPurpose, setWorkloadPurpose] = useState(
    "Run bounded Atlas health-check coordination.",
  );
  const [workloadAudience, setWorkloadAudience] = useState("service.health-check");
  const [workloadSecretReference, setWorkloadSecretReference] = useState(
    "secret.connector.health-readonly",
  );
  const [issuedWorkloadToken, setIssuedWorkloadToken] = useState<string | null>(null);
  const [pendingWorkloadAction, setPendingWorkloadAction] =
    useState<PendingWorkloadAction | null>(null);
  const [auditSearch, setAuditSearch] = useState("");
  const [auditOutcome, setAuditOutcome] = useState("");
  const [releaseMode, setReleaseMode] = useState<ReleasePreflightMode>("offline");
  const [releaseProfile, setReleaseProfile] =
    useState<ReleasePreflightProfile>("linux_lab");
  const [bootstrapRebaseJustification, setBootstrapRebaseJustification] = useState("");
  const [bootstrapRebasePending, setBootstrapRebasePending] = useState(false);
  const [bootstrapRebaseResult, setBootstrapRebaseResult] =
    useState<BootstrapRebaseResult | null>(null);
  const [artifactAcquisitionJustification, setArtifactAcquisitionJustification] = useState("");
  const [artifactAcquisitionPending, setArtifactAcquisitionPending] = useState(false);
  const [artifactWarningAccepted, setArtifactWarningAccepted] = useState(false);
  const [artifactAcquisitionResult, setArtifactAcquisitionResult] =
    useState<BootstrapArtifactAcquisitionResult | null>(null);
  const [configurationRenderingJustification, setConfigurationRenderingJustification] =
    useState("");
  const [configurationRenderingPending, setConfigurationRenderingPending] = useState(false);
  const [configurationRenderingResult, setConfigurationRenderingResult] =
    useState<BootstrapConfigurationRenderingResult | null>(null);
  const [trustProvisioningJustification, setTrustProvisioningJustification] = useState("");
  const [trustProvisioningPending, setTrustProvisioningPending] = useState(false);
  const [trustProvisioningResult, setTrustProvisioningResult] =
    useState<BootstrapTrustProvisioningResult | null>(null);
  const [dataInitializationJustification, setDataInitializationJustification] = useState("");
  const [dataInitializationPending, setDataInitializationPending] = useState(false);
  const [dataInitializationResult, setDataInitializationResult] =
    useState<BootstrapDataInitializationResult | null>(null);
  const [bootstrapClaimJustification, setBootstrapClaimJustification] = useState("");
  const [bootstrapClaimPending, setBootstrapClaimPending] = useState(false);
  const [bootstrapClaimResult, setBootstrapClaimResult] =
    useState<BootstrapClaimResult | null>(null);
  const [pendingDisableSubjectId, setPendingDisableSubjectId] = useState<string | null>(null);
  const [investigationQuestion, setInvestigationQuestion] = useState(
    "What evidence explains the current storage warning?",
  );
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
  const loginMutation = useMutation({
    mutationFn: () => createBrowserSession(username, password),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
    },
    onSettled: () => setPassword(""),
  });
  const logoutMutation = useMutation({
    mutationFn: logoutBrowserSession,
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ["storage-overview"] });
      queryClient.removeQueries({ queryKey: ["storage-impact"] });
      queryClient.removeQueries({ queryKey: ["health-check-overview"] });
      queryClient.removeQueries({ queryKey: ["security-export-overview"] });
      queryClient.removeQueries({ queryKey: ["approval-request"] });
      queryClient.removeQueries({ queryKey: ["api-credentials"] });
      queryClient.removeQueries({ queryKey: ["identity-governance"] });
      queryClient.removeQueries({ queryKey: ["workload-identities"] });
      queryClient.removeQueries({ queryKey: ["audit-export-overview"] });
      setApprovalRequestId(null);
      setApprovalRationale("");
      setIssuedApiToken(null);
      setPendingDisableSubjectId(null);
      setGovernanceReason("");
      setWorkloadReason("");
      setIssuedWorkloadToken(null);
      setPendingWorkloadAction(null);
      setBootstrapRebaseJustification("");
      setBootstrapRebasePending(false);
      setBootstrapRebaseResult(null);
      setArtifactAcquisitionJustification("");
      setArtifactAcquisitionPending(false);
      setArtifactWarningAccepted(false);
      setArtifactAcquisitionResult(null);
      setConfigurationRenderingJustification("");
      setConfigurationRenderingPending(false);
      setConfigurationRenderingResult(null);
      setTrustProvisioningJustification("");
      setTrustProvisioningPending(false);
      setTrustProvisioningResult(null);
      setBootstrapClaimJustification("");
      setBootstrapClaimPending(false);
      setBootstrapClaimResult(null);
      await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
    },
  });
  const sessionsQuery = useQuery({
    queryKey: ["browser-sessions"],
    queryFn: getBrowserSessions,
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const sessionInventory = sessionsQuery.data?.data;
  const sessions = sessionInventory?.sessions;
  const revokeSessionMutation = useMutation({
    mutationFn: revokeBrowserSession,
    onSuccess: async (_, sessionId) => {
      const revokedCurrent = sessions?.some(
        (session) => session.session_id === sessionId && session.current,
      );
      if (revokedCurrent) {
        queryClient.removeQueries({ queryKey: ["browser-sessions"] });
        await queryClient.invalidateQueries({ queryKey: ["current-identity"] });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["browser-sessions"] });
      }
    },
  });
  const apiCredentialsQuery = useQuery({
    queryKey: ["api-credentials"],
    queryFn: getApiCredentials,
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const apiCredentialInventory = apiCredentialsQuery.data?.data;
  const apiCredentials = apiCredentialInventory?.credentials;
  const availableApiGrants = apiCredentialInventory?.available_grants ?? [];
  const createApiCredentialMutation = useMutation({
    mutationFn: () =>
      createApiCredential({
        displayName: apiCredentialName,
        purpose: apiCredentialPurpose,
        expiresInMinutes: apiCredentialLifetime,
        permissionIds: selectedApiGrants,
      }),
    onSuccess: async (result) => {
      setIssuedApiToken(result.data.token);
      setApiCredentialName("");
      setApiCredentialPurpose("");
      await queryClient.invalidateQueries({ queryKey: ["api-credentials"] });
    },
  });
  const revokeApiCredentialMutation = useMutation({
    mutationFn: revokeApiCredential,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["api-credentials"] });
    },
  });
  const identityGovernanceQuery = useQuery({
    queryKey: ["identity-governance", governanceSearch],
    queryFn: () => getIdentityGovernance(governanceSearch),
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const identityGovernance = identityGovernanceQuery.data?.data;
  const revokeGovernedSessionMutation = useMutation({
    mutationFn: revokeGovernedSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["identity-governance"] });
    },
  });
  const disableGovernedIdentityMutation = useMutation({
    mutationFn: disableGovernedIdentity,
    onSuccess: async () => {
      setPendingDisableSubjectId(null);
      setGovernanceReason("");
      await queryClient.invalidateQueries({ queryKey: ["identity-governance"] });
    },
  });
  const revokeGovernedApiCredentialMutation = useMutation({
    mutationFn: revokeGovernedApiCredential,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["identity-governance"] });
    },
  });
  const workloadIdentityQuery = useQuery({
    queryKey: ["workload-identities", workloadSearch],
    queryFn: () => getWorkloadIdentities(workloadSearch),
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const workloadInventory = workloadIdentityQuery.data?.data;
  const createWorkloadIdentityMutation = useMutation({
    mutationFn: createWorkloadIdentity,
    onSuccess: async (result) => {
      setIssuedWorkloadToken(result.data.token);
      setPendingWorkloadAction(null);
      await queryClient.invalidateQueries({ queryKey: ["workload-identities"] });
    },
  });
  const rotateWorkloadCredentialMutation = useMutation({
    mutationFn: rotateWorkloadCredential,
    onSuccess: async (result) => {
      setIssuedWorkloadToken(result.data.token);
      setPendingWorkloadAction(null);
      await queryClient.invalidateQueries({ queryKey: ["workload-identities"] });
    },
  });
  const revokeWorkloadCredentialMutation = useMutation({
    mutationFn: revokeWorkloadCredential,
    onSuccess: async () => {
      setPendingWorkloadAction(null);
      await queryClient.invalidateQueries({ queryKey: ["workload-identities"] });
    },
  });
  const auditExportQuery = useQuery({
    queryKey: ["audit-export-overview", auditSearch, auditOutcome],
    queryFn: () => getAuditExportOverview(auditSearch, auditOutcome),
    enabled: Boolean(identity && identity.authentication.method !== "development"),
    retry: false,
  });
  const auditExport = auditExportQuery.data?.data;
  const auditHealth = auditExport?.health?.[0];
  const releasePreflightQuery = useQuery({
    queryKey: ["release-preflight", releaseMode, releaseProfile],
    queryFn: () => getReleasePreflight(releaseMode, releaseProfile),
    enabled: Boolean(identity),
    retry: false,
  });
  const releasePreflight = releasePreflightQuery.data?.data;
  const deploymentConfigurationQuery = useQuery({
    queryKey: ["deployment-configuration-preview", releaseProfile, identity?.scope],
    queryFn: () => previewDeploymentConfiguration(releaseProfile, identity!.scope),
    enabled: Boolean(identity),
    retry: false,
  });
  const deploymentConfiguration = deploymentConfigurationQuery.data?.data;
  const bootstrapTrustPlanQuery = useQuery({
    queryKey: [
      "bootstrap-trust-plan",
      deploymentConfiguration?.configuration_digest,
      identity?.scope,
    ],
    queryFn: () => previewBootstrapTrustPlan(deploymentConfiguration!, identity!.scope),
    enabled: Boolean(identity && deploymentConfiguration),
    retry: false,
  });
  const bootstrapTrustPlan = bootstrapTrustPlanQuery.data?.data;
  const bootstrapDataPlanQuery = useQuery({
    queryKey: [
      "bootstrap-data-plan",
      deploymentConfiguration?.configuration_digest,
      bootstrapTrustPlan?.trust_plan_digest,
      identity?.scope,
    ],
    queryFn: () =>
      previewBootstrapDataPlan(
        deploymentConfiguration!,
        bootstrapTrustPlan!,
        identity!.scope,
      ),
    enabled: Boolean(identity && deploymentConfiguration && bootstrapTrustPlan),
    retry: false,
  });
  const bootstrapDataPlan = bootstrapDataPlanQuery.data?.data;
  const bootstrapPlanQuery = useQuery({
    queryKey: [
      "bootstrap-plan",
      releasePreflight?.report_id,
      deploymentConfiguration?.preview_id,
    ],
    queryFn: () => getBootstrapPlan(releasePreflight!, deploymentConfiguration!, identity!.scope),
    enabled: Boolean(identity && releasePreflight && deploymentConfiguration),
    retry: false,
  });
  const bootstrapPlan = bootstrapPlanQuery.data?.data;
  const bootstrapStateQuery = useQuery({
    queryKey: ["bootstrap-state"],
    queryFn: getBootstrapState,
    enabled: Boolean(identity),
    retry: false,
  });
  const bootstrapState = bootstrapStateQuery.data?.data;
  const bootstrapInvalidationQuery = useQuery({
    queryKey: [
      "bootstrap-invalidation",
      bootstrapPlan?.plan_digest,
      deploymentConfiguration?.configuration_digest,
    ],
    queryFn: () =>
      previewBootstrapInvalidation(bootstrapPlan!, deploymentConfiguration!, identity!.scope),
    enabled: Boolean(identity && bootstrapPlan && deploymentConfiguration),
    retry: false,
  });
  const bootstrapInvalidation = bootstrapInvalidationQuery.data?.data;
  const bootstrapRebaseMutation = useMutation({
    mutationFn: () =>
      rebaseBootstrapPlan({
        state: bootstrapState!,
        preview: bootstrapInvalidation!,
        plan: bootstrapPlan!,
        configuration: deploymentConfiguration!,
        scope: identity!.scope,
        justification: bootstrapRebaseJustification.trim(),
      }),
    onSuccess: async (response) => {
      setBootstrapRebaseResult(response.data);
      setBootstrapRebasePending(false);
      setBootstrapRebaseJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      ]);
    },
  });
  const artifactAcquisitionMutation = useMutation({
    mutationFn: () =>
      acquireBootstrapArtifacts({
        state: bootstrapState!,
        preflight: releasePreflight!,
        scope: identity!.scope,
        justification: artifactAcquisitionJustification.trim(),
        warningAccepted: artifactWarningAccepted,
      }),
    onSuccess: async (response) => {
      setArtifactAcquisitionResult(response.data);
      setArtifactAcquisitionPending(false);
      setArtifactAcquisitionJustification("");
      setArtifactWarningAccepted(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      ]);
    },
  });
  const configurationRenderingMutation = useMutation({
    mutationFn: () =>
      renderBootstrapConfiguration({
        state: bootstrapState!,
        configuration: deploymentConfiguration!,
        scope: identity!.scope,
        justification: configurationRenderingJustification.trim(),
      }),
    onSuccess: async (response) => {
      setConfigurationRenderingResult(response.data);
      setConfigurationRenderingPending(false);
      setConfigurationRenderingJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      ]);
    },
  });
  const trustProvisioningMutation = useMutation({
    mutationFn: () =>
      provisionBootstrapTrust({
        state: bootstrapState!,
        configuration: deploymentConfiguration!,
        trustPlan: bootstrapTrustPlan!,
        scope: identity!.scope,
        justification: trustProvisioningJustification.trim(),
      }),
    onSuccess: async (response) => {
      setTrustProvisioningResult(response.data);
      setTrustProvisioningPending(false);
      setTrustProvisioningJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      ]);
    },
  });
  const dataInitializationMutation = useMutation({
    mutationFn: () =>
      initializeBootstrapData({
        state: bootstrapState!,
        configuration: deploymentConfiguration!,
        trustPlan: bootstrapTrustPlan!,
        dataPlan: bootstrapDataPlan!,
        scope: identity!.scope,
        justification: dataInitializationJustification.trim(),
      }),
    onSuccess: async (response) => {
      setDataInitializationResult(response.data);
      setDataInitializationPending(false);
      setDataInitializationJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-data-plan"] }),
      ]);
    },
  });
  const bootstrapClaimMutation = useMutation({
    mutationFn: () =>
      claimBootstrapLease({
        state: bootstrapState!,
        plan: bootstrapPlan!,
        configuration: deploymentConfiguration!,
        scope: identity!.scope,
        justification: bootstrapClaimJustification.trim(),
      }),
    onSuccess: async (response) => {
      setBootstrapClaimResult(response.data);
      setBootstrapClaimPending(false);
      setBootstrapClaimJustification("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bootstrap-state"] }),
        queryClient.invalidateQueries({ queryKey: ["bootstrap-invalidation"] }),
      ]);
    },
  });
  const artifactExecution =
    artifactAcquisitionResult?.execution ?? bootstrapState?.run?.artifact_acquisition;
  const configurationExecution =
    configurationRenderingResult?.execution ?? bootstrapState?.run?.configuration_rendering;
  const trustExecution =
    trustProvisioningResult?.execution ?? bootstrapState?.run?.trust_provisioning;
  const dataExecution =
    dataInitializationResult?.execution ?? bootstrapState?.run?.data_initialization;
  const artifactPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.acquire" &&
      bootstrapState.run.artifact_acquisition?.state !== "running" &&
      bootstrapPlan?.state === "ready" &&
      bootstrapPlan.plan_digest === bootstrapState.run.plan_digest &&
      releasePreflight &&
      releasePreflight.release_id === bootstrapState.run.release_id &&
      releasePreflight.profile === bootstrapState.run.profile &&
      releasePreflight.state !== "failed" &&
      releasePreflight.state !== "unchecked",
  );
  const bootstrapLeaseAvailable = Boolean(
    bootstrapState?.lease_available &&
      bootstrapPlan?.state === "ready" &&
      deploymentConfiguration?.state === "passed" &&
      bootstrapState?.run?.state !== "completed",
  );
  const configurationPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.configure" &&
      bootstrapState.run.configuration_rendering?.state !== "running" &&
      bootstrapState.run.completed_phase_ids.includes("phase.acquire") &&
      bootstrapState.run.artifact_acquisition?.state === "completed" &&
      deploymentConfiguration?.state === "passed" &&
      deploymentConfiguration.release_id === bootstrapState.run.release_id &&
      deploymentConfiguration.profile === bootstrapState.run.profile &&
      deploymentConfiguration.configuration_digest ===
        bootstrapState.run.configuration_digest,
  );
  const trustPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.trust" &&
      bootstrapState.run.trust_provisioning?.state !== "running" &&
      bootstrapState.run.completed_phase_ids.includes("phase.configure") &&
      bootstrapState.run.configuration_rendering?.state === "completed" &&
      deploymentConfiguration?.state === "passed" &&
      deploymentConfiguration.release_id === bootstrapState.run.release_id &&
      deploymentConfiguration.profile === bootstrapState.run.profile &&
      deploymentConfiguration.configuration_digest === bootstrapState.run.configuration_digest &&
      bootstrapTrustPlan?.state === "passed" &&
      bootstrapTrustPlan.release_id === bootstrapState.run.release_id &&
      bootstrapTrustPlan.profile === bootstrapState.run.profile &&
      bootstrapTrustPlan.configuration_digest === bootstrapState.run.configuration_digest,
  );
  const dataPhaseAvailable = Boolean(
    bootstrapState?.run &&
      bootstrapState.lease_held_by_current_actor &&
      bootstrapState.run.current_phase_id === "phase.data" &&
      bootstrapState.run.data_initialization?.state !== "running" &&
      bootstrapState.run.completed_phase_ids.includes("phase.trust") &&
      bootstrapState.run.trust_provisioning?.state === "completed" &&
      deploymentConfiguration?.state === "passed" &&
      deploymentConfiguration.release_id === bootstrapState.run.release_id &&
      deploymentConfiguration.profile === bootstrapState.run.profile &&
      deploymentConfiguration.configuration_digest === bootstrapState.run.configuration_digest &&
      bootstrapTrustPlan?.state === "passed" &&
      bootstrapTrustPlan.release_id === bootstrapState.run.release_id &&
      bootstrapTrustPlan.profile === bootstrapState.run.profile &&
      bootstrapTrustPlan.configuration_digest === bootstrapState.run.configuration_digest &&
      bootstrapState.run.trust_provisioning?.trust_plan_digest ===
        bootstrapTrustPlan.trust_plan_digest &&
      bootstrapDataPlan?.state === "passed" &&
      bootstrapDataPlan.release_id === bootstrapState.run.release_id &&
      bootstrapDataPlan.profile === bootstrapState.run.profile &&
      bootstrapDataPlan.configuration_digest === bootstrapState.run.configuration_digest &&
      bootstrapDataPlan.trust_plan_digest === bootstrapTrustPlan.trust_plan_digest,
  );
  const retryAuditExportMutation = useMutation({
    mutationFn: retryAuditExport,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["audit-export-overview"] });
    },
  });
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
  const healthChecksQuery = useQuery({
    queryKey: ["health-check-overview"],
    queryFn: getHealthCheckOverview,
    enabled: Boolean(identity),
    retry: false,
  });
  const healthChecks = healthChecksQuery.data?.data;
  const securityExportQuery = useQuery({
    queryKey: ["security-export-overview"],
    queryFn: getSecurityExportOverview,
    enabled: Boolean(identity),
    retry: false,
  });
  const securityExport = securityExportQuery.data?.data;
  const securityDestination = securityExport?.destinations?.[0];
  const securityHealth = securityExport?.health?.[0];
  const securityExportTestMutation = useMutation({
    mutationFn: sendSecurityExportTestEvent,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["security-export-overview"] });
    },
  });
  const selectedHealthCheck =
    healthChecks?.definitions.find((item) => item.definition_id === selectedHealthCheckId) ??
    healthChecks?.definitions[0];
  const selectedHealthSchedule = healthChecks?.schedules.find(
    (item) => item.definition_id === selectedHealthCheck?.definition_id,
  );
  const selectedHealthRun = healthChecks?.latest_runs.find(
    (item) => item.definition_id === selectedHealthCheck?.definition_id,
  );
  const runHealthCheckMutation = useMutation({
    mutationFn: (definitionId: string) => runHealthCheck(definitionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["health-check-overview"] });
    },
  });
  const investigationMutation = useMutation({
    mutationFn: ({ targetId, question }: { targetId: string; question: string }) =>
      createStorageInvestigation(targetId, question),
  });
  const reasoningArtifact = investigationMutation.data?.data;
  const rcaMutation = useMutation({
    mutationFn: ({ targetId, actualBehavior }: { targetId: string; actualBehavior: string }) =>
      createStorageRca(targetId, actualBehavior),
  });
  const rcaCase = rcaMutation.data?.data;
  const recommendationMutation = useMutation({
    mutationFn: ({ targetId, caseId, version }: { targetId: string; caseId: string; version: number }) =>
      createStorageRecommendation(targetId, caseId, version),
  });
  const recommendation = recommendationMutation.data?.data;
  const approvalQuery = useQuery({
    queryKey: ["approval-request", approvalRequestId],
    queryFn: () => getApprovalRequest(approvalRequestId ?? ""),
    enabled: Boolean(identity && approvalRequestId),
    retry: false,
  });
  const approvalCreateMutation = useMutation({
    mutationFn: ({
      targetId,
      recommendationId,
      recommendationVersion,
      optionId,
    }: {
      targetId: string;
      recommendationId: string;
      recommendationVersion: number;
      optionId: string;
    }) => createApprovalRequest(targetId, recommendationId, recommendationVersion, optionId),
    onSuccess: (result) => {
      const requestId = result.data.request_id;
      setApprovalRequestId(requestId);
      const url = new URL(window.location.href);
      url.searchParams.set("approval_request_id", requestId);
      window.history.replaceState({}, "", url);
    },
  });
  const approvalDecisionMutation = useMutation({
    mutationFn: ({
      requestId,
      version,
      outcome,
      rationale,
    }: {
      requestId: string;
      version: number;
      outcome: "approve" | "reject" | "needs_evidence" | "defer";
      rationale: string;
    }) => decideApprovalRequest(requestId, version, outcome, rationale),
    onSuccess: (result) => {
      queryClient.setQueryData(["approval-request", result.data.request_id], result);
      setApprovalRationale("");
    },
  });
  const approval =
    approvalDecisionMutation.data?.data ??
    approvalCreateMutation.data?.data ??
    approvalQuery.data?.data;
  const canReviewApproval = Boolean(
    approval &&
      approval.state === "pending" &&
      identity?.subject_kind === "human" &&
      identity.subject_id !== approval.packet.requested_by &&
      identity.authentication.assurance_level !== "development",
  );
  const reportMutation = useMutation({
    mutationFn: ({
      targetId,
      recommendationId,
      recommendationVersion,
      incidentReference,
    }: {
      targetId: string;
      recommendationId: string;
      recommendationVersion: number;
      incidentReference: string;
    }) =>
      createStorageTechnicalReport(
        targetId,
        recommendationId,
        recommendationVersion,
        incidentReference,
      ),
  });
  const technicalReport = reportMutation.data?.data;
  const incidentReference = rcaCase?.incident_references.find(
    (reference) => reference.reference_type === "incident",
  )?.reference_id;
  const longestImpactPath = impact
    ? [...impact.paths].sort((left, right) => right.entity_ids.length - left.entity_ids.length)[0]
    : undefined;
  const selectedEvidence =
    overview?.evidence.filter((item) =>
      selectedAsset?.evidence_references.includes(item.reference),
    ) ?? [];
  const healthyCount =
    overview?.assets.filter((asset) => asset.health === "healthy").length ?? 0;

  if (!identityQuery.isLoading && identityQuery.data === null) {
    const submitLogin = (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (username && password && !loginMutation.isPending) loginMutation.mutate();
    };
    return (
      <main className="login-shell">
        <section className="login-panel" aria-labelledby="login-title">
          <div className="login-brand">
            <div className="brand-mark" aria-hidden="true">A</div>
            <div><strong>ATLAS</strong><span>Enterprise Operations</span></div>
          </div>
          <div className="login-heading">
            <LockKeyhole size={22} />
            <div><h1 id="login-title">Sign in</h1><p>Enterprise identity</p></div>
          </div>
          <form onSubmit={submitLogin}>
            <label htmlFor="atlas-username">Username</label>
            <input
              id="atlas-username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              maxLength={128}
              required
              autoFocus
            />
            <label htmlFor="atlas-password">Password</label>
            <input
              id="atlas-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              maxLength={1024}
              required
            />
            {loginMutation.isError && (
              <p className="login-error" role="alert">Sign-in was not accepted.</p>
            )}
            <button
              className="login-submit"
              type="submit"
              disabled={!username || !password || loginMutation.isPending}
            >
              <LogIn size={18} />
              {loginMutation.isPending ? "Signing in" : "Sign in"}
            </button>
          </form>
        </section>
      </main>
    );
  }

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
            {identity?.authentication.method !== "development" && (
              <button
                className="icon-button"
                type="button"
                aria-label="Sign out"
                title="Sign out"
                disabled={logoutMutation.isPending}
                onClick={() => logoutMutation.mutate()}
              >
                <LogOut size={19} />
              </button>
            )}
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

              {auditExport && auditHealth && (
                <section className="workspace-section audit-export-section">
                  <div className="section-heading audit-export-heading">
                    <div>
                      <p className="eyebrow">AUDIT GOVERNANCE</p>
                      <h2>Enterprise audit delivery</h2>
                      <p>Bounded, secret-free evidence from the authoritative Atlas audit stream.</p>
                    </div>
                    <span className={`security-export-state ${auditHealth.state}`}>
                      <ShieldCheck size={14} /> {auditHealth.state}
                    </span>
                  </div>

                  <div className="audit-export-toolbar">
                    <label>
                      <span>Search bounded events</span>
                      <div className="audit-search-input">
                        <Search size={15} />
                        <input
                          aria-label="Search audit events"
                          value={auditSearch}
                          maxLength={80}
                          placeholder="Event, result, subject, correlation"
                          onChange={(event) => setAuditSearch(event.target.value)}
                        />
                      </div>
                    </label>
                    <label>
                      <span>Outcome</span>
                      <select
                        aria-label="Filter audit outcome"
                        value={auditOutcome}
                        onChange={(event) => setAuditOutcome(event.target.value)}
                      >
                        <option value="">All outcomes</option>
                        <option value="allowed">Allowed</option>
                        <option value="denied">Denied</option>
                        <option value="succeeded">Succeeded</option>
                        <option value="failed">Failed</option>
                      </select>
                    </label>
                    <button
                      className="run-check-button audit-retry-button"
                      type="button"
                      disabled={
                        retryAuditExportMutation.isPending || auditHealth.queue_depth === 0
                      }
                      onClick={() => retryAuditExportMutation.mutate()}
                    >
                      <RefreshCw
                        className={retryAuditExportMutation.isPending ? "spin" : undefined}
                        size={16}
                      />
                      Retry queued delivery
                    </button>
                  </div>

                  <div className="audit-health-grid" aria-label="Audit delivery health">
                    <div>
                      <span>Bounded page</span>
                      <strong>{auditExport.page.events.length}</strong>
                      <small>Maximum {auditExport.page.limit} events</small>
                    </div>
                    <div>
                      <span>Queued</span>
                      <strong>{auditHealth.queue_depth}</strong>
                      <small>{auditHealth.retrying_count} retrying</small>
                    </div>
                    <div>
                      <span>Transport handoffs</span>
                      <strong>{auditHealth.delivered_count}</strong>
                      <small>SIEM receipt not inferred</small>
                    </div>
                    <div>
                      <span>Dead-letter</span>
                      <strong>{auditHealth.dead_letter_count}</strong>
                      <small>Visible for governed follow-up</small>
                    </div>
                  </div>

                  <div className="audit-export-grid">
                    <div className="audit-events-panel">
                      <div className="audit-panel-heading">
                        <h3>Authorized events</h3>
                        <span>{auditExport.page.has_more ? "More available" : "Bounded result"}</span>
                      </div>
                      {auditExport.page.events.length === 0 ? (
                        <p className="audit-empty">No matching audit events in this exact scope.</p>
                      ) : (
                        <div className="audit-event-list">
                          {auditExport.page.events.map((event) => (
                            <article className="audit-event" key={`${event.sequence}-${event.event_id}`}>
                              <div className="audit-event-title">
                                <strong>{event.event_type}</strong>
                                <span className={`audit-outcome ${event.outcome}`}>
                                  {event.outcome}
                                </span>
                              </div>
                              <p>{event.result_code}</p>
                              <dl>
                                <div>
                                  <dt>Actor</dt>
                                  <dd>{event.subject_id ?? "Unknown subject"}</dd>
                                </div>
                                <div>
                                  <dt>Occurred</dt>
                                  <dd>{formatTimestamp(event.occurred_at)}</dd>
                                </div>
                                <div>
                                  <dt>Correlation</dt>
                                  <dd>{event.correlation_id}</dd>
                                </div>
                                <div>
                                  <dt>Permission</dt>
                                  <dd>{event.permission_id ?? "Not applicable"}</dd>
                                </div>
                              </dl>
                              <code>{event.event_id}</code>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="audit-delivery-panel">
                      <div className="audit-panel-heading">
                        <h3>Recent delivery state</h3>
                        <span>At least once</span>
                      </div>
                      {auditExport.recent_deliveries.length === 0 ? (
                        <p className="audit-empty">No delivery attempts are visible yet.</p>
                      ) : (
                        <div className="audit-delivery-list">
                          {auditExport.recent_deliveries.slice(0, 8).map((delivery) => (
                            <article className="audit-delivery" key={delivery.delivery_id}>
                              <div>
                                <strong>{delivery.state.replaceAll("_", " ")}</strong>
                                <span>{delivery.attempts} attempt(s)</span>
                              </div>
                              <code>{delivery.event_id}</code>
                              <small>{formatTimestamp(delivery.updated_at)}</small>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {retryAuditExportMutation.data && (
                    <div className="security-export-result" role="status">
                      <CheckCircle2 size={16} />
                      Retry completed: {retryAuditExportMutation.data.data.delivered} transport
                      handoff(s), {retryAuditExportMutation.data.data.retrying} still retrying.
                    </div>
                  )}
                  {retryAuditExportMutation.isError && (
                    <div className="security-export-result error-state" role="alert">
                      <AlertTriangle size={16} /> Delivery remains queued or unavailable.
                    </div>
                  )}
                  <div className="safety-notice">
                    <ShieldCheck size={16} />
                    <span>{auditExport.safety_notice}</span>
                  </div>
                </section>
              )}

              {releasePreflight && (
                <section className="workspace-section release-preflight-section">
                  <div className="section-heading release-preflight-heading">
                    <div>
                      <p className="eyebrow">RELEASE READINESS</p>
                      <h2>Read-only deployment preflight</h2>
                      <p>Immutable artifact and host checks before any installation activity.</p>
                    </div>
                    <span className={`state-badge ${releasePreflight.state}`}>
                      <PackageCheck size={14} /> {releasePreflight.state}
                    </span>
                  </div>
                  <div className="release-preflight-controls">
                    <label>
                      <span>Acquisition mode</span>
                      <select
                        aria-label="Release acquisition mode"
                        value={releaseMode}
                        onChange={(event) =>
                          setReleaseMode(event.target.value as ReleasePreflightMode)
                        }
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
                        value={releaseProfile}
                        onChange={(event) =>
                          setReleaseProfile(event.target.value as ReleasePreflightProfile)
                        }
                      >
                        <option value="developer">Developer</option>
                        <option value="linux_lab">Linux lab</option>
                      </select>
                    </label>
                    <div className="release-identity">
                      <span>Release</span>
                      <strong>{releasePreflight.release_version}</strong>
                      <code>{releasePreflight.build_id}</code>
                    </div>
                    <div className="release-identity">
                      <span>Manifest</span>
                      <strong>{releasePreflight.checks.length} checks</strong>
                      <code>{releasePreflight.manifest_digest.slice(0, 16)}...</code>
                    </div>
                  </div>
                  <div className="release-check-grid">
                    {releasePreflight.checks.map((check) => (
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
                      Read-only evidence only. No installation, mutation, deployment, or execution
                      is authorized.
                    </span>
                  </div>
                </section>
              )}

              {deploymentConfiguration && (
                <section className="workspace-section deployment-configuration-section">
                  <div className="section-heading deployment-configuration-heading">
                    <div>
                      <p className="eyebrow">CONFIGURATION CONTRACT</p>
                      <h2>Versioned deployment preview</h2>
                      <p>Deterministic, redacted settings resolved before any host mutation.</p>
                    </div>
                    <span className={`state-badge ${deploymentConfiguration.state}`}>
                      <Settings size={14} /> {deploymentConfiguration.state}
                    </span>
                  </div>
                  <div className="configuration-identity-strip">
                    <div>
                      <span>Profile</span>
                      <strong>{deploymentConfiguration.profile.replace("_", " ")}</strong>
                    </div>
                    <div>
                      <span>Environment</span>
                      <strong>{deploymentConfiguration.environment_id}</strong>
                    </div>
                    <div>
                      <span>Schema</span>
                      <code>{deploymentConfiguration.schema_version}</code>
                    </div>
                    <div>
                      <span>Digest</span>
                      <code>{deploymentConfiguration.configuration_digest.slice(0, 20)}...</code>
                    </div>
                  </div>
                  <div className="configuration-preview-grid">
                    <div className="configuration-field-list">
                      <h3>Effective fields</h3>
                      {deploymentConfiguration.fields.map((field) => (
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
                      {deploymentConfiguration.validations.map((validation) => (
                        <div className="configuration-validation" key={validation.code}>
                          <span className={`state-badge ${validation.state}`}>
                            {validation.state}
                          </span>
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
                      Preview only. No file write, secret provisioning, port change, installation, or
                      service execution is authorized.
                    </span>
                  </div>
                </section>
              )}

              {bootstrapPlan && (
                <section className="workspace-section bootstrap-plan-section">
                  <div className="section-heading bootstrap-plan-heading">
                    <div>
                      <p className="eyebrow">BOOTSTRAP PLAN</p>
                      <h2>Ordered deployment phases</h2>
                      <p>Exact-input readiness and resume boundaries without execution.</p>
                    </div>
                    <span className={`state-badge ${bootstrapPlan.state}`}>
                      <Workflow size={14} /> {bootstrapPlan.state}
                    </span>
                  </div>
                  <div className="bootstrap-plan-identity">
                    <div><span>Plan digest</span><code>{bootstrapPlan.plan_digest.slice(0, 20)}...</code></div>
                    <div><span>Resume key</span><code>{bootstrapPlan.resume_key}</code></div>
                    <div><span>Phases</span><strong>{bootstrapPlan.phases.length}</strong></div>
                  </div>
                  <ol className="bootstrap-phase-list">
                    {bootstrapPlan.phases.map((phase) => (
                      <li key={phase.phase_id}>
                        <span className="bootstrap-phase-number">{phase.sequence}</span>
                        <div>
                          <div className="bootstrap-phase-title">
                            <strong>{phase.title}</strong>
                            <span className={`state-badge ${phase.state}`}>{phase.state}</span>
                          </div>
                          <code>{phase.phase_id}</code>
                          <p>{phase.dependencies.length ? `After ${phase.dependencies.join(", ")}` : "No phase dependency"}</p>
                          <small>{phase.stop_guidance}</small>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <div className="safety-notice">
                    <ShieldCheck size={16} />
                    <span>Planning evidence only. No phase, command, rollback, or infrastructure mutation is authorized.</span>
                  </div>
                </section>
              )}

              {bootstrapState && (
                <section className="workspace-section bootstrap-state-section">
                  <div className="section-heading bootstrap-state-heading">
                    <div>
                      <p className="eyebrow">BOOTSTRAP CHECKPOINTS</p>
                      <h2>Resume and lease state</h2>
                      <p>Coordination metadata only; loading this view never claims a lease.</p>
                    </div>
                    <span className={`state-badge ${bootstrapState.durable ? "ready" : "warning"}`}>
                      <LockKeyhole size={14} />
                      {bootstrapState.durable ? "durable" : "development memory"}
                    </span>
                  </div>
                  {bootstrapState.run ? (
                    <>
                      <div className="bootstrap-state-summary">
                        <div>
                          <span>Run</span>
                          <code>{bootstrapState.run.run_id}</code>
                        </div>
                        <div>
                          <span>Revision</span>
                          <strong>{bootstrapState.run.version}</strong>
                        </div>
                        <div>
                          <span>Completed</span>
                          <strong>
                            {bootstrapState.run.completed_phase_ids.length}/
                            {bootstrapState.run.phase_ids.length}
                          </strong>
                        </div>
                        <div>
                          <span>Lease</span>
                          <strong>
                            {bootstrapState.lease_available
                              ? "Available"
                              : bootstrapState.lease_held_by_current_actor
                                ? "Held by this session"
                                : "Held by another operator"}
                          </strong>
                        </div>
                      </div>
                      <div
                        className="bootstrap-checkpoint-grid"
                        aria-label="Bootstrap checkpoint progress"
                      >
                        {bootstrapState.run.phase_ids.map((phaseId, index) => {
                          const checkpoint = bootstrapState.run?.checkpoints.find(
                            (item) => item.phase_id === phaseId,
                          );
                          const phaseState =
                            checkpoint?.state ??
                            (bootstrapState.run?.current_phase_id === phaseId
                              ? "current"
                              : "pending");
                          return (
                            <div className={`bootstrap-checkpoint ${phaseState}`} key={phaseId}>
                              <span>{index + 1}</span>
                              <div>
                                <code>{phaseId}</code>
                                <strong>{phaseState}</strong>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <div className="bootstrap-state-detail">
                        <div>
                          <span>Plan digest</span>
                          <code>{bootstrapState.run.plan_digest.slice(0, 20)}...</code>
                        </div>
                        <div>
                          <span>Lease expiry</span>
                          <strong>
                            {formatTimestamp(bootstrapState.run.lease_expires_at ?? undefined)}
                          </strong>
                        </div>
                      </div>
                      {artifactPhaseAvailable && !artifactAcquisitionPending && (
                        <div className="artifact-acquisition-action">
                          <div>
                            <strong>Acquire and verify release artifacts</strong>
                            <p>
                              Writes only the immutable release set to the governed Atlas artifact
                              store. Configuration, services, and infrastructure remain unchanged.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setArtifactAcquisitionResult(null);
                              setArtifactAcquisitionPending(true);
                            }}
                          >
                            <PackageCheck size={14} /> Review acquisition
                          </button>
                        </div>
                      )}
                      {artifactAcquisitionPending &&
                        artifactPhaseAvailable &&
                        releasePreflight && (
                          <div className="artifact-acquisition-confirmation" role="dialog">
                            <div>
                              <strong>Confirm artifact storage change</strong>
                              <p>
                                Release {releasePreflight.release_version} will be staged and
                                checksum-verified in {releasePreflight.mode} mode. Existing verified
                                files are reused and conflicting files are preserved.
                              </p>
                            </div>
                            <label>
                              Change justification
                              <input
                                value={artifactAcquisitionJustification}
                                maxLength={500}
                                onChange={(event) =>
                                  setArtifactAcquisitionJustification(event.target.value)
                                }
                                placeholder="Record the approved reason for acquiring this release"
                              />
                            </label>
                            {releasePreflight.state === "warning" && (
                              <label className="artifact-warning-acceptance">
                                <input
                                  type="checkbox"
                                  checked={artifactWarningAccepted}
                                  onChange={(event) =>
                                    setArtifactWarningAccepted(event.target.checked)
                                  }
                                />
                                <span>I accept the reviewed preflight warning for this lab run.</span>
                              </label>
                            )}
                            {artifactAcquisitionMutation.isError && (
                              <div className="impact-message impact-error" role="alert">
                                <AlertTriangle size={16} /> Artifact acquisition was not started.
                                Refresh the governed state before retrying.
                              </div>
                            )}
                            <div className="artifact-acquisition-confirm-actions">
                              <button
                                type="button"
                                onClick={() => {
                                  setArtifactAcquisitionPending(false);
                                  setArtifactAcquisitionJustification("");
                                  setArtifactWarningAccepted(false);
                                }}
                              >
                                Cancel
                              </button>
                              <button
                                className="artifact-acquisition-confirm"
                                type="button"
                                disabled={
                                  artifactAcquisitionJustification.trim().length < 12 ||
                                  (releasePreflight.state === "warning" &&
                                    !artifactWarningAccepted) ||
                                  artifactAcquisitionMutation.isPending
                                }
                                onClick={() => artifactAcquisitionMutation.mutate()}
                              >
                                <PackageCheck size={14} /> Confirm acquisition
                              </button>
                            </div>
                          </div>
                        )}
                      {artifactExecution && (
                        <div className={`artifact-acquisition-result ${artifactExecution.state}`}>
                          <div className="artifact-acquisition-result-heading">
                            {artifactExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>
                                Artifact acquisition {artifactExecution.state}
                              </strong>
                              <code>{artifactExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${artifactExecution.state}`}>
                              {artifactExecution.state}
                            </span>
                          </div>
                          <div className="artifact-acquisition-summary">
                            <div>
                              <span>Mode</span>
                              <strong>{artifactExecution.mode}</strong>
                            </div>
                            <div>
                              <span>Artifacts</span>
                              <strong>{artifactExecution.artifact_count}</strong>
                            </div>
                            <div>
                              <span>Verified bytes</span>
                              <strong>{artifactExecution.total_bytes.toLocaleString()}</strong>
                            </div>
                            <div>
                              <span>Completed</span>
                              <strong>
                                {formatTimestamp(artifactExecution.completed_at ?? undefined)}
                              </strong>
                            </div>
                          </div>
                          {artifactExecution.evidence.length > 0 && (
                            <div className="artifact-evidence-list">
                              {artifactExecution.evidence.map((item) => (
                                <div key={item.artifact_id}>
                                  <div>
                                    <code>{item.artifact_id}</code>
                                    <span>{item.disposition}</span>
                                  </div>
                                  <code>{item.sha256.slice(0, 20)}...</code>
                                </div>
                              ))}
                            </div>
                          )}
                          {artifactExecution.state === "failed" && (
                            <p className="artifact-recovery-note">
                              Verified prior content was preserved. Correct the bounded failure and
                              retry this phase under the active lease.
                            </p>
                          )}
                        </div>
                      )}
                      {configurationPhaseAvailable && !configurationRenderingPending && (
                        <div className="configuration-rendering-action">
                          <div>
                            <strong>Render and validate effective configuration</strong>
                            <p>
                              Writes only canonical non-secret configuration to the governed Atlas
                              configuration store. Trust, secrets, data, services, and infrastructure
                              remain unchanged.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setConfigurationRenderingResult(null);
                              setConfigurationRenderingPending(true);
                            }}
                          >
                            <FileText size={14} /> Review configuration
                          </button>
                        </div>
                      )}
                      {configurationRenderingPending &&
                        configurationPhaseAvailable &&
                        deploymentConfiguration && (
                          <div className="configuration-rendering-confirmation" role="dialog">
                            <div>
                              <strong>Confirm effective configuration change</strong>
                              <p>
                                Configuration {deploymentConfiguration.configuration_digest.slice(0, 12)}
                                ... will be recomputed, schema-validated, and atomically published.
                                Existing exact output is reused and conflicting content is preserved.
                              </p>
                            </div>
                            <label>
                              Change justification
                              <input
                                value={configurationRenderingJustification}
                                maxLength={500}
                                onChange={(event) =>
                                  setConfigurationRenderingJustification(event.target.value)
                                }
                                placeholder="Record the approved reason for rendering this configuration"
                              />
                            </label>
                            {configurationRenderingMutation.isError && (
                              <div className="impact-message impact-error" role="alert">
                                <AlertTriangle size={16} /> Configuration was not published. Refresh
                                the governed state and preview before retrying.
                              </div>
                            )}
                            <div className="configuration-rendering-confirm-actions">
                              <button
                                type="button"
                                onClick={() => {
                                  setConfigurationRenderingPending(false);
                                  setConfigurationRenderingJustification("");
                                }}
                              >
                                Cancel
                              </button>
                              <button
                                className="configuration-rendering-confirm"
                                type="button"
                                disabled={
                                  configurationRenderingJustification.trim().length < 12 ||
                                  configurationRenderingMutation.isPending
                                }
                                onClick={() => configurationRenderingMutation.mutate()}
                              >
                                <FileText size={14} /> Confirm configuration
                              </button>
                            </div>
                          </div>
                        )}
                      {configurationExecution && (
                        <div className={`configuration-rendering-result ${configurationExecution.state}`}>
                          <div className="configuration-rendering-result-heading">
                            {configurationExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>Configuration rendering {configurationExecution.state}</strong>
                              <code>{configurationExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${configurationExecution.state}`}>
                              {configurationExecution.state}
                            </span>
                          </div>
                          <div className="configuration-rendering-summary">
                            <div>
                              <span>Schema</span>
                              <strong>v1</strong>
                            </div>
                            <div>
                              <span>Files</span>
                              <strong>{configurationExecution.file_count}</strong>
                            </div>
                            <div>
                              <span>Verified bytes</span>
                              <strong>{configurationExecution.total_bytes.toLocaleString()}</strong>
                            </div>
                            <div>
                              <span>Completed</span>
                              <strong>
                                {formatTimestamp(configurationExecution.completed_at ?? undefined)}
                              </strong>
                            </div>
                          </div>
                          {configurationExecution.evidence.length > 0 && (
                            <div className="configuration-evidence-list">
                              {configurationExecution.evidence.map((item) => (
                                <div key={item.file_id}>
                                  <div>
                                    <code>{item.file_id}</code>
                                    <span>{item.disposition}</span>
                                  </div>
                                  <code>{item.sha256.slice(0, 20)}...</code>
                                </div>
                              ))}
                            </div>
                          )}
                          {configurationExecution.state === "failed" && (
                            <p className="configuration-recovery-note">
                              Prior verified configuration was preserved. Correct the bounded failure
                              and retry under the active lease.
                            </p>
                          )}
                        </div>
                      )}
                      {trustPhaseAvailable && !trustProvisioningPending && (
                        <div className="trust-provisioning-action">
                          <div>
                            <strong>Provision public trust and workload identities</strong>
                            <p>
                              Publishes only approved public certificates and opaque secret-reference
                              metadata. Private keys, credential values, data, services, and
                              infrastructure remain unchanged.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setTrustProvisioningResult(null);
                              setTrustProvisioningPending(true);
                            }}
                          >
                            <ShieldCheck size={14} /> Review trust
                          </button>
                        </div>
                      )}
                      {trustProvisioningPending &&
                        trustPhaseAvailable &&
                        bootstrapTrustPlan && (
                          <div className="trust-provisioning-confirmation" role="dialog">
                            <div>
                              <strong>Confirm public trust-store change</strong>
                              <p>
                                Trust plan {bootstrapTrustPlan.trust_plan_digest.slice(0, 12)}... will
                                publish {bootstrapTrustPlan.anchors.length} public anchor and {" "}
                                {bootstrapTrustPlan.workload_identities.length} workload identity
                                record. Existing exact output is reused.
                              </p>
                            </div>
                            <label>
                              Trust justification
                              <input
                                value={trustProvisioningJustification}
                                maxLength={500}
                                onChange={(event) =>
                                  setTrustProvisioningJustification(event.target.value)
                                }
                                placeholder="Record the approved reason for publishing trust metadata"
                              />
                            </label>
                            {trustProvisioningMutation.isError && (
                              <div className="impact-message impact-error" role="alert">
                                <AlertTriangle size={16} /> Trust metadata was not published. Refresh
                                the governed state and trust plan before retrying.
                              </div>
                            )}
                            <div className="trust-provisioning-confirm-actions">
                              <button
                                type="button"
                                onClick={() => {
                                  setTrustProvisioningPending(false);
                                  setTrustProvisioningJustification("");
                                }}
                              >
                                Cancel
                              </button>
                              <button
                                className="trust-provisioning-confirm"
                                type="button"
                                disabled={
                                  trustProvisioningJustification.trim().length < 12 ||
                                  trustProvisioningMutation.isPending
                                }
                                onClick={() => trustProvisioningMutation.mutate()}
                              >
                                <ShieldCheck size={14} /> Confirm trust
                              </button>
                            </div>
                          </div>
                        )}
                      {trustExecution && (
                        <div className={`trust-provisioning-result ${trustExecution.state}`}>
                          <div className="trust-provisioning-result-heading">
                            {trustExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>Trust provisioning {trustExecution.state}</strong>
                              <code>{trustExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${trustExecution.state}`}>
                              {trustExecution.state}
                            </span>
                          </div>
                          <div className="trust-provisioning-summary">
                            <div>
                              <span>Anchors</span>
                              <strong>{trustExecution.anchor_count}</strong>
                            </div>
                            <div>
                              <span>Identities</span>
                              <strong>{trustExecution.workload_identity_count}</strong>
                            </div>
                            <div>
                              <span>Files</span>
                              <strong>{trustExecution.file_count}</strong>
                            </div>
                            <div>
                              <span>Verified bytes</span>
                              <strong>{trustExecution.total_bytes.toLocaleString()}</strong>
                            </div>
                          </div>
                          {trustExecution.evidence.length > 0 && (
                            <div className="trust-evidence-list">
                              {trustExecution.evidence.map((item) => (
                                <div key={item.file_id}>
                                  <div>
                                    <code>{item.file_id}</code>
                                    <span>{item.disposition}</span>
                                  </div>
                                  <code>{item.sha256.slice(0, 20)}...</code>
                                </div>
                              ))}
                            </div>
                          )}
                          {trustExecution.state === "failed" && (
                            <p className="trust-recovery-note">
                              Prior verified trust content was preserved. Correct the bounded failure
                              and retry under the active lease.
                            </p>
                          )}
                        </div>
                      )}
                      {dataPhaseAvailable && bootstrapDataPlan && !dataInitializationPending && (
                        <div className="data-initialization-action">
                          <div>
                            <strong>Initialize governed schema state</strong>
                            <p>
                              Applies {bootstrapDataPlan.migrations.length} ordered, reversible
                              migration records to the approved {bootstrapDataPlan.target_kind} target.
                              External databases, services, backups, and infrastructure remain unchanged.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setDataInitializationResult(null);
                              setDataInitializationPending(true);
                            }}
                          >
                            <Database size={14} /> Review data
                          </button>
                        </div>
                      )}
                      {dataInitializationPending && dataPhaseAvailable && bootstrapDataPlan && (
                        <div className="data-initialization-confirmation" role="dialog">
                          <div>
                            <strong>Confirm clean data-schema initialization</strong>
                            <p>
                              Target {bootstrapDataPlan.target_id} is {bootstrapDataPlan.target_state}.
                              Schema revision will move from {bootstrapDataPlan.current_revision} to {" "}
                              {bootstrapDataPlan.target_revision}. Backup is not applicable to this clean,
                              synthetic initialization.
                            </p>
                          </div>
                          <div className="data-migration-list">
                            {bootstrapDataPlan.migrations.map((migration) => (
                              <div key={migration.migration_id}>
                                <span>{migration.sequence}</span>
                                <div>
                                  <code>{migration.migration_id}</code>
                                  <small>
                                    {migration.from_revision} to {migration.to_revision} / {" "}
                                    {migration.expected_object_count} objects
                                  </small>
                                </div>
                                <strong>reversible</strong>
                              </div>
                            ))}
                          </div>
                          <label>
                            Data justification
                            <input
                              value={dataInitializationJustification}
                              maxLength={500}
                              onChange={(event) =>
                                setDataInitializationJustification(event.target.value)
                              }
                              placeholder="Record the reviewed reason for initializing schema state"
                            />
                          </label>
                          {dataInitializationMutation.isError && (
                            <div className="impact-message impact-error" role="alert">
                              <AlertTriangle size={16} /> Schema state was not initialized. Refresh the
                              governed state and exact data plan before retrying.
                            </div>
                          )}
                          <div className="data-initialization-confirm-actions">
                            <button
                              type="button"
                              onClick={() => {
                                setDataInitializationPending(false);
                                setDataInitializationJustification("");
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              className="data-initialization-confirm"
                              type="button"
                              disabled={
                                dataInitializationJustification.trim().length < 12 ||
                                dataInitializationMutation.isPending
                              }
                              onClick={() => dataInitializationMutation.mutate()}
                            >
                              <Database size={14} /> Confirm data
                            </button>
                          </div>
                        </div>
                      )}
                      {dataExecution && (
                        <div className={`data-initialization-result ${dataExecution.state}`}>
                          <div className="data-initialization-result-heading">
                            {dataExecution.state === "completed" ? (
                              <CheckCircle2 size={18} />
                            ) : (
                              <AlertTriangle size={18} />
                            )}
                            <div>
                              <strong>Data initialization {dataExecution.state}</strong>
                              <code>{dataExecution.result_code}</code>
                            </div>
                            <span className={`state-badge ${dataExecution.state}`}>
                              {dataExecution.state}
                            </span>
                          </div>
                          <div className="data-initialization-summary">
                            <div>
                              <span>Revision</span>
                              <strong>{dataExecution.from_revision} to {dataExecution.to_revision}</strong>
                            </div>
                            <div>
                              <span>Migrations</span>
                              <strong>{dataExecution.migration_count}</strong>
                            </div>
                            <div>
                              <span>Verified objects</span>
                              <strong>{dataExecution.verified_object_count}</strong>
                            </div>
                            <div>
                              <span>Backup</span>
                              <strong>Not applicable</strong>
                            </div>
                          </div>
                          {dataExecution.evidence.length > 0 && (
                            <div className="data-evidence-list">
                              {dataExecution.evidence.map((item) => (
                                <div key={item.evidence_id}>
                                  <div>
                                    <code>{item.evidence_id}</code>
                                    <span>{item.disposition}</span>
                                  </div>
                                  <code>{item.sha256.slice(0, 20)}...</code>
                                </div>
                              ))}
                            </div>
                          )}
                          {dataExecution.state === "failed" && (
                            <p className="data-recovery-note">
                              No partial schema state was published. Correct the bounded failure and
                              retry under the active lease.
                            </p>
                          )}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="bootstrap-state-empty">
                      <LockKeyhole size={18} />
                      <div>
                        <strong>No checkpoint state has been initialized.</strong>
                        <p>The approved plan remains read-only and no lease is held.</p>
                      </div>
                    </div>
                  )}
                  {bootstrapLeaseAvailable && !bootstrapClaimPending && (
                    <div className="bootstrap-claim-action">
                      <div>
                        <strong>
                          {bootstrapState.run ? "Reclaim coordination lease" : "Initialize bootstrap run"}
                        </strong>
                        <p>
                          Establishes the exact plan lock and checkpoint boundary. It does not run a
                          phase or write release artifacts.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setBootstrapClaimResult(null);
                          setBootstrapClaimPending(true);
                        }}
                      >
                        <LockKeyhole size={14} /> Review lease
                      </button>
                    </div>
                  )}
                  {bootstrapClaimPending && bootstrapLeaseAvailable && (
                    <div className="bootstrap-claim-confirmation" role="dialog">
                      <div>
                        <strong>Confirm bootstrap coordination lease</strong>
                        <p>
                          The exact release, configuration, plan, and phase order will be locked to
                          this browser session for 10 minutes.
                        </p>
                      </div>
                      <label>
                        Lease justification
                        <input
                          value={bootstrapClaimJustification}
                          maxLength={500}
                          onChange={(event) => setBootstrapClaimJustification(event.target.value)}
                          placeholder="Record the reviewed reason for coordinating this bootstrap run"
                        />
                      </label>
                      {bootstrapClaimMutation.isError && (
                        <div className="impact-message impact-error" role="alert">
                          <AlertTriangle size={16} /> The coordination lease was not established.
                        </div>
                      )}
                      <div className="bootstrap-claim-confirm-actions">
                        <button
                          type="button"
                          onClick={() => {
                            setBootstrapClaimPending(false);
                            setBootstrapClaimJustification("");
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          className="bootstrap-claim-confirm"
                          type="button"
                          disabled={
                            bootstrapClaimJustification.trim().length < 12 ||
                            bootstrapClaimMutation.isPending
                          }
                          onClick={() => bootstrapClaimMutation.mutate()}
                        >
                          <LockKeyhole size={14} /> Confirm lease
                        </button>
                      </div>
                    </div>
                  )}
                  {bootstrapClaimResult && (
                    <div className="bootstrap-claim-result" role="status">
                      <CheckCircle2 size={18} />
                      <div>
                        <strong>Coordination lease established</strong>
                        <p>
                          Run {bootstrapClaimResult.run.run_id} is locked at revision {bootstrapClaimResult.run.version}.
                        </p>
                      </div>
                    </div>
                  )}
                  <div className="safety-notice">
                    <ShieldCheck size={16} />
                    <span>
                      A confirmed acquisition may change only the governed Atlas artifact store. No
                      configuration, service, rollback, connector, or infrastructure operation is
                      authorized.
                    </span>
                  </div>
                </section>
              )}

              {bootstrapInvalidation && (
                <section className="workspace-section bootstrap-invalidation-section">
                  <div className="section-heading bootstrap-invalidation-heading">
                    <div>
                      <p className="eyebrow">RESUME SAFETY</p>
                      <h2>Checkpoint invalidation preview</h2>
                      <p>Candidate inputs compared with the current run without changing it.</p>
                    </div>
                    <span className={`state-badge ${bootstrapInvalidation.state}`}>
                      <Scale size={14} /> {bootstrapInvalidation.state}
                    </span>
                  </div>
                  {bootstrapInvalidation.state === "empty" ? (
                    <div className="bootstrap-state-empty">
                      <Scale size={18} />
                      <div>
                        <strong>No current run is available for drift comparison.</strong>
                        <p>Initialize governed checkpoint state before evaluating resume safety.</p>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="bootstrap-invalidation-summary">
                        <div>
                          <span>Source revision</span>
                          <strong>{bootstrapInvalidation.source_run_version}</strong>
                        </div>
                        <div>
                          <span>Earliest boundary</span>
                          <code>{bootstrapInvalidation.earliest_affected_phase_id ?? "none"}</code>
                        </div>
                        <div>
                          <span>Reusable</span>
                          <strong>{bootstrapInvalidation.reusable_checkpoint_phase_ids.length}</strong>
                        </div>
                        <div>
                          <span>Invalidated</span>
                          <strong>{bootstrapInvalidation.invalidated_checkpoint_phase_ids.length}</strong>
                        </div>
                      </div>
                      {bootstrapInvalidation.changes.length > 0 && (
                        <div className="bootstrap-change-list">
                          {bootstrapInvalidation.changes.map((change) => (
                            <article key={change.reason_code}>
                              <div>
                                <code>{change.reason_code}</code>
                                <strong>{change.field.replaceAll("_", " ")}</strong>
                              </div>
                              <span>from {change.earliest_affected_phase_id}</span>
                            </article>
                          ))}
                        </div>
                      )}
                      <div className="bootstrap-invalidation-columns">
                        <div>
                          <h3>Reusable checkpoints</h3>
                          <p>
                            {bootstrapInvalidation.reusable_checkpoint_phase_ids.join(", ") ||
                              "None"}
                          </p>
                        </div>
                        <div>
                          <h3>Invalidated checkpoints</h3>
                          <p>
                            {bootstrapInvalidation.invalidated_checkpoint_phase_ids.join(", ") ||
                              "None"}
                          </p>
                        </div>
                        <div>
                          <h3>Downstream review</h3>
                          <p>{bootstrapInvalidation.downstream_phase_ids.join(", ") || "None"}</p>
                        </div>
                      </div>
                      {bootstrapInvalidation.state === "drifted" &&
                        bootstrapState?.run &&
                        bootstrapState.lease_held_by_current_actor &&
                        bootstrapInvalidation.source_run_version === bootstrapState.run.version &&
                        !bootstrapRebasePending && (
                          <div className="bootstrap-rebase-action">
                            <div>
                              <strong>Apply the reviewed checkpoint boundary</strong>
                              <p>
                                This updates Atlas coordination metadata only. It does not run any
                                deployment phase.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                setBootstrapRebaseResult(null);
                                setBootstrapRebasePending(true);
                              }}
                            >
                              <RefreshCw size={14} /> Review plan update
                            </button>
                          </div>
                        )}
                      {bootstrapRebasePending && bootstrapState?.run && (
                        <div className="bootstrap-rebase-confirmation" role="dialog">
                          <div>
                            <strong>Confirm checkpoint metadata update</strong>
                            <p>
                              Revision {bootstrapState.run.version} will move to the candidate plan.
                              Only checkpoints before {" "}
                              {bootstrapInvalidation.earliest_affected_phase_id} remain reusable.
                            </p>
                          </div>
                          <label>
                            Review justification
                            <input
                              value={bootstrapRebaseJustification}
                              maxLength={500}
                              onChange={(event) =>
                                setBootstrapRebaseJustification(event.target.value)
                              }
                              placeholder="Record the reviewed reason for this plan update"
                            />
                          </label>
                          {bootstrapRebaseMutation.isError && (
                            <div className="impact-message impact-error">
                              <AlertTriangle size={16} /> The checkpoint update was not completed.
                            </div>
                          )}
                          <div className="bootstrap-rebase-confirm-actions">
                            <button
                              type="button"
                              onClick={() => {
                                setBootstrapRebasePending(false);
                                setBootstrapRebaseJustification("");
                              }}
                            >
                              Cancel
                            </button>
                            <button
                              className="bootstrap-rebase-confirm"
                              type="button"
                              disabled={
                                bootstrapRebaseJustification.trim().length < 12 ||
                                bootstrapRebaseMutation.isPending
                              }
                              onClick={() => bootstrapRebaseMutation.mutate()}
                            >
                              <RefreshCw size={14} /> Confirm checkpoint update
                            </button>
                          </div>
                        </div>
                      )}
                      {bootstrapRebaseResult && (
                        <div className="bootstrap-rebase-result" role="status">
                          <CheckCircle2 size={18} />
                          <div>
                            <strong>
                              Plan metadata updated to revision {bootstrapRebaseResult.run.version}
                            </strong>
                            <p>
                              Preserved: {" "}
                              {bootstrapRebaseResult.preserved_checkpoint_phase_ids.join(", ") ||
                                "None"}
                              . Invalidated: {" "}
                              {bootstrapRebaseResult.invalidated_checkpoint_phase_ids.join(", ") ||
                                "None"}
                              .
                            </p>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  <div className="safety-notice">
                    <ShieldCheck size={16} />
                    <span>
                      Preview is read-only. A confirmed plan update changes checkpoint metadata only;
                      no lease, file, phase, rollback, or infrastructure operation is authorized.
                    </span>
                  </div>
                </section>
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

                  {identity && identity.authentication.method !== "development" && (
                    <section className="workspace-section session-section">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">SESSION SECURITY</p>
                          <h2>Browser sessions</h2>
                        </div>
                        <span className="session-count">
                          {sessions?.length ?? 0}{sessionInventory?.truncated ? "+" : ""} visible
                        </span>
                      </div>
                      {sessionsQuery.isLoading && (
                        <div className="impact-message">
                          <Clock3 size={18} /> Reading authorized session inventory
                        </div>
                      )}
                      {sessionsQuery.isError && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> Session inventory is unavailable.
                        </div>
                      )}
                      {revokeSessionMutation.isError && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> Session revocation was not completed.
                        </div>
                      )}
                      {sessions?.length === 0 && (
                        <div className="impact-message">No browser sessions are visible.</div>
                      )}
                      {sessions && sessions.length > 0 && (
                        <div className="session-list">
                          {sessions.map((session) => (
                            <div className="session-row" key={session.session_id}>
                              <div className="session-icon"><Monitor size={17} /></div>
                              <div className="session-detail">
                                <strong>{session.current ? "Current session" : "Browser session"}</strong>
                                <span>Last active {formatTimestamp(session.last_seen_at)}</span>
                              </div>
                              <div className="session-expiry">
                                <span>Expires</span>
                                <strong>{formatTimestamp(session.idle_expires_at)}</strong>
                              </div>
                              <span className={`state-badge ${session.state}`}>{session.state}</span>
                              {session.state === "active" && (
                                <button
                                  className="icon-button session-revoke"
                                  type="button"
                                  aria-label={
                                    session.current ? "Revoke current session" : "Revoke browser session"
                                  }
                                  title="Revoke session"
                                  disabled={revokeSessionMutation.isPending}
                                  onClick={() => revokeSessionMutation.mutate(session.session_id)}
                                >
                                  <Trash2 size={17} />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {identity && identity.authentication.method !== "development" && (
                    <section className="workspace-section api-credential-section">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">API ACCESS</p>
                          <h2>Personal read-only tokens</h2>
                        </div>
                        <span className="session-count">
                          {apiCredentials?.filter((item) => item.state === "active").length ?? 0}
                          {apiCredentialInventory?.truncated ? "+" : ""} active
                        </span>
                      </div>

                      {apiCredentialsQuery.isLoading && (
                        <div className="impact-message">
                          <Clock3 size={18} /> Reading authorized API access
                        </div>
                      )}
                      {apiCredentialsQuery.isError && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> API access is unavailable.
                        </div>
                      )}

                      {issuedApiToken && (
                        <div className="issued-token" role="status">
                          <div className="issued-token-heading">
                            <div>
                              <span>NEW TOKEN</span>
                              <strong>Available once</strong>
                            </div>
                            <button
                              className="icon-button"
                              type="button"
                              aria-label="Dismiss API token"
                              title="Dismiss token"
                              onClick={() => setIssuedApiToken(null)}
                            >
                              <X size={17} />
                            </button>
                          </div>
                          <div className="issued-token-value">
                            <code>{issuedApiToken}</code>
                            <button
                              className="icon-button"
                              type="button"
                              aria-label="Copy API token"
                              title="Copy token"
                              onClick={() => void navigator.clipboard.writeText(issuedApiToken)}
                            >
                              <Copy size={17} />
                            </button>
                          </div>
                        </div>
                      )}

                      {apiCredentialInventory && (
                        <form
                          className="api-credential-form"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (
                              apiCredentialName.trim() &&
                              apiCredentialPurpose.trim() &&
                              selectedApiGrants.length > 0 &&
                              !createApiCredentialMutation.isPending
                            ) {
                              createApiCredentialMutation.mutate();
                            }
                          }}
                        >
                          <div className="api-credential-fields">
                            <label>
                              <span>Name</span>
                              <input
                                value={apiCredentialName}
                                onChange={(event) => setApiCredentialName(event.target.value)}
                                maxLength={80}
                                required
                              />
                            </label>
                            <label>
                              <span>Purpose</span>
                              <input
                                value={apiCredentialPurpose}
                                onChange={(event) => setApiCredentialPurpose(event.target.value)}
                                maxLength={240}
                                required
                              />
                            </label>
                            <label>
                              <span>Lifetime</span>
                              <select
                                value={apiCredentialLifetime}
                                onChange={(event) =>
                                  setApiCredentialLifetime(Number(event.target.value))
                                }
                              >
                                <option value={5}>5 minutes</option>
                                <option value={15}>15 minutes</option>
                                <option value={30}>30 minutes</option>
                                <option value={60}>60 minutes</option>
                              </select>
                            </label>
                          </div>
                          <fieldset className="api-grant-options">
                            <legend>Read access</legend>
                            {availableApiGrants.map((grant) => (
                              <label key={grant.permission_id}>
                                <input
                                  type="checkbox"
                                  checked={selectedApiGrants.includes(grant.permission_id)}
                                  onChange={(event) =>
                                    setSelectedApiGrants((current) =>
                                      event.target.checked
                                        ? [...current, grant.permission_id]
                                        : current.filter((item) => item !== grant.permission_id),
                                    )
                                  }
                                />
                                <span>{apiGrantLabel(grant.permission_id)}</span>
                              </label>
                            ))}
                          </fieldset>
                          <div className="api-credential-submit">
                            <span>Read-only · expires automatically</span>
                            <button
                              className="run-check-button"
                              type="submit"
                              disabled={
                                createApiCredentialMutation.isPending ||
                                !apiCredentialName.trim() ||
                                !apiCredentialPurpose.trim() ||
                                selectedApiGrants.length === 0
                              }
                            >
                              {createApiCredentialMutation.isPending ? (
                                <RefreshCw className="spin" size={16} />
                              ) : (
                                <KeyRound size={16} />
                              )}
                              Create token
                            </button>
                          </div>
                        </form>
                      )}

                      {(createApiCredentialMutation.isError ||
                        revokeApiCredentialMutation.isError) && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> API access change was not completed.
                        </div>
                      )}

                      {apiCredentials?.length === 0 && (
                        <div className="impact-message">No personal API tokens are visible.</div>
                      )}
                      {apiCredentials && apiCredentials.length > 0 && (
                        <div className="api-credential-list">
                          {apiCredentials.map((credential) => (
                            <div className="api-credential-row" key={credential.credential_id}>
                              <div className="session-icon"><KeyRound size={17} /></div>
                              <div className="api-credential-detail">
                                <strong>{credential.display_name}</strong>
                                <span>{credential.purpose}</span>
                                <small>
                                  {credential.grants.map((grant) =>
                                    apiGrantLabel(grant.permission_id),
                                  ).join(" · ")}
                                </small>
                              </div>
                              <div className="session-expiry">
                                <span>Expires</span>
                                <strong>{formatTimestamp(credential.expires_at)}</strong>
                              </div>
                              <span className={`state-badge ${credential.state}`}>
                                {credential.state}
                              </span>
                              {credential.state === "active" && (
                                <button
                                  className="icon-button session-revoke"
                                  type="button"
                                  aria-label={`Revoke ${credential.display_name}`}
                                  title="Revoke token"
                                  disabled={revokeApiCredentialMutation.isPending}
                                  onClick={() =>
                                    revokeApiCredentialMutation.mutate(
                                      credential.credential_id,
                                    )
                                  }
                                >
                                  <Trash2 size={17} />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  {identityGovernance && (
                    <section className="workspace-section identity-governance-section">
                      <div className="section-heading governance-heading">
                        <div>
                          <p className="eyebrow">IDENTITY GOVERNANCE</p>
                          <h2>Administrative access review</h2>
                        </div>
                        <span className="session-count">
                          {identityGovernance.subjects.length} identities {" · "}
                          {identityGovernance.sessions.length +
                            identityGovernance.api_credentials.length}
                          {identityGovernance.truncated ? "+" : ""} active
                        </span>
                      </div>

                      <div className="governance-toolbar">
                        <label>
                          <span>Search identities and credentials</span>
                          <div className="governance-input">
                            <Search size={15} />
                            <input
                              aria-label="Search identity governance"
                              value={governanceSearch}
                              maxLength={128}
                              placeholder="Subject, provider, session, or token name"
                              onChange={(event) => setGovernanceSearch(event.target.value)}
                            />
                          </div>
                        </label>
                        <label>
                          <span>Governance reason</span>
                          <input
                            aria-label="Identity governance revocation reason"
                            value={governanceReason}
                            maxLength={240}
                            placeholder="Required for revocation or identity disablement"
                            onChange={(event) => setGovernanceReason(event.target.value)}
                          />
                        </label>
                      </div>

                      {(disableGovernedIdentityMutation.isError ||
                        revokeGovernedSessionMutation.isError ||
                        revokeGovernedApiCredentialMutation.isError) && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> The administrative identity change was not
                          completed; prior access state remains authoritative.
                        </div>
                      )}

                      <div className="governance-panel governance-subject-panel">
                        <div className="governance-panel-heading">
                          <div>
                            <UserCheck size={17} />
                            <h3>Enterprise identities</h3>
                          </div>
                          <span>{identityGovernance.subjects.length}</span>
                        </div>
                        {identityGovernance.subjects.length === 0 && (
                          <div className="governance-empty">No matching enterprise identities.</div>
                        )}
                        <div className="governance-subject-records">
                          {identityGovernance.subjects.map((governedSubject) => {
                            const confirming =
                              pendingDisableSubjectId === governedSubject.subject_id;
                            return (
                              <article
                                className="governance-record governance-subject-record"
                                key={governedSubject.subject_id}
                              >
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{governedSubject.display_name}</strong>
                                    <span>{governedSubject.subject_id}</span>
                                  </div>
                                  <span className={`state-badge ${governedSubject.state}`}>
                                    {governedSubject.state}
                                  </span>
                                </div>
                                <dl>
                                  <div>
                                    <dt>Provider</dt>
                                    <dd>{governedSubject.provider_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Browser sessions</dt>
                                    <dd>{governedSubject.active_session_count} active</dd>
                                  </div>
                                  <div>
                                    <dt>Personal tokens</dt>
                                    <dd>{governedSubject.active_api_credential_count} active</dd>
                                  </div>
                                  <div>
                                    <dt>Observed</dt>
                                    <dd>{formatTimestamp(governedSubject.observed_at)}</dd>
                                  </div>
                                </dl>
                                {governedSubject.disabled_at && (
                                  <p>
                                    Disabled {formatTimestamp(governedSubject.disabled_at)}. New
                                    authentication and personal-token issuance remain blocked.
                                  </p>
                                )}
                                {confirming && governedSubject.state === "active" && (
                                  <div className="governance-disable-confirmation" role="dialog">
                                    <div>
                                      <strong>Confirm identity disablement</strong>
                                      <p>
                                        This disables {governedSubject.display_name} and atomically
                                        revokes {governedSubject.active_session_count} browser
                                        session(s) and {" "}
                                        {governedSubject.active_api_credential_count} personal
                                        token(s). Re-enable is not part of this slice.
                                      </p>
                                    </div>
                                    <div className="governance-confirm-actions">
                                      <button
                                        type="button"
                                        onClick={() => setPendingDisableSubjectId(null)}
                                      >
                                        Cancel
                                      </button>
                                      <button
                                        className="governance-disable-confirm"
                                        type="button"
                                        disabled={
                                          !governanceReason.trim() ||
                                          disableGovernedIdentityMutation.isPending
                                        }
                                        onClick={() =>
                                          disableGovernedIdentityMutation.mutate({
                                            subjectId: governedSubject.subject_id,
                                            expectedVersion: governedSubject.version,
                                            reason: governanceReason.trim(),
                                            idempotencyKey: governanceIdempotencyKey(
                                              "identity",
                                              governedSubject.version,
                                            ),
                                          })
                                        }
                                      >
                                        <UserX size={14} /> Confirm disablement
                                      </button>
                                    </div>
                                  </div>
                                )}
                                <div className="governance-record-footer">
                                  <code>
                                    {governedSubject.authentication_method} · v
                                    {governedSubject.version}
                                  </code>
                                  {governedSubject.state === "active" && !confirming && (
                                    <button
                                      className="governance-revoke"
                                      type="button"
                                      disabled={disableGovernedIdentityMutation.isPending}
                                      onClick={() =>
                                        setPendingDisableSubjectId(governedSubject.subject_id)
                                      }
                                    >
                                      <UserX size={14} /> Disable identity
                                    </button>
                                  )}
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      </div>

                      <div className="governance-grid">
                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <Monitor size={17} />
                              <h3>Browser sessions</h3>
                            </div>
                            <span>{identityGovernance.sessions.length}</span>
                          </div>
                          {identityGovernance.sessions.length === 0 && (
                            <div className="governance-empty">No matching sessions.</div>
                          )}
                          <div className="governance-records">
                            {identityGovernance.sessions.map((session) => (
                              <article className="governance-record" key={session.session_id}>
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{session.subject_display_name}</strong>
                                    <span>{session.subject_id}</span>
                                  </div>
                                  <span className="state-badge active">active</span>
                                </div>
                                <dl>
                                  <div>
                                    <dt>Provider</dt>
                                    <dd>{session.provider_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Last active</dt>
                                    <dd>{formatTimestamp(session.last_seen_at)}</dd>
                                  </div>
                                  <div>
                                    <dt>Idle expiry</dt>
                                    <dd>{formatTimestamp(session.idle_expires_at)}</dd>
                                  </div>
                                </dl>
                                <div className="governance-record-footer">
                                  <code>{session.session_id}</code>
                                  <button
                                    className="governance-revoke"
                                    type="button"
                                    disabled={
                                      !governanceReason.trim() ||
                                      revokeGovernedSessionMutation.isPending
                                    }
                                    onClick={() =>
                                      revokeGovernedSessionMutation.mutate({
                                        sessionId: session.session_id,
                                        expectedVersion: session.version,
                                        reason: governanceReason.trim(),
                                        idempotencyKey: governanceIdempotencyKey(
                                          "session",
                                          session.version,
                                        ),
                                      })
                                    }
                                  >
                                    <Trash2 size={14} /> Revoke session
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>

                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <KeyRound size={17} />
                              <h3>Personal API tokens</h3>
                            </div>
                            <span>{identityGovernance.api_credentials.length}</span>
                          </div>
                          {identityGovernance.api_credentials.length === 0 && (
                            <div className="governance-empty">No matching personal tokens.</div>
                          )}
                          <div className="governance-records">
                            {identityGovernance.api_credentials.map((credential) => (
                              <article
                                className="governance-record"
                                key={credential.credential_id}
                              >
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{credential.display_name}</strong>
                                    <span>
                                      {credential.subject_display_name} {" · "}
                                      {credential.subject_id}
                                    </span>
                                  </div>
                                  <span className="state-badge active">active</span>
                                </div>
                                <p>{credential.purpose}</p>
                                <dl>
                                  <div>
                                    <dt>Provider</dt>
                                    <dd>{credential.provider_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Grant</dt>
                                    <dd>
                                      {credential.grants
                                        .map((grant) => apiGrantLabel(grant.permission_id))
                                        .join(" · ")}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt>Expires</dt>
                                    <dd>{formatTimestamp(credential.expires_at)}</dd>
                                  </div>
                                </dl>
                                <div className="governance-record-footer">
                                  <code>{credential.credential_id}</code>
                                  <button
                                    className="governance-revoke"
                                    type="button"
                                    disabled={
                                      !governanceReason.trim() ||
                                      revokeGovernedApiCredentialMutation.isPending
                                    }
                                    onClick={() =>
                                      revokeGovernedApiCredentialMutation.mutate({
                                        credentialId: credential.credential_id,
                                        expectedVersion: credential.version,
                                        reason: governanceReason.trim(),
                                        idempotencyKey: governanceIdempotencyKey(
                                          "token",
                                          credential.version,
                                        ),
                                      })
                                    }
                                  >
                                    <Trash2 size={14} /> Revoke token
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>
                      </div>
                    </section>
                  )}

                  {workloadInventory && (
                    <section className="workspace-section workload-identity-section">
                      <div className="section-heading governance-heading">
                        <div>
                          <p className="eyebrow">WORKLOAD TRUST</p>
                          <h2>Platform workload identities</h2>
                          <p>
                            Short-lived service credentials with exact audience and environment
                            boundaries.
                          </p>
                        </div>
                        <span className="session-count">
                          {workloadInventory.identities.length} identities {" · "}
                          {workloadInventory.credentials.length}
                          {workloadInventory.truncated ? "+" : ""} credentials
                        </span>
                      </div>

                      <div className="governance-toolbar workload-toolbar">
                        <label>
                          <span>Search workload identities</span>
                          <div className="governance-input">
                            <Search size={15} />
                            <input
                              aria-label="Search workload identities"
                              value={workloadSearch}
                              maxLength={128}
                              placeholder="Service, instance, owner, or audience"
                              onChange={(event) => setWorkloadSearch(event.target.value)}
                            />
                          </div>
                        </label>
                        <label>
                          <span>Governance reason</span>
                          <input
                            aria-label="Workload identity governance reason"
                            value={workloadReason}
                            maxLength={240}
                            placeholder="Required for create, rotate, or revoke"
                            onChange={(event) => setWorkloadReason(event.target.value)}
                          />
                        </label>
                      </div>

                      {(createWorkloadIdentityMutation.isError ||
                        rotateWorkloadCredentialMutation.isError ||
                        revokeWorkloadCredentialMutation.isError) && (
                        <div className="impact-message impact-error">
                          <AlertTriangle size={18} /> The workload identity change was not
                          completed; prior trust state remains authoritative.
                        </div>
                      )}

                      {issuedWorkloadToken && (
                        <div className="workload-token-once" role="status">
                          <div>
                            <KeyRound size={18} />
                            <div>
                              <strong>Credential shown once</strong>
                              <p>Store it in the approved secret manager before dismissing.</p>
                            </div>
                          </div>
                          <code>{issuedWorkloadToken}</code>
                          <div className="workload-token-actions">
                            <button
                              type="button"
                              title="Copy credential"
                              aria-label="Copy workload credential"
                              onClick={() => void navigator.clipboard?.writeText(issuedWorkloadToken)}
                            >
                              <Copy size={15} />
                            </button>
                            <button type="button" onClick={() => setIssuedWorkloadToken(null)}>
                              Dismiss
                            </button>
                          </div>
                        </div>
                      )}

                      <form
                        className="workload-create-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          setPendingWorkloadAction({ kind: "create" });
                        }}
                      >
                        <div className="governance-panel-heading">
                          <div>
                            <Server size={17} />
                            <h3>Register workload identity</h3>
                          </div>
                          <span>C2 governed</span>
                        </div>
                        <div className="workload-form-grid">
                          <label>
                            <span>Identity ID</span>
                            <input
                              aria-label="Workload identity ID"
                              value={workloadIdentityId}
                              onChange={(event) => setWorkloadIdentityId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Display name</span>
                            <input
                              aria-label="Workload display name"
                              value={workloadDisplayName}
                              onChange={(event) => setWorkloadDisplayName(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Service</span>
                            <input
                              aria-label="Workload service ID"
                              value={workloadServiceId}
                              onChange={(event) => setWorkloadServiceId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Instance</span>
                            <input
                              aria-label="Workload instance ID"
                              value={workloadInstanceId}
                              onChange={(event) => setWorkloadInstanceId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Owner</span>
                            <input
                              aria-label="Workload owner subject ID"
                              value={workloadOwnerId}
                              onChange={(event) => setWorkloadOwnerId(event.target.value)}
                            />
                          </label>
                          <label>
                            <span>Audience</span>
                            <input
                              aria-label="Workload audience"
                              value={workloadAudience}
                              onChange={(event) => setWorkloadAudience(event.target.value)}
                            />
                          </label>
                          <label className="workload-form-wide">
                            <span>Secret reference</span>
                            <input
                              aria-label="Workload secret reference"
                              value={workloadSecretReference}
                              onChange={(event) => setWorkloadSecretReference(event.target.value)}
                            />
                          </label>
                          <label className="workload-form-wide">
                            <span>Purpose</span>
                            <input
                              aria-label="Workload purpose"
                              value={workloadPurpose}
                              onChange={(event) => setWorkloadPurpose(event.target.value)}
                            />
                          </label>
                        </div>
                        <button
                          className="governance-revoke workload-create-button"
                          type="submit"
                          disabled={
                            !workloadReason.trim() ||
                            !workloadIdentityId.trim() ||
                            createWorkloadIdentityMutation.isPending
                          }
                        >
                          <KeyRound size={14} /> Review creation
                        </button>
                      </form>

                      {pendingWorkloadAction?.kind === "create" && (
                        <div className="governance-disable-confirmation" role="dialog">
                          <div>
                            <strong>Confirm workload identity creation</strong>
                            <p>
                              Creates {workloadIdentityId} with one 10-minute credential for {" "}
                              {workloadAudience}. It receives no human role and no execution
                              authority.
                            </p>
                          </div>
                          <div className="governance-confirm-actions">
                            <button type="button" onClick={() => setPendingWorkloadAction(null)}>
                              Cancel
                            </button>
                            <button
                              className="governance-disable-confirm"
                              type="button"
                              onClick={() =>
                                createWorkloadIdentityMutation.mutate({
                                  identityId: workloadIdentityId.trim(),
                                  displayName: workloadDisplayName.trim(),
                                  serviceId: workloadServiceId.trim(),
                                  instanceId: workloadInstanceId.trim(),
                                  ownerSubjectId: workloadOwnerId.trim(),
                                  purpose: workloadPurpose.trim(),
                                  audience: workloadAudience.trim(),
                                  secretReferenceId: workloadSecretReference.trim(),
                                  lifetimeMinutes: 10,
                                  reason: workloadReason.trim(),
                                  idempotencyKey: governanceIdempotencyKey(
                                    "workload-create",
                                    1,
                                  ),
                                })
                              }
                            >
                              <ShieldCheck size={14} /> Confirm creation
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="governance-grid workload-grid">
                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <Server size={17} />
                              <h3>Service identities</h3>
                            </div>
                            <span>{workloadInventory.identities.length}</span>
                          </div>
                          {workloadInventory.identities.length === 0 && (
                            <div className="governance-empty">No matching workload identities.</div>
                          )}
                          <div className="governance-records">
                            {workloadInventory.identities.map((workload) => (
                              <article className="governance-record" key={workload.identity_id}>
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{workload.display_name}</strong>
                                    <span>{workload.identity_id}</span>
                                  </div>
                                  <span className={`state-badge ${workload.state}`}>
                                    {workload.state}
                                  </span>
                                </div>
                                <p>{workload.purpose}</p>
                                <dl>
                                  <div>
                                    <dt>Service / instance</dt>
                                    <dd>{workload.service_id} / {workload.instance_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Owner</dt>
                                    <dd>{workload.owner_subject_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Audience</dt>
                                    <dd>{workload.audiences.join(" · ")}</dd>
                                  </div>
                                </dl>
                                {pendingWorkloadAction?.kind === "rotate" &&
                                  pendingWorkloadAction.identityId === workload.identity_id && (
                                    <div className="governance-disable-confirmation" role="dialog">
                                      <div>
                                        <strong>Confirm credential rotation</strong>
                                        <p>
                                          Issues a new 10-minute credential. Existing active
                                          credentials retire after a two-minute overlap.
                                        </p>
                                      </div>
                                      <div className="governance-confirm-actions">
                                        <button
                                          type="button"
                                          onClick={() => setPendingWorkloadAction(null)}
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          className="governance-disable-confirm"
                                          type="button"
                                          onClick={() =>
                                            rotateWorkloadCredentialMutation.mutate({
                                              identityId: workload.identity_id,
                                              expectedVersion: workload.version,
                                              lifetimeMinutes: 10,
                                              overlapMinutes: 2,
                                              reason: workloadReason.trim(),
                                              idempotencyKey: governanceIdempotencyKey(
                                                "workload-rotate",
                                                workload.version,
                                              ),
                                            })
                                          }
                                        >
                                          <RefreshCw size={14} /> Confirm rotation
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                <div className="governance-record-footer">
                                  <code>v{workload.version} · {workload.environment_id}</code>
                                  <button
                                    className="governance-revoke"
                                    type="button"
                                    disabled={!workloadReason.trim()}
                                    onClick={() =>
                                      setPendingWorkloadAction({
                                        kind: "rotate",
                                        identityId: workload.identity_id,
                                        version: workload.version,
                                      })
                                    }
                                  >
                                    <RefreshCw size={14} /> Rotate credential
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>

                        <div className="governance-panel">
                          <div className="governance-panel-heading">
                            <div>
                              <KeyRound size={17} />
                              <h3>Credential health</h3>
                            </div>
                            <span>{workloadInventory.credentials.length}</span>
                          </div>
                          {workloadInventory.credentials.length === 0 && (
                            <div className="governance-empty">No workload credentials issued.</div>
                          )}
                          <div className="governance-records">
                            {workloadInventory.credentials.map((credential) => (
                              <article className="governance-record" key={credential.credential_id}>
                                <div className="governance-record-heading">
                                  <div>
                                    <strong>{credential.identity_id}</strong>
                                    <span>{credential.credential_id}</span>
                                  </div>
                                  <span className={`state-badge ${credential.state}`}>
                                    {credential.state}
                                  </span>
                                </div>
                                <dl>
                                  <div>
                                    <dt>Audience</dt>
                                    <dd>{credential.audiences.join(" · ")}</dd>
                                  </div>
                                  <div>
                                    <dt>Expires</dt>
                                    <dd>{formatTimestamp(credential.expires_at)}</dd>
                                  </div>
                                  <div>
                                    <dt>Signing key</dt>
                                    <dd>version {credential.key_version}</dd>
                                  </div>
                                </dl>
                                {pendingWorkloadAction?.kind === "revoke" &&
                                  pendingWorkloadAction.credentialId ===
                                    credential.credential_id && (
                                    <div className="governance-disable-confirmation" role="dialog">
                                      <div>
                                        <strong>Confirm immediate revocation</strong>
                                        <p>
                                          This credential stops authenticating immediately. The
                                          workload must already have replacement trust.
                                        </p>
                                      </div>
                                      <div className="governance-confirm-actions">
                                        <button
                                          type="button"
                                          onClick={() => setPendingWorkloadAction(null)}
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          className="governance-disable-confirm"
                                          type="button"
                                          onClick={() =>
                                            revokeWorkloadCredentialMutation.mutate({
                                              credentialId: credential.credential_id,
                                              expectedVersion: credential.version,
                                              reason: workloadReason.trim(),
                                              idempotencyKey: governanceIdempotencyKey(
                                                "workload-revoke",
                                                credential.version,
                                              ),
                                            })
                                          }
                                        >
                                          <Trash2 size={14} /> Confirm revocation
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                <div className="governance-record-footer">
                                  <code>v{credential.version}</code>
                                  {(credential.state === "active" ||
                                    credential.state === "retiring") && (
                                    <button
                                      className="governance-revoke"
                                      type="button"
                                      disabled={!workloadReason.trim()}
                                      onClick={() =>
                                        setPendingWorkloadAction({
                                          kind: "revoke",
                                          credentialId: credential.credential_id,
                                          version: credential.version,
                                        })
                                      }
                                    >
                                      <Trash2 size={14} /> Revoke credential
                                    </button>
                                  )}
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>
                      </div>
                    </section>
                  )}

                  <section className="workspace-section security-export-section">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">SECURITY EXPORT</p>
                        <h2>Syslog and SIEM delivery</h2>
                      </div>
                      {securityDestination && (
                        <span className={`security-export-state ${securityHealth?.state ?? "active"}`}>
                          <ShieldCheck size={14} /> {securityHealth?.state ?? "active"}
                        </span>
                      )}
                    </div>

                    {securityExportQuery.isLoading && (
                      <div className="impact-message">
                        <Clock3 size={18} /> Reading authorized export health
                      </div>
                    )}
                    {securityExportQuery.isError && (
                      <div className="impact-message impact-error">
                        <AlertTriangle size={18} /> Export health is unavailable; no delivery is
                        inferred.
                      </div>
                    )}
                    {securityExport && securityDestination && securityHealth && (
                      <>
                        <div className="security-export-grid">
                          <div className="security-destination">
                            <span>Destination</span>
                            <strong>{securityDestination.name}</strong>
                            <small>
                              {securityDestination.host}:{securityDestination.port}
                            </small>
                          </div>
                          <div>
                            <span>Transport</span>
                            <strong>TLS</strong>
                            <small>Server and hostname verified</small>
                          </div>
                          <div>
                            <span>Certificate</span>
                            <strong>{securityHealth.certificate_days_remaining} days</strong>
                            <small>Until expiry</small>
                          </div>
                          <div>
                            <span>Queue</span>
                            <strong>{securityHealth.queue_depth}</strong>
                            <small>{securityHealth.retrying_count} retrying</small>
                          </div>
                          <div>
                            <span>Transport handoffs</span>
                            <strong>{securityHealth.delivered_count}</strong>
                            <small>{securityHealth.dead_letter_count} dead-letter</small>
                          </div>
                        </div>

                        <div className="security-export-detail">
                          <div>
                            <h3>RFC 5424 preview</h3>
                            <p className="security-payload">{securityExport.preview_message.payload}</p>
                            <small>
                              {securityExport.mapping_version} · {securityExport.preview_message.payload_bytes} bytes · digest {securityExport.preview_message.content_digest.slice(0, 16)}…
                            </small>
                          </div>
                          <div className="security-export-action">
                            <dl>
                              <div>
                                <dt>Collector handoff</dt>
                                <dd>
                                  {securityHealth.last_transport_handoff_at
                                    ? formatTimestamp(securityHealth.last_transport_handoff_at)
                                    : "No handoff yet"}
                                </dd>
                              </div>
                              <div>
                                <dt>SIEM ingestion</dt>
                                <dd>Not confirmed</dd>
                              </div>
                            </dl>
                            <button
                              className="run-check-button"
                              type="button"
                              disabled={securityExportTestMutation.isPending}
                              onClick={() => securityExportTestMutation.mutate()}
                            >
                              {securityExportTestMutation.isPending ? (
                                <RefreshCw className="spin" size={16} />
                              ) : (
                                <Play size={16} />
                              )}
                              Send test event
                            </button>
                          </div>
                        </div>

                        {securityExportTestMutation.data && (
                          <div className="security-export-result" role="status">
                            <CheckCircle2 size={16} />
                            Transport handoff recorded. SIEM ingestion remains unconfirmed.
                          </div>
                        )}
                        {securityExportTestMutation.isError && (
                          <div className="security-export-result error-state" role="alert">
                            <AlertTriangle size={16} /> Test event was not delivered.
                          </div>
                        )}
                        <div className="safety-notice">
                          <ShieldCheck size={16} />
                          <span>{securityExport.safety_notice}</span>
                        </div>
                      </>
                    )}
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
                                  onClick={() => {
                                    setSelectedAssetId(asset.asset_id);
                                    investigationMutation.reset();
                                    rcaMutation.reset();
                                    recommendationMutation.reset();
                                    reportMutation.reset();
                                  }}
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

                  <section className="workspace-section health-checks-section">
                    <div className="section-heading health-check-heading">
                      <div>
                        <p className="eyebrow">SCHEDULED HEALTH CHECKS</p>
                        <h2>Governed read-only checks</h2>
                      </div>
                      <span className="data-profile">
                        <Clock3 size={14} /> Deterministic schedule
                      </span>
                    </div>

                    {healthChecksQuery.isLoading && (
                      <p className="context-empty">Loading authorized health checks...</p>
                    )}
                    {healthChecksQuery.isError && (
                      <p className="inline-alert">Authorized health-check context is unavailable.</p>
                    )}
                    {healthChecks && selectedHealthCheck && selectedHealthSchedule && (
                      <>
                        <div className="health-check-tabs" role="tablist" aria-label="Health checks">
                          {healthChecks.definitions.map((definition) => (
                            <button
                              key={definition.definition_id}
                              type="button"
                              role="tab"
                              aria-selected={
                                definition.definition_id === selectedHealthCheck.definition_id
                              }
                              className={
                                definition.definition_id === selectedHealthCheck.definition_id
                                  ? "active"
                                  : ""
                              }
                              onClick={() => setSelectedHealthCheckId(definition.definition_id)}
                            >
                              <Activity size={16} />
                              <span>{definition.title}</span>
                              <small>v{definition.version}</small>
                            </button>
                          ))}
                        </div>

                        <div className="health-check-toolbar">
                          <div>
                            <strong>{selectedHealthCheck.title}</strong>
                            <span>{selectedHealthCheck.capability_id}</span>
                          </div>
                          <button
                            className="run-check-button"
                            type="button"
                            disabled={
                              !selectedHealthCheck.enabled || runHealthCheckMutation.isPending
                            }
                            onClick={() =>
                              runHealthCheckMutation.mutate(selectedHealthCheck.definition_id)
                            }
                          >
                            {runHealthCheckMutation.isPending ? (
                              <RefreshCw className="spin" size={16} />
                            ) : (
                              <Play size={16} />
                            )}
                            {runHealthCheckMutation.isPending ? "Running" : "Run check"}
                          </button>
                        </div>

                        <div className="health-check-summary">
                          <div>
                            <span>Schedule</span>
                            <strong>Every {selectedHealthSchedule.interval_minutes} min</strong>
                            <small>Next {formatTimestamp(selectedHealthSchedule.next_due_at)}</small>
                          </div>
                          <div>
                            <span>Latest run</span>
                            <strong className={`run-state ${selectedHealthRun?.state ?? "unknown"}`}>
                              {selectedHealthRun?.state.replaceAll("_", " ") ?? "No run"}
                            </strong>
                            <small>{formatTimestamp(selectedHealthRun?.completed_at)}</small>
                          </div>
                          <div>
                            <span>Boundary</span>
                            <strong>{selectedHealthCheck.capability_class} read-only</strong>
                            <small>{selectedHealthCheck.limits.timeout_seconds}s timeout</small>
                          </div>
                          <div>
                            <span>Evidence</span>
                            <strong>{selectedHealthRun?.evidence.length ?? 0} records</strong>
                            <small>{selectedHealthRun?.step_count ?? 0} bounded steps</small>
                          </div>
                        </div>

                        {selectedHealthRun && (
                          <div className="health-check-detail-grid">
                            <div className="health-observations">
                              <h3>Latest observations</h3>
                              <div className="table-wrap">
                                <table>
                                  <thead>
                                    <tr>
                                      <th>Component</th>
                                      <th>Metric</th>
                                      <th>Value</th>
                                      <th>State</th>
                                      <th>Freshness</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {selectedHealthRun.observations.map((observation) => (
                                      <tr key={observation.observation_id}>
                                        <td>{observation.component}</td>
                                        <td className="mono-cell">{observation.metric}</td>
                                        <td>
                                          {observation.value}
                                          {observation.unit ? ` ${observation.unit}` : ""}
                                        </td>
                                        <td>
                                          <span className={`observation-state ${observation.state}`}>
                                            {observation.state === "normal" ? (
                                              <CheckCircle2 size={14} />
                                            ) : (
                                              <AlertTriangle size={14} />
                                            )}
                                            {observation.state}
                                          </span>
                                        </td>
                                        <td>
                                          <span className={`freshness ${observation.freshness}`}>
                                            {observation.freshness}
                                          </span>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            <div className="health-check-findings">
                              <h3>Findings and limits</h3>
                              {selectedHealthRun.findings.map((finding) => (
                                <article key={finding.finding_id}>
                                  <span className={`severity-badge ${finding.severity}`}>
                                    {finding.severity}
                                  </span>
                                  <strong>{finding.title}</strong>
                                  <p>{finding.summary}</p>
                                </article>
                              ))}
                              {selectedHealthRun.partial_reasons.map((reason) => (
                                <p className="health-limit-note" key={reason}>
                                  <CircleHelp size={15} /> {reason}
                                </p>
                              ))}
                              {selectedHealthRun.unknowns.map((unknown) => (
                                <p className="health-unknown" key={unknown}>
                                  {unknown}
                                </p>
                              ))}
                            </div>
                          </div>
                        )}

                        {runHealthCheckMutation.isError && (
                          <p className="inline-alert">The read-only health check could not run.</p>
                        )}
                        <div className="health-check-safety">
                          <ShieldCheck size={16} />
                          <span>{healthChecks.safety_notice}</span>
                        </div>
                      </>
                    )}
                  </section>

                  <section className="workspace-section reasoning-section" aria-live="polite">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">EVIDENCE-GROUNDED INVESTIGATION</p>
                        <h2>Reasoning artifact</h2>
                      </div>
                      {reasoningArtifact && (
                        <span className="reasoning-version">
                          <BrainCircuit size={14} /> Version {reasoningArtifact.version}
                        </span>
                      )}
                    </div>

                    {!reasoningArtifact && !investigationMutation.isPending && (
                      <div className="reasoning-empty">
                        <BrainCircuit size={21} />
                        <div>
                          <strong>Start a bounded investigation</strong>
                          <p>
                            The selected target will be assessed from authorized evidence without
                            claiming root cause or outage.
                          </p>
                        </div>
                      </div>
                    )}
                    {investigationMutation.isPending && (
                      <div className="reasoning-empty">
                        <Clock3 size={20} />
                        <div>
                          <strong>Assembling governed evidence</strong>
                          <p>Scope, citations, epistemic types, and safety checks are being validated.</p>
                        </div>
                      </div>
                    )}
                    {investigationMutation.isError && (
                      <div className="reasoning-empty reasoning-error">
                        <AlertTriangle size={20} />
                        <div>
                          <strong>Investigation unavailable</strong>
                          <p>No conclusion is shown when the governed artifact cannot be validated.</p>
                        </div>
                      </div>
                    )}

                    {reasoningArtifact && (
                      <>
                        <div className="reasoning-summary-grid">
                          <div>
                            <span>Confidence</span>
                            <strong className={`confidence ${reasoningArtifact.summary.confidence}`}>
                              {reasoningArtifact.summary.confidence}
                            </strong>
                            <p>{reasoningArtifact.summary.confidence_rationale}</p>
                          </div>
                          <div>
                            <span>Supported decision</span>
                            <strong>{reasoningArtifact.summary.supported_decision}</strong>
                          </div>
                          <div>
                            <span>Not supported</span>
                            <strong>{reasoningArtifact.summary.unsupported_decision}</strong>
                          </div>
                        </div>

                        <div className="reasoning-facts-grid">
                          <div>
                            <h3>Known</h3>
                            <ul>
                              {reasoningArtifact.summary.known.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h3>Inferred</h3>
                            <ul>
                              {reasoningArtifact.summary.inferred.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h3>Unknown</h3>
                            <ul>
                              {reasoningArtifact.summary.unknowns.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        <div className="reasoning-body-grid">
                          <div className="claim-ledger">
                            <h3>Typed claim ledger</h3>
                            {reasoningArtifact.claims.map((claim) => (
                              <article key={claim.claim_id}>
                                <div>
                                  <span className={`epistemic-type ${claim.epistemic_type}`}>
                                    {claim.epistemic_type.replaceAll("_", " ")}
                                  </span>
                                  <span className={`confidence ${claim.confidence}`}>
                                    {claim.confidence}
                                  </span>
                                </div>
                                <strong>{claim.text}</strong>
                                <small>
                                  {claim.supporting_evidence.length} supporting /{" "}
                                  {claim.contradicting_evidence.length} contradicting evidence
                                </small>
                              </article>
                            ))}
                          </div>

                          <div className="hypothesis-ledger">
                            <h3>Alternative hypotheses</h3>
                            {reasoningArtifact.hypotheses.map((hypothesis) => (
                              <article key={hypothesis.hypothesis_id}>
                                <div>
                                  <span className="state-badge">{hypothesis.state}</span>
                                  <span className={`confidence ${hypothesis.confidence}`}>
                                    {hypothesis.confidence}
                                  </span>
                                </div>
                                <strong>{hypothesis.statement}</strong>
                                <p>{hypothesis.confidence_rationale}</p>
                                <div className="next-check">
                                  <ShieldCheck size={14} />
                                  <span>
                                    {hypothesis.discriminating_checks[0]?.title} ·{" "}
                                    {hypothesis.discriminating_checks[0]?.capability_class} read-only
                                  </span>
                                </div>
                              </article>
                            ))}
                          </div>
                        </div>

                        <div className="reasoning-timeline">
                          <h3>Normalized UTC timeline</h3>
                          {reasoningArtifact.timeline.map((event) => (
                            <div key={event.event_id}>
                              <span>{formatTimestamp(event.occurred_at)}</span>
                              <strong>{event.summary}</strong>
                              <small>{event.evidence_references.length} linked evidence</small>
                            </div>
                          ))}
                        </div>

                        <div className="reasoning-stop">
                          <CircleHelp size={16} />
                          <div>
                            <strong>Stop reason</strong>
                            <p>{reasoningArtifact.stop_reason}</p>
                            <span>{reasoningArtifact.summary.safest_next_check}</span>
                          </div>
                        </div>
                        <div className="safety-notice">
                          <ShieldCheck size={16} />
                          <span>{reasoningArtifact.safety_notice}</span>
                        </div>
                      </>
                    )}
                  </section>

                  <section className="workspace-section rca-section" aria-live="polite">
                    <div className="section-heading rca-heading">
                      <div>
                        <p className="eyebrow">ROOT CAUSE ANALYSIS</p>
                        <h2>Governed RCA case</h2>
                      </div>
                      <button
                        className="run-check-button"
                        type="button"
                        disabled={!reasoningArtifact || !selectedAsset || rcaMutation.isPending}
                        onClick={() => {
                          if (reasoningArtifact && selectedAsset) {
                            recommendationMutation.reset();
                            reportMutation.reset();
                            rcaMutation.mutate({
                              targetId: selectedAsset.asset_id,
                              actualBehavior:
                                reasoningArtifact.summary.known[0] ??
                                `Storage health is ${selectedAsset.health}.`,
                            });
                          }
                        }}
                      >
                        {rcaMutation.isPending ? (
                          <RefreshCw className="spin" size={14} />
                        ) : (
                          <FileText size={14} />
                        )}
                        Build RCA case
                      </button>
                    </div>

                    {!rcaCase && !rcaMutation.isPending && !rcaMutation.isError && (
                      <div className="reasoning-empty">
                        <FileText size={21} />
                        <div>
                          <strong>Investigation evidence required</strong>
                          <p>
                            Build a provisional case after the governed reasoning artifact is
                            available. Root cause and service impact remain unconfirmed.
                          </p>
                        </div>
                      </div>
                    )}
                    {rcaMutation.isPending && (
                      <div className="reasoning-empty">
                        <Clock3 size={20} />
                        <div>
                          <strong>Building immutable RCA case</strong>
                          <p>Evidence balance, causal taxonomy, and diagnostics are being checked.</p>
                        </div>
                      </div>
                    )}
                    {rcaMutation.isError && (
                      <div className="reasoning-empty reasoning-error">
                        <AlertTriangle size={20} />
                        <div>
                          <strong>RCA case unavailable</strong>
                          <p>No cause statement is shown when governance checks fail.</p>
                        </div>
                      </div>
                    )}

                    {rcaCase && (
                      <>
                        <div className="rca-summary-grid">
                          <div>
                            <span>Case version</span>
                            <strong>Version {rcaCase.version}</strong>
                            <small>{rcaCase.incident_references[0]?.reference_id}</small>
                          </div>
                          <div>
                            <span>State</span>
                            <strong className={`rca-state ${rcaCase.state}`}>
                              {rcaCase.state}
                            </strong>
                            <small>{rcaCase.severity} severity</small>
                          </div>
                          <div>
                            <span>Owner</span>
                            <strong>{rcaCase.owner}</strong>
                            <small>{rcaCase.target_id}</small>
                          </div>
                          <div>
                            <span>Human review</span>
                            <strong>{rcaCase.human_review.status}</strong>
                            <small>Attributable review required</small>
                          </div>
                        </div>

                        <div className="rca-impact-grid">
                          <div>
                            <h3>Observed symptom</h3>
                            <strong>{rcaCase.symptoms[0]?.statement}</strong>
                            <p>{rcaCase.symptoms[0]?.current_state}</p>
                          </div>
                          <div>
                            <h3>Affected / possible</h3>
                            <strong>{rcaCase.impact_scope.affected_entities.join(", ")}</strong>
                            <p>
                              Possible services: {rcaCase.impact_scope.possibly_affected_services.join(", ")}
                            </p>
                          </div>
                          <div>
                            <h3>Explicitly unaffected</h3>
                            <strong>
                              {rcaCase.impact_scope.explicitly_unaffected_entities.join(", ")}
                            </strong>
                            <p>{rcaCase.impact_scope.limitations[0]}</p>
                          </div>
                        </div>

                        <div className="rca-body-grid">
                          <div className="rca-hypotheses">
                            <h3>Ranked hypotheses</h3>
                            {rcaCase.hypotheses.map((hypothesis) => (
                              <article key={hypothesis.hypothesis_id}>
                                <div className="rca-hypothesis-title">
                                  <span className="rca-rank">#{hypothesis.rank}</span>
                                  <span className="epistemic-type">
                                    {hypothesis.cause_type.replaceAll("_", " ")}
                                  </span>
                                  <span className={`confidence ${hypothesis.confirmation_level}`}>
                                    {hypothesis.confirmation_level.replaceAll("_", " ")}
                                  </span>
                                </div>
                                <strong>{hypothesis.statement}</strong>
                                <p>{hypothesis.mechanism}</p>
                                <small>
                                  {hypothesis.supporting_evidence.length} supporting /{" "}
                                  {hypothesis.contradicting_evidence.length} contradicting /{" "}
                                  {hypothesis.missing_expected_observations.length} missing
                                </small>
                                <div className="rca-sequence">
                                  {hypothesis.expected_sequence.map((step) => (
                                    <span key={step}>{step}</span>
                                  ))}
                                </div>
                              </article>
                            ))}
                          </div>

                          <div className="rca-diagnostics">
                            <h3>Bounded diagnostics</h3>
                            {rcaCase.hypotheses.flatMap((hypothesis) =>
                              hypothesis.diagnostic_steps.map((step) => (
                                <article key={`${hypothesis.hypothesis_id}-${step.step_id}`}>
                                  <div>
                                    <ShieldCheck size={14} />
                                    <span>{step.capability_class}</span>
                                  </div>
                                  <strong>{step.question}</strong>
                                  <p>{step.capability_id}</p>
                                  <small>
                                    {step.timeout_seconds}s timeout · max {step.max_output_records}{" "}
                                    records · no approval
                                  </small>
                                </article>
                              )),
                            )}
                          </div>
                        </div>

                        <div className="rca-gaps-grid">
                          <div>
                            <h3>Evidence gaps</h3>
                            <ul>
                              {rcaCase.evidence_gaps.map((gap) => (
                                <li key={gap}>{gap}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h3>Current blocker</h3>
                            <p>{rcaCase.blocker}</p>
                            <strong>{rcaCase.safest_next_step}</strong>
                          </div>
                        </div>

                        <div className="rca-provisional">
                          <CircleHelp size={17} />
                          <div>
                            <strong>Provisional cause statement</strong>
                            <p>{rcaCase.provisional_statement.statement}</p>
                            <span>
                              {rcaCase.provisional_statement.prevention_or_verification_implication}
                            </span>
                          </div>
                        </div>
                        <div className="safety-notice">
                          <ShieldCheck size={16} />
                          <span>{rcaCase.safety_notice}</span>
                        </div>
                      </>
                    )}
                  </section>

                  <section className="workspace-section recommendation-section" aria-live="polite">
                    <div className="section-heading recommendation-heading">
                      <div>
                        <p className="eyebrow">RECOMMENDATION ENGINE</p>
                        <h2>Operational choices</h2>
                      </div>
                      <button
                        className="run-check-button recommendation-button"
                        type="button"
                        disabled={!rcaCase || recommendationMutation.isPending}
                        onClick={() => {
                          if (rcaCase) {
                            reportMutation.reset();
                            approvalCreateMutation.reset();
                            approvalDecisionMutation.reset();
                            setApprovalRequestId(null);
                            const url = new URL(window.location.href);
                            url.searchParams.delete("approval_request_id");
                            window.history.replaceState({}, "", url);
                            recommendationMutation.mutate({
                              targetId: rcaCase.target_id,
                              caseId: rcaCase.case_id,
                              version: rcaCase.version,
                            });
                          }
                        }}
                      >
                        {recommendationMutation.isPending ? (
                          <RefreshCw className="spin" size={14} />
                        ) : (
                          <Scale size={14} />
                        )}
                        Compare options
                      </button>
                    </div>

                    {!recommendation &&
                      !recommendationMutation.isPending &&
                      !recommendationMutation.isError && (
                        <div className="reasoning-empty">
                          <Scale size={21} />
                          <div>
                            <strong>Governed RCA case required</strong>
                            <p>
                              Compare diagnostic, escalation, deferral, and blocked change-planning
                              choices after the provisional RCA case is available.
                            </p>
                          </div>
                        </div>
                      )}
                    {recommendationMutation.isPending && (
                      <div className="reasoning-empty">
                        <Clock3 size={20} />
                        <div>
                          <strong>Comparing operational choices</strong>
                          <p>Evidence, risk, reversibility, interruption, and policy are being validated.</p>
                        </div>
                      </div>
                    )}
                    {recommendationMutation.isError && (
                      <div className="reasoning-empty reasoning-error">
                        <AlertTriangle size={20} />
                        <div>
                          <strong>Recommendation unavailable</strong>
                          <p>No preferred option is shown when source or governance checks fail.</p>
                        </div>
                      </div>
                    )}

                    {recommendation && (
                      <>
                        <div className="recommendation-summary-grid">
                          <div>
                            <span>Artifact</span>
                            <strong>Version {recommendation.version}</strong>
                            <small>{recommendation.state.replaceAll("_", " ")}</small>
                          </div>
                          <div>
                            <span>Source RCA</span>
                            <strong>Version {recommendation.source_case_version}</strong>
                            <small>{recommendation.source_case_state}</small>
                          </div>
                          <div>
                            <span>Human review</span>
                            <strong>{recommendation.human_review.status}</strong>
                            <small>{recommendation.accountable_audience}</small>
                          </div>
                          <div>
                            <span>Expires</span>
                            <strong>{formatTimestamp(recommendation.expires_at)}</strong>
                            <small>{recommendation.horizon.replaceAll("_", " ")}</small>
                          </div>
                        </div>

                        <div className="preferred-option-banner">
                          <CheckCircle2 size={18} />
                          <div>
                            <span>Preferred for the current decision</span>
                            <strong>
                              {recommendation.options.find(
                                (option) => option.option_id === recommendation.preferred_option_id,
                              )?.title ?? "No option preferred"}
                            </strong>
                            <p>{recommendation.preference_rationale}</p>
                          </div>
                        </div>

                        <div className="recommendation-options">
                          <h3>Compared options</h3>
                          <div>
                            {recommendation.options.map((option) => (
                              <article
                                className={`${option.state} ${option.preference}`}
                                key={option.option_id}
                              >
                                <div className="recommendation-option-head">
                                  <span className="recommendation-category">
                                    {option.category.replaceAll("_", " ")}
                                  </span>
                                  <span className={`recommendation-state ${option.state}`}>
                                    {option.state}
                                  </span>
                                  <span className={`risk-level ${option.overall_risk}`}>
                                    {option.overall_risk} risk
                                  </span>
                                </div>
                                <strong>{option.title}</strong>
                                <p>{option.intended_outcome}</p>
                                <div className="recommendation-option-metrics">
                                  <span>
                                    Evidence <strong>{option.confidence}</strong>
                                  </span>
                                  <span>
                                    Duration{" "}
                                    <strong>
                                      {option.duration.minimum_minutes}-
                                      {option.duration.maximum_minutes} min
                                    </strong>
                                  </span>
                                  <span>
                                    Interruption <strong>{option.interruption.expected_mode}</strong>
                                  </span>
                                </div>
                                <div className="recommendation-plan">
                                  {option.plan_steps.map((step) => (
                                    <div key={step.step_id}>
                                      <span>{step.order}</span>
                                      <p>{step.conceptual_action}</p>
                                      <small>
                                        {step.capability_class} · {step.capability_id ?? "human procedure"}
                                      </small>
                                    </div>
                                  ))}
                                </div>
                                {option.state === "blocked" ? (
                                  <div className="recommendation-exclusions">
                                    <strong>Blocked by policy and readiness</strong>
                                    <ul>
                                      {option.exclusion_reasons.map((reason) => (
                                        <li key={reason}>{reason}</li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : (
                                  <div className="recommendation-readiness">
                                    <span>
                                      Rollback {option.recovery.rollback_feasible ? "credible" : "not established"}
                                    </span>
                                    <span>{option.policy_outcome.replaceAll("_", " ")}</span>
                                  </div>
                                )}
                              </article>
                            ))}
                          </div>
                        </div>

                        <div className="recommendation-comparison">
                          <h3>Visible comparison dimensions</h3>
                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>Dimension</th>
                                  {recommendation.options.map((option) => (
                                    <th key={option.option_id}>{option.category.replaceAll("_", " ")}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {recommendation.comparisons.map((comparison) => (
                                  <tr key={comparison.dimension}>
                                    <td>{comparison.dimension.replaceAll("_", " ")}</td>
                                    {recommendation.options.map((option) => (
                                      <td key={option.option_id}>
                                        {comparison.option_values.find(
                                          ([optionId]) => optionId === option.option_id,
                                        )?.[1] ?? "Unknown"}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <div className="recommendation-policy-grid">
                          <div>
                            <h3>Policy constraints</h3>
                            <ul>
                              {recommendation.policy_constraints.map((constraint) => (
                                <li key={constraint}>{constraint}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h3>Decision boundary</h3>
                            <p>
                              {recommendation.execution_authorized
                                ? "Execution authority present"
                                : "No execution authority"}
                            </p>
                            <strong>Review does not grant RBAC, approval, or runtime authority.</strong>
                          </div>
                        </div>
                        <div className="safety-notice">
                          <ShieldCheck size={16} />
                          <span>{recommendation.safety_notice}</span>
                        </div>
                      </>
                    )}
                  </section>

                  <section className="workspace-section approval-section" aria-live="polite">
                    <div className="section-heading approval-heading">
                      <div>
                        <p className="eyebrow">HUMAN GOVERNANCE</p>
                        <h2>Immutable approval review</h2>
                      </div>
                      <button
                        className="run-check-button approval-submit"
                        type="button"
                        disabled={
                          !recommendation?.preferred_option_id || approvalCreateMutation.isPending
                          || Boolean(approval)
                        }
                        onClick={() => {
                          if (recommendation?.preferred_option_id) {
                            approvalCreateMutation.mutate({
                              targetId: recommendation.target_id,
                              recommendationId: recommendation.recommendation_id,
                              recommendationVersion: recommendation.version,
                              optionId: recommendation.preferred_option_id,
                            });
                          }
                        }}
                      >
                        {approvalCreateMutation.isPending ? (
                          <RefreshCw className="spin" size={14} />
                        ) : (
                          <UserCheck size={14} />
                        )}
                        Submit for human review
                      </button>
                    </div>

                    {!approval &&
                      !approvalQuery.isLoading &&
                      !approvalCreateMutation.isPending &&
                      !approvalQuery.isError &&
                      !approvalCreateMutation.isError && (
                        <div className="reasoning-empty">
                          <UserCheck size={21} />
                          <div>
                            <strong>Governed recommendation required</strong>
                            <p>An exact option is bound to an immutable packet before human review.</p>
                          </div>
                        </div>
                      )}
                    {(approvalQuery.isLoading || approvalCreateMutation.isPending) && (
                      <div className="reasoning-empty">
                        <Clock3 size={20} />
                        <div><strong>Building immutable packet</strong><p>Source versions, evidence, risk, impact, recovery, and expiry are being bound.</p></div>
                      </div>
                    )}
                    {(approvalQuery.isError || approvalCreateMutation.isError) && (
                      <div className="reasoning-empty reasoning-error">
                        <AlertTriangle size={20} />
                        <div><strong>Approval unavailable</strong><p>No review controls are shown when packet validation fails.</p></div>
                      </div>
                    )}

                    {approval && (
                      <>
                        <div className="approval-summary-grid">
                          <div><span>State</span><strong>{approval.state.replaceAll("_", " ")}</strong><small>Version {approval.version}</small></div>
                          <div><span>Requester</span><strong>{approval.packet.requested_by}</strong><small>{approval.packet.purpose}</small></div>
                          <div><span>Risk</span><strong>{approval.packet.overall_risk}</strong><small>{approval.packet.option_confidence} confidence</small></div>
                          <div><span>Expires</span><strong>{formatTimestamp(approval.packet.expires_at)}</strong><small>{approval.packet.canonicalization_version}</small></div>
                        </div>

                        <div className="approval-digest">
                          <ShieldCheck size={17} />
                          <div><span>Canonical packet digest</span><strong>{approval.packet.canonical_digest}</strong></div>
                        </div>

                        <div className="approval-focus">
                          <div><span>Exact option</span><strong>{approval.packet.option_title}</strong><p>{approval.packet.confidence_rationale}</p></div>
                          <div><span>Impact boundary</span><strong>{approval.packet.blast_radius}</strong><p>{approval.packet.impact_confirmed ? "Impact confirmed" : "Impact remains unconfirmed"} · {approval.packet.graph_maturity}</p></div>
                          <div><span>Interruption</span><strong>{approval.packet.interruption_expected_mode}</strong><p>Worst credible: {approval.packet.interruption_worst_credible_mode}</p></div>
                          <div><span>Recovery</span><strong>{approval.packet.rollback_feasible ? "Rollback described" : "Rollback not established"}</strong><p>{approval.packet.recovery_strategy}</p></div>
                        </div>

                        <div className="approval-evidence-grid">
                          <div><h3>Evidence and assumptions</h3><ul>{approval.packet.evidence_summaries.map((item) => <li key={item}>{item}</li>)}{approval.packet.assumptions.map((item) => <li key={item}>Assumption: {item}</li>)}</ul></div>
                          <div><h3>Unknowns and gaps</h3><ul>{[...approval.packet.unknowns, ...approval.packet.impact_gaps, ...approval.packet.recovery_gaps].map((item) => <li key={item}>{item}</li>)}</ul></div>
                        </div>

                        <div className="approval-plan">
                          <h3>Bound ordered plan</h3>
                          {approval.packet.plan_steps.map((step) => (
                            <div key={step.step_id}><span>{step.order}</span><p>{step.conceptual_action}</p><small>{step.capability_class} · {step.stop_condition}</small></div>
                          ))}
                        </div>

                        <div className="approval-review-boundary">
                          <div><strong>{approval.execution_authorized ? "Execution authority present" : "No execution authority"}</strong><p>An approval records a human decision only. It grants no RBAC, connector, or runtime permission.</p></div>
                          {approval.decisions.length > 0 && (
                            <div className="approval-history"><span>Decision history</span>{approval.decisions.map((item) => <p key={item.decision_id}><strong>{item.outcome.replaceAll("_", " ")}</strong> by {item.reviewer_id}: {item.rationale}</p>)}</div>
                          )}
                        </div>

                        {approval.state === "pending" && !canReviewApproval && (
                          <div className="approval-ineligible"><LockKeyhole size={17} /><div><strong>Separated reviewer required</strong><p>The requester, a non-human identity, or development assurance cannot decide this packet.</p></div></div>
                        )}
                        {canReviewApproval && (
                          <div className="approval-controls">
                            <label htmlFor="approval-rationale">Decision rationale</label>
                            <textarea id="approval-rationale" value={approvalRationale} onChange={(event) => setApprovalRationale(event.target.value)} maxLength={1000} placeholder="Record the evidence-based reason for this decision..." />
                            <div>
                              {([
                                ["approve", "Approve", CheckCircle2],
                                ["reject", "Reject", X],
                                ["needs_evidence", "Needs evidence", CircleHelp],
                                ["defer", "Defer", Clock3],
                              ] as const).map(([outcome, label, Icon]) => (
                                <button key={outcome} type="button" disabled={approvalRationale.trim().length < 5 || approvalDecisionMutation.isPending} onClick={() => approvalDecisionMutation.mutate({ requestId: approval.request_id, version: approval.version, outcome, rationale: approvalRationale.trim() })}><Icon size={14} />{label}</button>
                              ))}
                            </div>
                          </div>
                        )}
                        {approvalDecisionMutation.isError && <div className="impact-message impact-error"><AlertTriangle size={18} /> Decision was not recorded; reload the immutable packet before retrying.</div>}
                      </>
                    )}
                  </section>

                  <section className="workspace-section report-section" aria-live="polite">
                    <div className="section-heading report-heading">
                      <div>
                        <p className="eyebrow">TECHNICAL REPORT</p>
                        <h2>Decision report and ITSM handoff</h2>
                      </div>
                      <div className="report-heading-actions">
                        {technicalReport && (
                          <button
                            className="icon-button report-download"
                            type="button"
                            aria-label="Download technical report"
                            title="Download Markdown report"
                            onClick={() =>
                              downloadMarkdown(
                                `atlas-${technicalReport.target_id.split(".").at(-1) ?? "storage"}-decision-report-v${technicalReport.version}.md`,
                                technicalReport.rendered_markdown,
                              )
                            }
                          >
                            <Download size={15} />
                          </button>
                        )}
                        <button
                          className="run-check-button report-button"
                          type="button"
                          disabled={
                            !recommendation ||
                            !incidentReference ||
                            reportMutation.isPending
                          }
                          onClick={() => {
                            if (recommendation && incidentReference) {
                              reportMutation.mutate({
                                targetId: recommendation.target_id,
                                recommendationId: recommendation.recommendation_id,
                                recommendationVersion: recommendation.version,
                                incidentReference,
                              });
                            }
                          }}
                        >
                          {reportMutation.isPending ? (
                            <RefreshCw className="spin" size={14} />
                          ) : (
                            <FileChartColumn size={14} />
                          )}
                          Generate report
                        </button>
                      </div>
                    </div>

                    {!technicalReport &&
                      !reportMutation.isPending &&
                      !reportMutation.isError && (
                        <div className="reasoning-empty">
                          <FileChartColumn size={21} />
                          <div>
                            <strong>Governed recommendation required</strong>
                            <p>
                              Generate a source-bound technical report and a review-only ITSM
                              handoff draft after the option comparison is available.
                            </p>
                          </div>
                        </div>
                      )}
                    {reportMutation.isPending && (
                      <div className="reasoning-empty">
                        <Clock3 size={20} />
                        <div>
                          <strong>Validating report source and evidence</strong>
                          <p>Lineage, classification, redaction, integrity, and audit are being checked.</p>
                        </div>
                      </div>
                    )}
                    {reportMutation.isError && (
                      <div className="reasoning-empty reasoning-error">
                        <AlertTriangle size={20} />
                        <div>
                          <strong>Technical report unavailable</strong>
                          <p>No partial report or ITSM draft is disclosed after a validation failure.</p>
                        </div>
                      </div>
                    )}

                    {technicalReport && (
                      <>
                        <div className="report-summary-grid">
                          <div>
                            <span>Report</span>
                            <strong>Version {technicalReport.version}</strong>
                            <small>{technicalReport.state.replaceAll("_", " ")}</small>
                          </div>
                          <div>
                            <span>Audience</span>
                            <strong>{technicalReport.audience.replaceAll("_", " ")}</strong>
                            <small>{technicalReport.classification}</small>
                          </div>
                          <div>
                            <span>Human review</span>
                            <strong>{technicalReport.review.status}</strong>
                            <small>{technicalReport.owner}</small>
                          </div>
                          <div>
                            <span>Redaction</span>
                            <strong>{technicalReport.redaction_state}</strong>
                            <small>Expires {formatTimestamp(technicalReport.expires_at)}</small>
                          </div>
                        </div>

                        <div className="report-lineage">
                          <FileText size={18} />
                          <div>
                            <span>Immutable source lineage</span>
                            <strong>
                              Recommendation v{technicalReport.source.recommendation_version} · RCA v
                              {technicalReport.source.rca_case_version}
                            </strong>
                            <p>
                              {technicalReport.source.evidence_ids.length} authorized evidence references ·
                              digest {technicalReport.content_digest.slice(0, 16)}…
                            </p>
                          </div>
                        </div>

                        <div className="report-sections">
                          <h3>Structured report sections</h3>
                          <div>
                            {technicalReport.sections.map((section) => (
                              <article key={section.section_id} className={section.state}>
                                <div className="report-section-head">
                                  <strong>{section.title}</strong>
                                  <span>{section.state}</span>
                                </div>
                                <ul>
                                  {section.statements.map((statement) => (
                                    <li key={statement}>{statement}</li>
                                  ))}
                                </ul>
                                {section.evidence_references.length > 0 && (
                                  <div className="report-evidence">
                                    <span>Evidence</span>
                                    {section.evidence_references.map((reference) => (
                                      <code key={reference}>{reference}</code>
                                    ))}
                                  </div>
                                )}
                                {section.limitations.length > 0 && (
                                  <div className="report-limitations">
                                    <strong>Limitations</strong>
                                    <ul>
                                      {section.limitations.map((limitation) => (
                                        <li key={limitation}>{limitation}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </article>
                            ))}
                          </div>
                        </div>

                        {technicalReport.itsm_handoff && (
                          <div className="itsm-handoff">
                            <div>
                              <span>ITSM HANDOFF DRAFT</span>
                              <h3>{technicalReport.itsm_handoff.incident_reference}</h3>
                              <p>{technicalReport.itsm_handoff.generated_content_label}</p>
                            </div>
                            <dl>
                              <div>
                                <dt>Status</dt>
                                <dd>{technicalReport.itsm_handoff.state.replaceAll("_", " ")}</dd>
                              </div>
                              <div>
                                <dt>Operation</dt>
                                <dd>{technicalReport.itsm_handoff.operation.replaceAll("_", " ")}</dd>
                              </div>
                              <div>
                                <dt>External dispatch</dt>
                                <dd>
                                  {technicalReport.itsm_handoff.dispatch_authorized
                                    ? "Authorized"
                                    : "Not authorized"}
                                </dd>
                              </div>
                              <div>
                                <dt>Record mutation</dt>
                                <dd>
                                  {technicalReport.itsm_handoff.external_record_mutated
                                    ? "Recorded"
                                    : "None"}
                                </dd>
                              </div>
                            </dl>
                            <div className="itsm-fields">
                              {technicalReport.itsm_handoff.field_mappings.map((mapping) => (
                                <div key={mapping.field}>
                                  <span>{mapping.field.replaceAll("_", " ")}</span>
                                  <strong>{mapping.value}</strong>
                                </div>
                              ))}
                            </div>
                            <p className="itsm-idempotency">
                              Idempotency {technicalReport.itsm_handoff.idempotency_key.slice(0, 20)}…
                            </p>
                          </div>
                        )}

                        <div className="report-boundary-grid">
                          <div>
                            <h3>Execution boundary</h3>
                            <strong>
                              {technicalReport.execution_authorized
                                ? "Execution authority present"
                                : "No execution authority"}
                            </strong>
                          </div>
                          <div>
                            <h3>External-system boundary</h3>
                            <strong>
                              {technicalReport.external_mutation_authorized
                                ? "External mutation authority present"
                                : "No external mutation authority"}
                            </strong>
                          </div>
                        </div>
                        <div className="safety-notice">
                          <ShieldCheck size={16} />
                          <span>{technicalReport.safety_notice}</span>
                        </div>
                      </>
                    )}
                  </section>

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
              <form
                className="composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  const question = investigationQuestion.trim();
                  if (selectedAsset && question) {
                    rcaMutation.reset();
                    recommendationMutation.reset();
                    reportMutation.reset();
                    investigationMutation.mutate({ targetId: selectedAsset.asset_id, question });
                  }
                }}
              >
                <textarea
                  aria-label="Ask Atlas"
                  placeholder="Ask Atlas to investigate the selected storage system..."
                  rows={2}
                  value={investigationQuestion}
                  onChange={(event) => setInvestigationQuestion(event.target.value)}
                  disabled={!selectedAsset || investigationMutation.isPending}
                />
                <div className="composer-footer">
                  <span>Authorized evidence · 24-hour UTC window · decision support only</span>
                  <button
                    className="send-button"
                    type="submit"
                    aria-label="Start investigation"
                    disabled={
                      !selectedAsset ||
                      !investigationQuestion.trim() ||
                      investigationMutation.isPending
                    }
                  >
                    <Send size={17} />
                  </button>
                </div>
              </form>
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
