import { MessageSquare } from "lucide-react";

export function ChatEmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <MessageSquare className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium">Начните диалог</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Выберите существующий чат или создайте новый, чтобы задать вопросы по
        вашим документам.
      </p>
    </div>
  );
}
