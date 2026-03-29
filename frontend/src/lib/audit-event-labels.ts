/**
 * Человекочитаемые подписи для audit event_type (соответствуют backend write_audit_log).
 * Неизвестные типы показываются как есть — не подменяем смысл.
 */

export interface AuditEventPresentation {
  /** Короткий заголовок в UI */
  title: string;
  /** Пояснение для подсказки / описания */
  hint?: string;
}

const LABELS: Record<string, AuditEventPresentation> = {
  "quota.denied": {
    title: "Превышение квоты",
    hint: "API отклонил операцию по месячному лимиту (запросы, токены, загрузка, документы и т.д.).",
  },
  "workspace.access_denied": {
    title: "Доступ к workspace отклонён",
    hint: "Попытка обратиться к чужому или недоступному рабочему пространству (cross-workspace).",
  },
  "document.deleted": {
    title: "Документ удалён",
    hint: "Пользователь удалил документ в текущем workspace.",
  },
  "ingestion.failed": {
    title: "Ошибка индексации (job)",
    hint: "Фоновая задача индексации завершилась с ошибкой.",
  },
  "auth.login_failed": {
    title: "Неудачный вход",
    hint: "Неверные учётные данные; пароль в журнал не пишется.",
  },
  "auth.password_reset_requested": {
    title: "Запрошен сброс пароля",
    hint: "Пользователь инициировал восстановление доступа по email.",
  },
  "auth.password_reset_completed": {
    title: "Пароль сменён после сброса",
    hint: "Успешное завершение потока сброса пароля.",
  },
  "auth.login": {
    title: "Успешный вход",
    hint: "Сессия создана, выданы токены.",
  },
  "auth.register": {
    title: "Регистрация",
    hint: "Создан новый пользователь.",
  },
  "auth.logout": {
    title: "Выход",
    hint: "Завершение текущей сессии.",
  },
  "auth.logout_all": {
    title: "Выход со всех устройств",
    hint: "Отозваны все refresh-сессии.",
  },
  "auth.refresh_reuse_detected": {
    title: "Повторное использование refresh",
    hint: "Подозрение на reuse токена — сессии сброшены.",
  },
  "auth.email_verified": {
    title: "Email подтверждён",
    hint: "Верификация адреса завершена.",
  },
  /** Зарезервировано под будущий эмит backend — в логах пока может не встречаться */
  "member.role_changed": {
    title: "Смена роли участника",
    hint: "Если появится в API: изменение роли в workspace (owner / admin / member / viewer).",
  },
};

/** Варианты для серверного фильтра (exact match) — плюс пустая строка = все */
export const AUDIT_SERVER_FILTER_PRESETS: { value: string; label: string }[] = [
  { value: "", label: "Все типы (без фильтра на сервере)" },
  { value: "quota.denied", label: "Превышение квоты (quota.denied)" },
  { value: "workspace.access_denied", label: "Доступ к workspace отклонён" },
  { value: "document.deleted", label: "Документ удалён" },
  { value: "ingestion.failed", label: "Ошибка индексации" },
  { value: "auth.login_failed", label: "Неудачный вход" },
  { value: "auth.password_reset_requested", label: "Запрос сброса пароля" },
  { value: "auth.password_reset_completed", label: "Пароль сменён" },
  { value: "auth.login", label: "Успешный вход" },
  { value: "auth.register", label: "Регистрация" },
  { value: "auth.logout", label: "Выход" },
  { value: "auth.logout_all", label: "Выход со всех устройств" },
  { value: "auth.refresh_reuse_detected", label: "Reuse refresh-токена" },
  { value: "auth.email_verified", label: "Подтверждение email" },
];

/** Алиасы для будущих имён в API (пока backend может не эмитить). */
const NORMALIZED_ALIASES: Record<string, string> = {
  "workspace.member_role_changed": "member.role_changed",
  "member.role_updated": "member.role_changed",
};

export function getAuditEventPresentation(eventType: string): AuditEventPresentation {
  const key = NORMALIZED_ALIASES[eventType] ?? eventType;
  const p = LABELS[key];
  if (p) return p;
  return {
    title: eventType,
    hint: "Тип события пока не описан в UI — смотрите сырое значение и metadata.",
  };
}

export function targetTypeHint(targetType: string | null | undefined): string | undefined {
  if (!targetType) return undefined;
  const t = targetType.toLowerCase();
  if (t === "workspace") return "Объект: рабочее пространство";
  if (t === "document") return "Объект: документ";
  if (t === "user") return "Объект: пользователь";
  return `Тип объекта: ${targetType}`;
}
