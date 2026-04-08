"use client";

import { useState, useEffect } from "react";
import { useSearch } from "@/hooks/use-search";
import { PageHeader } from "@/components/shared/page-header";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { SearchBar } from "@/components/search/search-bar";
import { AnswerCard } from "@/components/search/answer-card";
import { SearchHitCard } from "@/components/search/search-hit-card";
import { SearchEmptyState } from "@/components/search/search-empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { WorkspaceProductContext } from "@/components/workspace/workspace-product-context";
import { PRODUCT_SECTION } from "@/lib/product-terminology";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { QuotaLimitCtaBanner } from "@/components/billing/quota-limit-cta";
import { isQuotaErrorMessage } from "@/lib/quota-error";

export default function SearchPage() {
  const { currentWorkspace } = useWorkspace();
  const { result, loading, error, search } = useSearch();
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (error) setDismissed(false);
  }, [error]);

  return (
    <>
      <PageHeader
        title="Поиск"
        description={`Семантический поиск только по проиндексированным документам выбранного ${PRODUCT_SECTION.workspace.toLowerCase()} — без доступа к чужим пространствам.`}
      />

      <WorkspaceProductContext
        className="mt-4"
        area="индекс и ответы поиска — в границах этого рабочего пространства"
        viewerDetail="Поиск и просмотр источников доступны в режиме чтения. Запросы поиска учитываются в месячной квоте плана так же, как у остальных ролей."
      />

      {error && !dismissed ? (
        <div className="mt-6 space-y-3">
          <ProductErrorBanner
            message={error}
            onDismiss={() => setDismissed(true)}
          />
          <QuotaLimitCtaBanner
            workspaceSlug={currentWorkspace?.slug}
            role={currentWorkspace?.role}
            show={isQuotaErrorMessage(error)}
          />
        </div>
      ) : null}

      <div className="mt-8">
        <SearchBar onSearch={search} loading={loading} />
      </div>

      <div className="mx-auto mt-8 max-w-2xl space-y-4">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-2xl" />
          ))
        ) : result ? (
          <>
            {result.answer ? (
              <AnswerCard
                answer={result.answer}
                details={result.details}
                nextStep={result.next_step}
                confidence={result.confidence}
              />
            ) : null}
            {result.decision === "clarify" && result.clarifying_question ? (
              <AnswerCard
                answer={`Нужна конкретизация: ${result.clarifying_question}`}
                nextStep={result.next_step}
                confidence={result.confidence}
              />
            ) : null}
            {result.decision === "insufficient_context" && result.clarifying_question ? (
              <AnswerCard
                answer="Недостаточно подтвержденных данных в документах."
                details={`Уточнение: ${result.clarifying_question}`}
                nextStep={result.next_step}
                confidence={result.confidence}
              />
            ) : null}
            {result.hits.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                По вашему запросу ничего не найдено
              </p>
            ) : (
              <Accordion
                type="single"
                collapsible
                className="rounded-2xl border px-4"
                defaultValue={
                  result.evidence_collapsed_by_default ? undefined : "search-sources"
                }
              >
                <AccordionItem value="search-sources" className="border-none">
                  <AccordionTrigger className="py-3 text-sm hover:no-underline">
                    Источники ({result.hits.length})
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-4 pb-2">
                      {result.hits.map((hit, i) => (
                        <SearchHitCard key={hit.chunk_id} hit={hit} index={i} />
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}
          </>
        ) : (
          <SearchEmptyState />
        )}
      </div>
    </>
  );
}
