/** Единая продуктовая терминология (не dev-slang). */

import { PIPELINE_JOB_STATUSES, type PipelineJobStatus } from "@/lib/ingestion-statuses";

/** Название раздела очереди в UI (сайдбар / заголовок). */
export const PRODUCT_SECTION = {
  workspace: "Рабочее пространство",
  ingestionQueue: "Очередь обработки",
  ingestionJob: "Задача индексации",
  planAndQuotas: "План и лимиты",
  team: "Команда и доступ",
} as const;

export function workspaceRoleLabel(role: string): string {
  const r = (role || "").toLowerCase();
  if (r === "owner") return "Владелец";
  if (r === "admin") return "Администратор";
  if (r === "member") return "Участник";
  if (r === "viewer") return "Наблюдатель";
  return role;
}

const PIPELINE_LABELS: Record<PipelineJobStatus, string> = {
  queued: "В очереди",
  processing: "Индексация",
  retrying: "Повторная попытка",
  ready: "Готово",
  failed: "Ошибка",
};

/**
 * Единые подписи фаз пайплайна для документа и для job (тот же API-словарь статусов).
 */
function isPipelineJobStatus(s: string): s is PipelineJobStatus {
  return (PIPELINE_JOB_STATUSES as readonly string[]).includes(s);
}

export function pipelineStatusLabel(status: string): string {
  const s = (status || "").toLowerCase();
  if (isPipelineJobStatus(s)) return PIPELINE_LABELS[s];
  if (s === "deleted") return "Удалён";
  return status;
}

/** Статус строки в каталоге документов (включая удалён soft-delete, если отражён в поле status). */
export function documentStatusLabel(status: string): string {
  return pipelineStatusLabel(status);
}

/** @deprecated используйте pipelineStatusLabel — подписи совпадают */
export function ingestionJobStatusLabel(status: string): string {
  return pipelineStatusLabel(status);
}
