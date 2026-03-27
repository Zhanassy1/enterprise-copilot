import { Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface AnswerCardProps {
  answer: string;
  details?: string | null;
  nextStep?: string | null;
  confidence?: number;
}

export function AnswerCard({ answer, details, nextStep, confidence }: AnswerCardProps) {
  return (
    <Card className="border-primary/20 bg-primary/[0.02]">
      <CardContent className="flex gap-3 p-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Sparkles className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-primary/70">
            Ответ AI
          </p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{answer}</p>
          {details ? (
            <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
              Детали: {details}
            </p>
          ) : null}
          {typeof confidence === "number" ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Уверенность: {(confidence * 100).toFixed(0)}%
            </p>
          ) : null}
          {nextStep ? (
            <p className="mt-1 text-sm font-medium">Следующий шаг: {nextStep}</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
