const workspaceKey = "ec_workspace_id";

export function getWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(workspaceKey);
}

export function setWorkspaceId(id: string): void {
  localStorage.setItem(workspaceKey, id);
}

export function clearWorkspaceId(): void {
  localStorage.removeItem(workspaceKey);
}
