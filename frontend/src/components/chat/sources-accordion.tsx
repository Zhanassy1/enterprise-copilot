"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { ScoreBadge } from "@/components/shared/score-badge";
import { truncate } from "@/lib/utils";
import type { SearchHit } from "@/lib/api-client";

interface SourcesAccordionProps {
  sources: SearchHit[];
}

export function SourcesAccordion({ sources }: SourcesAccordionProps) {
  if (sources.length === 0) return null;

  return (
    <Accordion type="single" collapsible className="mt-2">
      <AccordionItem value="sources" className="border-none">
        <AccordionTrigger className="py-1 text-xs text-muted-foreground hover:no-underline">
          Источники ({sources.length})
        </AccordionTrigger>
        <AccordionContent>
          <div className="space-y-2">
            {sources.map((s, i) => (
              <div
                key={`${s.chunk_id}-${i}`}
                className="rounded-lg bg-muted/50 p-3 text-xs"
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-muted-foreground">
                    Фрагмент {s.chunk_index + 1}
                  </span>
                  <ScoreBadge score={s.score} />
                </div>
                <p className="leading-relaxed">{truncate(s.text, 300)}</p>
              </div>
            ))}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
