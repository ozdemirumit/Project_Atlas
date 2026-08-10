export const workspaceIds = ["Workspace", "Health", "Connectors"] as const;

export type WorkspaceId = (typeof workspaceIds)[number];

export function isKnownWorkspaceHash(hash: string): boolean {
  const candidate = hash.replace(/^#\/?/, "").toLowerCase();
  return workspaceIds.some((workspace) => workspace.toLowerCase() === candidate);
}

export function workspaceFromHash(hash: string): WorkspaceId {
  const candidate = hash.replace(/^#\/?/, "").toLowerCase();
  return workspaceIds.find((workspace) => workspace.toLowerCase() === candidate) ?? "Workspace";
}

export function workspaceHash(workspace: WorkspaceId): string {
  return `#/${workspace.toLowerCase()}`;
}
