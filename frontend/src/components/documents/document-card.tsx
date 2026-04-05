"use client";

import Link from "next/link";
import { FileIcon } from "@/components/shared/file-icon";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fileTypeLabel, formatDate } from "@/lib/utils";
import { BookOpen, Trash2 } from "lucide-react";
import type { DocumentOut } from "@/lib/api-client";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { workspaceAppHref } from "@/lib/workspace-path";
import { documentStatusLabel, pipelineStatusLabel } from "@/lib/product-terminology";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface DocumentCardProps {
  doc: DocumentOut;
  onSummary: (id: string) => void;
  onDelete: (id: string) => void;
  /** false для роли «наблюдатель»: удаление и загрузка запрещены API */
  canMutate?: boolean;
}

export function DocumentCard({ doc, onSummary, onDelete, canMutate = true }: DocumentCardProps) {
  const { currentWorkspace } = useWorkspace();
  const jobsHref = currentWorkspace?.slug ? workspaceAppHref(currentWorkspace.slug, "/jobs") : "/jobs";
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="flex items-start gap-4 p-5">
        <FileIcon type={fileTypeLabel(doc.filename)} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{doc.filename}</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{formatDate(doc.created_at)}</span>
            {doc.status && (
              <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-foreground/90" title={doc.status}>
                {documentStatusLabel(doc.status)}
              </span>
            )}
            {doc.ingestion_job_status ? (
              <Link
                href={jobsHref}
                className="text-[10px] text-primary underline-offset-2 hover:underline"
                title={`Статус job: ${doc.ingestion_job_status}`}
              >
                {pipelineStatusLabel(doc.ingestion_job_status)}
              </Link>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button
            variant="ghost"
            size="icon"
            title="Краткое содержание"
            onClick={() => onSummary(doc.id)}
          >
            <BookOpen className="h-4 w-4" />
          </Button>
          {canMutate ? (
            <Button variant="ghost" size="icon" title="Удалить" onClick={() => onDelete(doc.id)}>
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className="inline-flex h-10 w-10 cursor-not-allowed items-center justify-center rounded-xl text-muted-foreground opacity-60"
                  tabIndex={0}
                  aria-label="Удаление недоступно"
                >
                  <Trash2 className="h-4 w-4" />
                </span>
              </TooltipTrigger>
              <TooltipContent side="left">Только просмотр: нет права на изменение</TooltipContent>
            </Tooltip>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
