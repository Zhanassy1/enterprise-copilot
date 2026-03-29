/** Нормализация ролей workspace из API (owner / admin / member / viewer). */

export function normalizeWorkspaceRole(role: string | null | undefined): string {
  return (role ?? "").trim().toLowerCase();
}

/** Загрузка, удаление документов, создание чат-сессий и отправка сообщений (WorkspaceWriteAccess в API). */
export function canWriteInWorkspace(role: string | null | undefined): boolean {
  const r = normalizeWorkspaceRole(role);
  return r === "owner" || r === "admin" || r === "member";
}

/** Расширенный аудит, часть административных сценариев. */
export function isOwnerOrAdmin(role: string | null | undefined): boolean {
  const r = normalizeWorkspaceRole(role);
  return r === "owner" || r === "admin";
}
