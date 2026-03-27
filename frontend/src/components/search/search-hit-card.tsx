import { Card, CardContent } from "@/components/ui/card";
import { ScoreBadge } from "@/components/shared/score-badge";
import { truncate } from "@/lib/utils";
import type { SearchHit } from "@/lib/api-client";

interface SearchHitCardProps {
  hit: SearchHit;
  index: number;
}

export function SearchHitCard({ hit, index }: SearchHitCardProps) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            Результат #{index + 1} · Фрагмент {hit.chunk_index + 1}
          </span>
          <ScoreBadge score={hit.score} />
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {truncate(hit.text, 600)}
        </p>
      </CardContent>
    </Card>
  );
}
