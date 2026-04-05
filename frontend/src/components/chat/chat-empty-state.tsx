import { MessageSquare } from "lucide-react";
import { ProductEmptyState } from "@/components/shared/product-empty-state";
import { PRODUCT_SECTION } from "@/lib/product-terminology";

export function ChatEmptyState() {
  return (
    <ProductEmptyState
      icon={MessageSquare}
      title="Выберите диалог"
      description={
        <>
          Создайте новый диалог («+» слева) и задайте вопрос — ответ строится по содержимому проиндексированных документов{" "}
          {PRODUCT_SECTION.workspace.toLowerCase()} с указанием источников.
        </>
      }
    />
  );
}
