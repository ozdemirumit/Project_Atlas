export const workspaceIds = ["Workspace", "Health", "Connectors"] as const;
export const healthViewIds = ["overview", "investigate", "deployments", "governance"] as const;

export type WorkspaceId = (typeof workspaceIds)[number];
export type HealthViewId = (typeof healthViewIds)[number];

function hashSegments(hash: string): string[] {
  return hash
    .replace(/^#\/?/, "")
    .toLowerCase()
    .split("/")
    .filter(Boolean);
}

export function isKnownWorkspaceHash(hash: string): boolean {
  const [workspace, view, ...remainder] = hashSegments(hash);
  if (remainder.length > 0) return false;
  if (workspace === "health" && view) {
    return healthViewIds.some((candidate) => candidate === view);
  }
  return !view && workspaceIds.some((candidate) => candidate.toLowerCase() === workspace);
}

export function workspaceFromHash(hash: string): WorkspaceId {
  const [candidate] = hashSegments(hash);
  return workspaceIds.find((workspace) => workspace.toLowerCase() === candidate) ?? "Workspace";
}

export function workspaceHash(workspace: WorkspaceId): string {
  return workspace === "Health" ? healthViewHash("overview") : `#/${workspace.toLowerCase()}`;
}

export function healthViewFromHash(hash: string): HealthViewId {
  const [workspace, view] = hashSegments(hash);
  if (workspace !== "health") return "overview";
  return healthViewIds.find((candidate) => candidate === view) ?? "overview";
}

export function healthViewHash(view: HealthViewId): string {
  return `#/health/${view}`;
}
