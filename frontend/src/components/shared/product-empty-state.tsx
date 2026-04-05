import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type ProductEmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  children?: ReactNode;
};

/** Единый layout пустых экранов (документы, поиск, чат, jobs, team, billing). */
export function ProductEmptyState({ icon: Icon, title, description, children }: ProductEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center md:py-20">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <Icon className="h-8 w-8 text-muted-foreground" aria-hidden />
      </div>
      <h3 className="text-lg font-medium">{title}</h3>
      <div className="mt-1 max-w-md text-sm text-muted-foreground">{description}</div>
      {children ? <div className="mt-4 flex flex-wrap justify-center gap-2">{children}</div> : null}
    </div>
  );
}
