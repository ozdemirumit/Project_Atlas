import { Blocks, Boxes, BrainCircuit, ShieldCheck, type LucideIcon } from "lucide-react";

import type { ConnectorViewId } from "../shell/workspace";

interface ConnectorViewDescriptor {
  id: ConnectorViewId;
  label: string;
  icon: LucideIcon;
}

const connectorViewDescriptors: readonly ConnectorViewDescriptor[] = [
  { id: "inventory", label: "Inventory", icon: Boxes },
  { id: "builder", label: "Builder", icon: Blocks },
  { id: "runtime", label: "Runtime", icon: ShieldCheck },
  { id: "knowledge", label: "Knowledge", icon: BrainCircuit },
] as const;

export function ConnectorWorkspaceNavigation({
  activeView,
  onNavigate,
}: {
  activeView: ConnectorViewId;
  onNavigate: (view: ConnectorViewId) => void;
}) {
  const navigateFromKeyboard = (index: number, key: string) => {
    let nextIndex: number | null = null;
    if (key === "ArrowRight") nextIndex = (index + 1) % connectorViewDescriptors.length;
    if (key === "ArrowLeft") {
      nextIndex =
        (index - 1 + connectorViewDescriptors.length) % connectorViewDescriptors.length;
    }
    if (key === "Home") nextIndex = 0;
    if (key === "End") nextIndex = connectorViewDescriptors.length - 1;
    if (nextIndex === null) return false;

    const nextView = connectorViewDescriptors[nextIndex]!;
    document.getElementById(`connector-view-tab-${nextView.id}`)?.focus();
    onNavigate(nextView.id);
    return true;
  };

  return (
    <nav className="connector-workspace-navigation" aria-label="Connector task views">
      <div className="connector-workspace-tabs" role="tablist">
        {connectorViewDescriptors.map(({ id, icon: Icon, label }, index) => (
          <button
            key={id}
            id={`connector-view-tab-${id}`}
            type="button"
            role="tab"
            aria-selected={activeView === id}
            tabIndex={activeView === id ? 0 : -1}
            onClick={() => onNavigate(id)}
            onKeyDown={(event) => {
              if (navigateFromKeyboard(index, event.key)) event.preventDefault();
            }}
          >
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
