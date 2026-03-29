import { FileText } from "lucide-react";

export function DocumentEmptyState({ canUpload = true }: { canUpload?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <FileText className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium">Нет документов</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        {canUpload ? (
          <>
            Загрузите первый документ — индексация выполнится в фоне; статус виден на карточке и в «Очереди обработки».
            Форматы: PDF, DOCX, TXT.
          </>
        ) : (
          <>
            В этом рабочем пространстве (workspace) пока нет файлов. У роли «наблюдатель» нет права загрузки — попросите
            участника, администратора или владельца добавить документы.
          </>
        )}
      </p>
    </div>
  );
}
