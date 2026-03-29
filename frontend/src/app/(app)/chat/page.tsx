"use client";

import { useState } from "react";
import { useChat } from "@/hooks/use-chat";
import { ProductErrorBanner } from "@/components/shared/product-error-banner";
import { ChatSessionList } from "@/components/chat/chat-session-list";
import { ChatWindow } from "@/components/chat/chat-window";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { PanelLeftOpen } from "lucide-react";
import { useWorkspace } from "@/components/workspace/workspace-provider";
import { WorkspaceContextStrip } from "@/components/workspace/workspace-context-strip";
import { canWriteInWorkspace } from "@/lib/workspace-role";

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
          <div className="border-b px-4 py-2">
            <ProductErrorBanner message={error} onRetry={() => void refresh()} />
          </div>
        ) : null}
        <div className="hidden border-b px-4 py-2 md:block">
          <WorkspaceContextStrip area="диалоги и источники — только в этом workspace" />
          {!canChatWrite ? (
            <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">
              Роль «наблюдатель»: можно просматривать существующие диалоги, но создание и отправка сообщений отключены (политика API).
            </p>
          ) : null}
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
          {!canChatWrite ? (
            <p className="text-xs text-amber-800 dark:text-amber-200">
              Наблюдатель: можно открыть существующие диалоги, отправка сообщений и новые сессии отключены.
            </p>
          ) : null}
        </div>
        <div className="flex-1 overflow-hidden">
          <ChatWindow
            messages={messages}
            loadingMessages={loadingMessages}
            sending={sending}
            isStreaming={isStreaming}
            hasSession={!!activeSessionId}
            onSend={(msg) => void sendMessage(msg)}
            canSend={canChatWrite}
          />
        </div>
      </div>
    </div>
  );
}
