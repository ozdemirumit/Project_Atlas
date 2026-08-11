import { Activity, PackageCheck, Search, ShieldCheck, type LucideIcon } from "lucide-react";

import type { HealthViewId } from "../shell/workspace";

export interface HealthViewDescriptor {
  id: HealthViewId;
  label: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

export const healthViewDescriptors: readonly HealthViewDescriptor[] = [
  {
    id: "overview",
    label: "Overview",
    title: "Health overview",
    description: "Evidence-linked inventory, findings, impact, and scheduled checks.",
    icon: Activity,
  },
  {
    id: "investigate",
    label: "Investigate",
    title: "Investigate infrastructure",
    description: "Evidence-bound analysis, root cause, recommendations, and review.",
    icon: Search,
  },
  {
    id: "deployments",
    label: "Deployments",
    title: "Deployment readiness",
    description: "Release, configuration, bootstrap, and checkpoint coordination.",
    icon: PackageCheck,
  },
  {
    id: "governance",
    label: "Governance",
    title: "Operational governance",
    description: "Human review, access, audit, and security delivery controls.",
    icon: ShieldCheck,
  },
] as const;

export function healthViewDescriptor(view: HealthViewId): HealthViewDescriptor {
  return (
    healthViewDescriptors.find((candidate) => candidate.id === view) ??
    healthViewDescriptors[0]!
  );
}
