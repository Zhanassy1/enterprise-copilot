"use client";

import { cn } from "@/lib/utils";
import { formatBytesIEC, formatQuotaNumber } from "@/lib/format-quota";

export type QuotaUnit = "requests" | "tokens" | "bytes" | "documents";

interface QuotaUsageRowProps {
  title: string;
  description?: string;
  used: number;
  /** null = без потолка по плану (напр. документы Team) */
  limit: number | null;
  unit: QuotaUnit;
}

function displayUsed(used: number, unit: QuotaUnit): string {
  if (unit === "bytes") return formatBytesIEC(used);
  return formatQuotaNumber(used);
}

function displayLimit(limit: number, unit: QuotaUnit): string {
  if (unit === "bytes") return formatBytesIEC(limit);
  return formatQuotaNumber(limit);
}

export function QuotaUsageRow({ title, description, used, limit, unit }: QuotaUsageRowProps) {
  const unlimited = limit === null;
  const safeUsed = Math.max(0, used);
  const cap = limit ?? 0;
  const over = !unlimited && cap > 0 && safeUsed > cap;
  const pct =
    unlimited || cap <= 0 ? null : Math.min(100, Math.round((safeUsed / cap) * 1000) / 10);

  const remaining =
    unlimited || cap <= 0 ? null : Math.max(0, Math.floor(cap - safeUsed));

  return (
    <div className="space-y-2 rounded-xl border border-border/70 bg-card/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium leading-none">{title}</p>
          {description ? (
            <p className="mt-1 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
        <div className="text-right text-sm tabular-nums">
          {unlimited ? (
            <span>
              <span className="font-medium text-foreground">{displayUsed(safeUsed, unit)}</span>
              <span className="text-muted-foreground"> — без потолка по плану</span>
            </span>
          ) : (
            <>
              <span className={cn("font-medium", over && "text-destructive")}>
                {displayUsed(safeUsed, unit)}
              </span>
              <span className="text-muted-foreground">
                {" "}
                / {displayLimit(cap, unit)}
              </span>
              {remaining !== null && !over ? (
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  осталось {unit === "bytes" ? formatBytesIEC(remaining) : formatQuotaNumber(remaining)}
                </span>
              ) : null}
              {over ? (
                <span className="mt-0.5 block text-xs font-medium text-destructive">
                  превышение лимита
                </span>
              ) : null}
            </>
          )}
        </div>
      </div>
      {!unlimited && cap > 0 ? (
        <div
          className="h-2.5 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={Math.min(safeUsed, cap)}
          aria-valuemin={0}
          aria-valuemax={cap}
          aria-label={title}
        >
          <div
            className={cn(
              "h-full rounded-full transition-all",
              over ? "bg-destructive" : pct !== null && pct >= 90 ? "bg-amber-500" : "bg-primary"
            )}
            style={{ width: `${Math.min(100, pct ?? 0)}%` }}
          />
        </div>
      ) : unlimited ? (
        <div className="h-2.5 w-full rounded-full bg-muted/60" title="Лимит по плану не задан" />
      ) : (
        <p className="text-xs text-muted-foreground">Лимит 0 — уточните конфигурацию workspace.</p>
      )}
    </div>
  );
}
