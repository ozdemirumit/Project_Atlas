import type { HealthViewId } from "../shell/workspace";
import { healthViewDescriptors } from "./healthWorkspace";

interface HealthWorkspaceNavigationProps {
  activeView: HealthViewId;
  onNavigate: (view: HealthViewId) => void;
}

export function HealthWorkspaceNavigation({
  activeView,
  onNavigate,
}: HealthWorkspaceNavigationProps) {
  const navigateFromKeyboard = (index: number, key: string) => {
    let nextIndex: number | null = null;
    if (key === "ArrowRight") nextIndex = (index + 1) % healthViewDescriptors.length;
    if (key === "ArrowLeft") {
      nextIndex = (index - 1 + healthViewDescriptors.length) % healthViewDescriptors.length;
    }
    if (key === "Home") nextIndex = 0;
    if (key === "End") nextIndex = healthViewDescriptors.length - 1;
    if (nextIndex === null) return false;

    const nextView = healthViewDescriptors[nextIndex]!;
    document.getElementById(`health-view-tab-${nextView.id}`)?.focus();
    onNavigate(nextView.id);
    return true;
  };

  return (
    <nav className="health-workspace-navigation" aria-label="Health task views">
      <div className="health-workspace-tabs" role="tablist">
        {healthViewDescriptors.map(({ id, icon: Icon, label }, index) => (
          <button
            key={id}
            id={`health-view-tab-${id}`}
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
