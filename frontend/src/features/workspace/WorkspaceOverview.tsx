import {
  Activity,
  ArrowRight,
  Blocks,
  Bot,
  BrainCircuit,
  FileChartColumn,
  GitBranch,
  KeyRound,
  Network,
  ScanSearch,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import type { WorkspaceCapabilityDestination } from "../shell/workspace";

interface Capability {
  destination: WorkspaceCapabilityDestination;
  icon: typeof Activity;
  label: string;
}

interface CapabilityGroup {
  capabilities: Capability[];
  title: string;
}

const capabilityGroups: CapabilityGroup[] = [
  {
    title: "Operational planning",
    capabilities: [
      {
        label: "Workflow planning",
        destination: { workspace: "Workspace", view: "workflows" },
        icon: Workflow,
      },
    ],
  },
  {
    title: "Infrastructure operations",
    capabilities: [
      { label: "Inventory and health", destination: { workspace: "Health", view: "overview" }, icon: Activity },
      { label: "Topology and service impact", destination: { workspace: "Health", view: "overview" }, icon: GitBranch },
      { label: "Investigation and RCA", destination: { workspace: "Health", view: "investigate" }, icon: ScanSearch },
      { label: "Recommendations and reports", destination: { workspace: "Health", view: "investigate" }, icon: FileChartColumn },
    ],
  },
  {
    title: "Connector lifecycle",
    capabilities: [
      { label: "MCP Builder", destination: { workspace: "Connectors", view: "builder" }, icon: Blocks },
      { label: "Package trust chain", destination: { workspace: "Connectors", view: "builder" }, icon: ShieldCheck },
      { label: "Runtime governance", destination: { workspace: "Connectors", view: "runtime" }, icon: Network },
    ],
  },
  {
    title: "AI decision support",
    capabilities: [
      { label: "Knowledge indexing", destination: { workspace: "Connectors", view: "knowledge" }, icon: BrainCircuit },
      { label: "Protected model context", destination: { workspace: "Connectors", view: "knowledge" }, icon: Bot },
      { label: "Recommendation review", destination: { workspace: "Connectors", view: "knowledge" }, icon: Workflow },
    ],
  },
  {
    title: "Enterprise controls",
    capabilities: [
      { label: "Identity and access", destination: { workspace: "Health", view: "governance" }, icon: KeyRound },
      { label: "Audit and SIEM export", destination: { workspace: "Health", view: "governance" }, icon: ShieldCheck },
      { label: "Deployment and bootstrap", destination: { workspace: "Health", view: "deployments" }, icon: Workflow },
    ],
  },
];

interface WorkspaceOverviewProps {
  onNavigate: (destination: WorkspaceCapabilityDestination) => void;
}

function destinationLabel(destination: WorkspaceCapabilityDestination): string {
  const view = destination.view.charAt(0).toUpperCase() + destination.view.slice(1);
  return `${destination.workspace} / ${view}`;
}

export function WorkspaceOverview({ onNavigate }: WorkspaceOverviewProps) {
  return (
    <div className="workspace-overview">
      <div className="workspace-overview-summary" aria-label="Workspace coverage">
        <div>
          <strong>4</strong>
          <span>operational domains</span>
        </div>
        <div>
          <strong>14</strong>
          <span>available capabilities</span>
        </div>
        <div>
          <strong>3</strong>
          <span>active workspaces</span>
        </div>
      </div>

      <div className="workspace-capability-groups">
        {capabilityGroups.map((group) => (
          <section className="workspace-capability-group" key={group.title}>
            <div className="workspace-capability-heading">
              <h2>{group.title}</h2>
              <span>{group.capabilities.length}</span>
            </div>
            <div className="workspace-capability-list">
              {group.capabilities.map(({ destination, icon: Icon, label }) => (
                <button
                  className="workspace-capability"
                  key={label}
                  onClick={() => onNavigate(destination)}
                  type="button"
                >
                  <Icon size={18} strokeWidth={1.8} />
                  <span>{label}</span>
                  <small>{destinationLabel(destination)}</small>
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
