"use client";

import { useState } from "react";
import type { AnswerStyle } from "@/lib/api-client";
import { useChat } from "@/hooks/use-chat";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { ChatSessionList } from "@/components/chat/chat-session-list";
import { ChatWindow } from "@/components/chat/chat-window";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { PanelLeftOpen } from "lucide-react";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { WorkspaceProductContext } from "@/components/workspace/workspace-product-context";
import { PRODUCT_SECTION } from "@/lib/product-terminology";
import { canWriteInWorkspace } from "@/lib/workspace-role";
import { QuotaLimitCtaBanner } from "@/components/billing/quota-limit-cta";
import { isQuotaErrorMessage } from "@/lib/quota-error";

export default function ChatPage() {
  const { currentWorkspace } = useWorkspace();
  const canChatWrite = canWriteInWorkspace(currentWorkspace?.role);
  const {
    sessions,
    activeSessionId,
    messages,
    loadingSessions,
    loadingMessages,
    sending,
    isStreaming,
    selectSession,
    createSession,
    sendMessage,
    error,
    refresh,
  } = useChat();

  const [panelOpen, setPanelOpen] = useState(false);
  const [answerStyle, setAnswerStyle] = useState<AnswerStyle>("concise");

  const handleCreate = async () => {
    await createSession();
    setPanelOpen(false);
  };

  const handleSelect = (id: string) => {
    selectSession(id);
    setPanelOpen(false);
  };

  return (
    <div className="-mx-4 -my-8 flex h-[calc(100vh-3.5rem)] sm:-mx-6 lg:-mx-8 lg:h-screen">
      {/* Desktop session list */}
      <div className="hidden w-72 shrink-0 border-r md:block">
        <ChatSessionList
          sessions={sessions}
          activeSessionId={activeSessionId}
          loading={loadingSessions}
          onSelect={handleSelect}
          onCreate={handleCreate}
          canCreateSessions={canChatWrite}
        />
      </div>

      {/* Mobile session list */}
      <Sheet open={panelOpen} onOpenChange={setPanelOpen}>
        <SheetContent side="left" className="w-72 p-0 md:hidden">
          <SheetHeader className="sr-only">
            <SheetTitle>Диалоги</SheetTitle>
          </SheetHeader>
          <ChatSessionList
            sessions={sessions}
            activeSessionId={activeSessionId}
            loading={loadingSessions}
            onSelect={handleSelect}
            onCreate={handleCreate}
            canCreateSessions={canChatWrite}
          />
        </SheetContent>
      </Sheet>

      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        {error ? (
          <div className="border-b space-y-3 px-4 py-2">
            <ProductErrorBanner message={error} onRetry={() => void refresh()} />
            <QuotaLimitCtaBanner
              workspaceSlug={currentWorkspace?.slug}
              role={currentWorkspace?.role}
              show={isQuotaErrorMessage(error)}
            />
          </div>
        ) : null}
        <div className="hidden border-b px-4 py-2 md:block">
          <WorkspaceProductContext
            className="mt-0"
            area={`диалоги и источники — только в этом ${PRODUCT_SECTION.workspace.toLowerCase()}`}
            viewerDetail="Можно просматривать существующие диалоги; создание сессий и отправка сообщений отключены для роли «наблюдатель»."
          />
        </div>
        <div className="flex flex-col gap-2 border-b px-4 py-2 md:hidden">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={() => setPanelOpen(true)}>
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium">
              {sessions.find((s) => s.id === activeSessionId)?.title ?? "Чат"}
            </span>
          </div>
          <WorkspaceProductContext
            className="mt-0"
            area={`диалоги — в границах ${PRODUCT_SECTION.workspace.toLowerCase()}`}
            viewerDetail="Можно открывать существующие диалоги; новые сессии и отправка сообщений отключены для роли «наблюдатель»."
          />
        </div>
        <div className="flex-1 overflow-hidden">
          {activeSessionId && canChatWrite ? (
            <div className="flex items-center gap-2 border-b px-4 py-2 text-xs text-muted-foreground">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={answerStyle === "narrative"}
                  onChange={(e) =>
                    setAnswerStyle(e.target.checked ? "narrative" : "concise")
                  }
                />
                Связный ответ по документам
              </label>
            </div>
          ) : null}
          {!loadingSessions && sessions.length === 0 && canChatWrite ? (
            <div className="flex flex-col items-center justify-center gap-3 border-b bg-muted/20 px-4 py-10 text-center">
              <p className="max-w-sm text-sm text-muted-foreground">
                Пока нет диалогов. Создайте первый — и задайте вопрос по документам {PRODUCT_SECTION.workspace.toLowerCase()}.
              </p>
              <Button type="button" onClick={() => void handleCreate()}>
                Создать первый диалог
              </Button>
            </div>
          ) : null}
          <ChatWindow
            messages={messages}
            loadingMessages={loadingMessages}
            sending={sending}
            isStreaming={isStreaming}
            hasSession={!!activeSessionId}
            onSend={(msg) => void sendMessage(msg, 5, answerStyle)}
            canSend={canChatWrite}
          />
        </div>
      </div>
    </div>
  );
}
