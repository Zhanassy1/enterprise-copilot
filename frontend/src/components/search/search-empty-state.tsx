import { Search } from "lucide-react";
import { ProductEmptyState } from "@/components/shared/product-empty-state";
import { PRODUCT_SECTION } from "@/lib/product-terminology";

export function SearchEmptyState() {
  return (
    <ProductEmptyState
      icon={Search}
      title="Поиск по документам"
      description={
        <>
          Введите запрос — будут показаны релевантные фрагменты из проиндексированных файлов текущего{" "}
          {PRODUCT_SECTION.workspace.toLowerCase()} и краткий ответ с опорой на источники. Запросы учитываются в месячной
          квоте плана.
        </>
      }
    />
  );
}
