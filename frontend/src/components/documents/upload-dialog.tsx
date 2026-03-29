"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import { toErrorMessage } from "@/lib/api-client";

interface UploadDialogProps {
  onUpload: (file: File) => Promise<unknown>;
  /** Для роли viewer: кнопка без диалога, с подсказкой (API запретит upload). */
  disabled?: boolean;
  disabledReason?: string;
}

export function UploadDialog({ onUpload, disabled, disabledReason }: UploadDialogProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        await onUpload(file);
        toast.success(`Файл «${file.name}» загружен`);
        setOpen(false);
      } catch (err) {
        toast.error(toErrorMessage(err));
      } finally {
        setUploading(false);
      }
    },
    [onUpload]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  if (disabled) {
    return (
      <div className="flex max-w-xs flex-col items-end gap-1 text-right">
        <Button type="button" disabled title={disabledReason ?? "Загрузка недоступна для вашей роли"}>
          <Upload className="h-4 w-4" />
          Загрузить
        </Button>
        {disabledReason ? (
          <p className="text-xs text-muted-foreground">{disabledReason}</p>
        ) : null}
      </div>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Upload className="h-4 w-4" />
          Загрузить
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Загрузка документа</DialogTitle>
          <DialogDescription>
            Поддерживаются PDF, DOCX и TXT файлы до 25 МБ
          </DialogDescription>
        </DialogHeader>
        <div
          className={`flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-colors ${
            dragActive
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50"
          }`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
        >
          {uploading ? (
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          ) : (
            <>
              <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Перетащите файл сюда или нажмите для выбора
              </p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
