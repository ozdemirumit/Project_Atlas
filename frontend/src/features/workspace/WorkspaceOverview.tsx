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

import type { WorkspaceId } from "../shell/workspace";

interface Capability {
  destination: Exclude<WorkspaceId, "Workspace">;
  icon: typeof Activity;
  label: string;
}

interface CapabilityGroup {
  capabilities: Capability[];
  title: string;
}

const capabilityGroups: CapabilityGroup[] = [
  {
    title: "Infrastructure operations",
    capabilities: [
      { label: "Inventory and health", destination: "Health", icon: Activity },
      { label: "Topology and service impact", destination: "Health", icon: GitBranch },
      { label: "Investigation and RCA", destination: "Health", icon: ScanSearch },
      { label: "Recommendations and reports", destination: "Health", icon: FileChartColumn },
    ],
  },
  {
    title: "Connector lifecycle",
    capabilities: [
      { label: "MCP Builder", destination: "Connectors", icon: Blocks },
      { label: "Package trust chain", destination: "Connectors", icon: ShieldCheck },
      { label: "Runtime governance", destination: "Connectors", icon: Network },
    ],
  },
  {
    title: "AI decision support",
    capabilities: [
      { label: "Knowledge indexing", destination: "Connectors", icon: BrainCircuit },
      { label: "Protected model context", destination: "Connectors", icon: Bot },
      { label: "Recommendation review", destination: "Connectors", icon: Workflow },
    ],
  },
  {
    title: "Enterprise controls",
    capabilities: [
      { label: "Identity and access", destination: "Health", icon: KeyRound },
      { label: "Audit and SIEM export", destination: "Health", icon: ShieldCheck },
      { label: "Deployment and bootstrap", destination: "Health", icon: Workflow },
    ],
  },
];

interface WorkspaceOverviewProps {
  onNavigate: (workspace: WorkspaceId) => void;
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
          <strong>13</strong>
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
                  <small>{destination}</small>
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
