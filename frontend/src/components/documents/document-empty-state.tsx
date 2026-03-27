import { FileText } from "lucide-react";

export function DocumentEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <FileText className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium">Нет документов</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Загрузите первый документ, чтобы начать работу. Поддерживаются PDF, DOCX
        и TXT файлы.
      </p>
    </div>
  );
}
