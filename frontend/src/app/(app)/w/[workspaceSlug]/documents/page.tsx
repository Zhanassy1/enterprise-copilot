"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { useDocuments } from "@/hooks/use-documents";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { toErrorMessage, type DocumentOut } from "@/lib/api-client";
import { PageHeader } from "@/components/shared/page-header";
import { DocumentCard } from "@/components/documents/document-card";
import { UploadDialog } from "@/components/documents/upload-dialog";
import { SummaryDialog } from "@/components/documents/summary-dialog";
import { DeleteConfirmDialog } from "@/components/documents/delete-confirm-dialog";
import { DocumentEmptyState } from "@/components/documents/document-empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { WorkspaceProductContext } from "@/components/workspace/workspace-product-context";
import { canUploadDocuments } from "@/lib/workspace-role";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QuotaLimitCtaBanner } from "@/components/billing/quota-limit-cta";
import { isQuotaOrLimitError } from "@/lib/quota-error";

export default function DocumentsPage() {
  const { currentWorkspace } = useWorkspace();
  const canMutate = canUploadDocuments(currentWorkspace?.role);
  const { documents, loading, error, uploadDocument, deleteDocument, getSummary, refresh } =
    useDocuments();

  const [quotaCta, setQuotaCta] = useState(false);
  const wrappedUpload = useCallback(
    async (file: File) => {
      try {
        await uploadDocument(file);
      } catch (e) {
        if (isQuotaOrLimitError(e)) setQuotaCta(true);
        throw e;
      }
    },
    [uploadDocument]
  );

  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryText, setSummaryText] = useState<string | null>(null);
  const [summaryFilename, setSummaryFilename] = useState("");

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentOut | null>(null);

  const handleSummary = async (id: string) => {
    const doc = documents.find((d) => d.id === id);
    if (!doc) return;
    setSummaryFilename(doc.filename);
    setSummaryText(null);
    setSummaryOpen(true);
    setSummaryLoading(true);
    try {
      const result = await getSummary(id);
      setSummaryText(result.summary);
    } catch (err) {
      toast.error(toErrorMessage(err));
      setSummaryOpen(false);
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleDeleteClick = (id: string) => {
    const doc = documents.find((d) => d.id === id);
    if (!doc) return;
    setDeleteTarget(doc);
    setDeleteOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteDocument(deleteTarget.id);
      toast.success(`«${deleteTarget.filename}» удалён`);
    } catch (err) {
      toast.error(toErrorMessage(err));
    } finally {
      setDeleteOpen(false);
      setDeleteTarget(null);
    }
  };

  return (
    <TooltipProvider delayDuration={300}>
      <PageHeader
        title="Документы"
        description="Каталог файлов текущего рабочего пространства: загрузка, статусы индексации, краткое содержание."
        action={
          <UploadDialog
            onUpload={wrappedUpload}
            disabled={!canMutate}
            disabledReason="У наблюдателя (viewer) нет права загрузки в этом workspace — только просмотр каталога и действий без изменения данных."
          />
        }
      />

      <WorkspaceProductContext
        className="mt-4"
        area="каталог и операции с файлами ниже относятся к этому рабочему пространству"
        viewerDetail="Загрузка и удаление документов отключены в интерфейсе. Краткое содержание по уже проиндексированным файлам можно открыть, если политика API разрешает чтение."
      />

      {error ? (
        <div className="mt-4">
          <ProductErrorBanner message={error} onRetry={() => void refresh()} retryLabel="Обновить список" />
        </div>
      ) : null}

      <QuotaLimitCtaBanner
        workspaceSlug={currentWorkspace?.slug}
        role={currentWorkspace?.role}
        show={quotaCta}
        className="mt-4"
      />

      {loading ? (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px] rounded-2xl" />
          ))}
        </div>
        ) : documents.length === 0 ? (
        <DocumentEmptyState canUpload={canMutate} workspaceSlug={currentWorkspace?.slug} />
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              onSummary={handleSummary}
              onDelete={handleDeleteClick}
              canMutate={canMutate}
            />
          ))}
        </div>
      )}

      <SummaryDialog
        open={summaryOpen}
        onOpenChange={setSummaryOpen}
        filename={summaryFilename}
        summary={summaryText}
        loading={summaryLoading}
      />
      <DeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        filename={deleteTarget?.filename ?? ""}
        onConfirm={handleDeleteConfirm}
      />
    </TooltipProvider>
  );
}
