"use client";

import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { AnswerStyle } from "@/lib/api-client";

interface SearchBarProps {
  onSearch: (query: string, topK: number, answerStyle: AnswerStyle) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [answerStyle, setAnswerStyle] = useState<AnswerStyle>("concise");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    onSearch(trimmed, topK, answerStyle);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto flex w-full max-w-2xl flex-col gap-3"
    >
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите поисковый запрос…"
            className="pl-9"
          />
        </div>
        <Button type="submit" disabled={loading || !query.trim()}>
          {loading ? <Loader2 className="animate-spin" /> : "Найти"}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <label htmlFor="topk">Результатов:</label>
          <select
            id="topk"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="rounded-lg border border-input bg-background px-2 py-1 text-sm"
          >
            {[3, 5, 10, 15, 20].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={answerStyle === "narrative"}
            onChange={(e) =>
              setAnswerStyle(e.target.checked ? "narrative" : "concise")
            }
          />
          Связный ответ (как в диалоге)
        </label>
      </div>
    </form>
  );
}
