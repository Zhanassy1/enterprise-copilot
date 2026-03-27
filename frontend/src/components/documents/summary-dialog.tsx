"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2 } from "lucide-react";

interface SummaryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  filename: string;
  summary: string | null;
  loading: boolean;
}

export function SummaryDialog({
  open,
  onOpenChange,
  filename,
  summary,
  loading,
}: SummaryDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Краткое содержание</DialogTitle>
          <DialogDescription className="truncate">{filename}</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ScrollArea className="max-h-[60vh]">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {summary || "Нет данных"}
            </p>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
