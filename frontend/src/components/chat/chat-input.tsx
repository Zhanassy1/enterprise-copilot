"use client";

import { useState } from "react";
import { SendHorizontal, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
  /** Только на время запроса — не смешивать с «наблюдатель» */
  loading?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled,
  loading = false,
  placeholder = "Задайте вопрос по документам…",
}: ChatInputProps) {
  const [text, setText] = useState("");

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex items-end gap-2 border-t bg-background p-4">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={1}
        className="min-h-[44px] max-h-[120px] resize-none"
        disabled={disabled}
      />
      <Button size="icon" onClick={handleSubmit} disabled={disabled || !text.trim()}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizontal className="h-4 w-4" />}
      </Button>
    </div>
  );
}
