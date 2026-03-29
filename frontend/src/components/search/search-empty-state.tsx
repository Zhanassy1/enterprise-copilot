import { Search } from "lucide-react";

export function SearchEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <Search className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium">Поиск по документам</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        Введите запрос — будут показаны релевантные фрагменты из проиндексированных файлов текущего рабочего пространства и
        краткий ответ с опорой на источники.
      </p>
    </div>
  );
}
