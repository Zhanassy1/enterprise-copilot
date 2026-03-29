"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode };

type State = { hasError: boolean; message: string };

class AppErrorBoundaryInner extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(err: Error): State {
    return { hasError: true, message: err.message };
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    console.error("[AppErrorBoundary]", err, info.componentStack);
    toast.error("Ошибка интерфейса. Данные на экране могли отобразиться не полностью.");
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex min-h-[min(480px,70vh)] flex-col items-center justify-center gap-4 rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center"
          role="alert"
        >
          <h2 className="text-lg font-semibold text-foreground">Сбой при отображении</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            {this.state.message || "Неожиданная ошибка React. Обновите страницу или вернитесь назад."}
          </p>
          <Button type="button" onClick={() => window.location.reload()}>
            Обновить страницу
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Resets error state on client route change so navigation recovers after a crash. */
export function AppErrorBoundary({ children }: Props) {
  const pathname = usePathname();
  return <AppErrorBoundaryInner key={pathname}>{children}</AppErrorBoundaryInner>;
}
