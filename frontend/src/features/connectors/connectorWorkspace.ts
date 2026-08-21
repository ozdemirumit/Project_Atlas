import { Blocks, Boxes, BrainCircuit, ShieldCheck, type LucideIcon } from "lucide-react";

import type { ConnectorViewId } from "../shell/workspace";

export interface ConnectorViewDescriptor {
  id: ConnectorViewId;
  label: string;
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

export const connectorViewDescriptors: readonly ConnectorViewDescriptor[] = [
  {
    id: "inventory",
    label: "Installed MCPs",
    eyebrow: "MCP LIFECYCLE",
    title: "Installed MCP management",
    description: "Add disabled connector instances or retire unused records with history preserved.",
    icon: Boxes,
  },
  {
    id: "builder",
    label: "Builder",
    eyebrow: "MCP BUILDER",
    title: "Governed connector analysis",
    description: "Quarantined OpenAPI evidence review for read-only connector candidates.",
    icon: Blocks,
  },
  {
    id: "runtime",
    label: "Runtime",
    eyebrow: "RUNTIME GOVERNANCE",
    title: "Connector runtime evidence",
    description: "Review bounded trust, configuration, session, and invocation evidence.",
    icon: ShieldCheck,
  },
  {
    id: "knowledge",
    label: "Knowledge",
    eyebrow: "KNOWLEDGE GOVERNANCE",
    title: "Connector knowledge evidence",
    description: "Review governed retrieval, model context, and recommendation evidence.",
    icon: BrainCircuit,
  },
] as const;

export function connectorViewDescriptor(view: ConnectorViewId): ConnectorViewDescriptor {
  return (
    connectorViewDescriptors.find((candidate) => candidate.id === view) ??
    connectorViewDescriptors[0]!
  );
}
