import { FileText } from "lucide-react";
import Link from "next/link";
import { ProductEmptyState } from "@/components/shared/product-empty-state";
import { PRODUCT_SECTION } from "@/lib/product-terminology";
import { workspaceAppHref } from "@/lib/workspace-path";

type Props = {
  canUpload?: boolean;
  workspaceSlug?: string | null;
};

export function DocumentEmptyState({ canUpload = true, workspaceSlug }: Props) {
  return (
    <ProductEmptyState
      icon={FileText}
      title="Нет документов"
      description={
        canUpload ? (
          <>
            Загрузите первый документ — индексация выполнится в фоне; статус виден на карточке и в разделе «
            {PRODUCT_SECTION.ingestionQueue}». Форматы: PDF, DOCX, TXT.
          </>
        ) : (
          <>
            В этом {PRODUCT_SECTION.workspace.toLowerCase()} пока нет файлов. У роли «наблюдатель» нет права загрузки —
            попросите участника, администратора или владельца добавить документы.
          </>
        )
      }
    >
      {!canUpload && workspaceSlug ? (
        <Link href={workspaceAppHref(workspaceSlug, "/jobs")} className="text-sm text-primary underline-offset-2 hover:underline">
          К {PRODUCT_SECTION.ingestionQueue.toLowerCase()}
        </Link>
      ) : null}
    </ProductEmptyState>
  );
}
