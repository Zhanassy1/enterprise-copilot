import { MessageSquare } from "lucide-react";

export function ChatEmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <MessageSquare className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium">Выберите диалог</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Создайте новый диалог («+» слева) и задайте вопрос — ответ строится по содержимому проиндексированных документов с
        указанием источников.
      </p>
    </div>
  );
}
