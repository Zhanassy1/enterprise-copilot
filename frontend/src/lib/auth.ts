import { clearWorkspaceId } from "./workspace";

const TOKEN_KEY = "ec_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  clearWorkspaceId();
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
