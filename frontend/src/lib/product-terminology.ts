/** Единая продуктовая терминология (не dev-slang). */

export function workspaceRoleLabel(role: string): string {
  const r = (role || "").toLowerCase();
  if (r === "owner") return "Владелец";
  if (r === "admin") return "Администратор";
  if (r === "member") return "Участник";
  if (r === "viewer") return "Наблюдатель";
  return role;
}

export function documentStatusLabel(status: string): string {
  const s = (status || "").toLowerCase();
  const m: Record<string, string> = {
    queued: "В очереди",
    processing: "Обработка",
    ready: "Готово",
    failed: "Ошибка",
    deleted: "Удалён",
  };
  return m[s] ?? status;
}

export function ingestionJobStatusLabel(status: string): string {
  const s = (status || "").toLowerCase();
  const m: Record<string, string> = {
    queued: "В очереди",
    processing: "Индексация",
    retrying: "Повторная попытка",
    ready: "Готово",
    failed: "Ошибка",
  };
  return m[s] ?? status;
}
