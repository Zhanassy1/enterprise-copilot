"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ProductErrorBannerProps {
  message: string;
  className?: string;
  onRetry?: () => void;
  retryLabel?: string;
  onDismiss?: () => void;
}

export function ProductErrorBanner({
  message,
  className,
  onRetry,
  retryLabel = "Повторить",
  onDismiss,
}: ProductErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="flex gap-2 text-sm text-destructive">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <span>{message}</span>
      </div>
      <div className="flex shrink-0 gap-2">
        {onRetry ? (
          <Button type="button" variant="outline" size="sm" className="border-destructive/50" onClick={onRetry}>
            {retryLabel}
          </Button>
        ) : null}
        {onDismiss ? (
          <Button type="button" variant="ghost" size="sm" onClick={onDismiss}>
            Скрыть
          </Button>
        ) : null}
      </div>
    </div>
  );
}
