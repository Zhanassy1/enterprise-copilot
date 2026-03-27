"use client";

import { FileIcon } from "@/components/shared/file-icon";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fileTypeLabel, formatDate } from "@/lib/utils";
import { BookOpen, Trash2 } from "lucide-react";
import type { DocumentOut } from "@/lib/api-client";

interface DocumentCardProps {
  doc: DocumentOut;
  onSummary: (id: string) => void;
  onDelete: (id: string) => void;
}

export function DocumentCard({ doc, onSummary, onDelete }: DocumentCardProps) {
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="flex items-start gap-4 p-5">
        <FileIcon type={fileTypeLabel(doc.filename)} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{doc.filename}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatDate(doc.created_at)}
          </p>
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
          <Button
            variant="ghost"
            size="icon"
            title="Удалить"
            onClick={() => onDelete(doc.id)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
