import { useEffect, useRef, useState } from "react";
import { useChatStore, Message } from "../stores/useChatStore";
import { useUserStore } from "../stores/useUserStore";
import { MessageBubble } from "./MessageBubble";
import { QuickActionChips } from "./QuickActionChips";
import { ResetConfirmModal } from "./ResetConfirmModal";
import { streamChat } from "../lib/stream";
import { api, ApiError } from "../lib/api";
import { useToastStore } from "../stores/useToastStore";
import { haptic } from "../lib/telegram";

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages);
  const input = useChatStore((s) => s.input);
  const setInput = useChatStore((s) => s.setInput);
  const streaming = useChatStore((s) => s.streaming);
  const setAbort = useChatStore((s) => s.setAbort);
  const cancel = useChatStore((s) => s.cancel);
  const hydrate = useChatStore((s) => s.hydrate);
  const appendDelta = useChatStore((s) => s.appendDelta);
  const markComplete = useChatStore((s) => s.markComplete);
  const markError = useChatStore((s) => s.markError);
  const clear = useChatStore((s) => s.clear);
  const telegramId = useUserStore((s) => s.telegramId);
  const pushToast = useToastStore((s) => s.push);

  const [resetOpen, setResetOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Hydrate from /v1/history on mount.
  useEffect(() => {
    if (!telegramId) return;
    (async () => {
      try {
        const data = await api<Message[]>("/history");
        hydrate(data);
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [telegramId, hydrate, pushToast]);

  // Auto-scroll to bottom.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  async function send() {
    if (!input.trim() || streaming) return;
    haptic.impact("light");
    const userMsg: Message = { role: "user", content: input };
    const asstMsg: Message = { role: "assistant", content: "", streaming: true };
    useChatStore.setState((s) => ({
      messages: [...s.messages, userMsg, asstMsg],
      input: "",
      streaming: true,
    }));
    const ctrl = new AbortController();
    setAbort(ctrl);

    try {
      const history = useChatStore.getState().messages
        .filter((m) => !m.error)
        .map(({ role, content }) => ({ role, content }));
      let firstDelta = true;
      for await (const frame of streamChat({ messages: history.slice(0, -1) }, ctrl.signal)) {
        if (frame.kind === "delta") {
          if (firstDelta) {
            haptic.notify("success");
            firstDelta = false;
          }
          appendDelta(frame.delta);
        } else if (frame.kind === "done") {
          markComplete();
        } else if (frame.kind === "error") {
          markError();
          pushToast({ type: "error", text: frame.message });
        }
      }
    } catch (e) {
      markError();
      const err = e as ApiError;
      if (err.status === 400 && err.code === "no_api_key") {
        pushToast({ type: "warning", text: "Connect a key to chat." });
      } else {
        pushToast({ type: "error", text: err.message || "Stream failed." });
      }
    } finally {
      setAbort(null);
    }
  }

  async function doReset() {
    setResetOpen(false);
    try {
      await api("/reset", { method: "POST" });
      clear();
      pushToast({ type: "success", text: "Conversation cleared." });
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto pt-2 pb-32">
        {messages.length === 0 && (
          <div className="px-4 pt-12 text-center">
            <h2 className="text-xl font-semibold text-tg-text mb-4">How can I help you today?</h2>
            <QuickActionChips onReset={() => setResetOpen(true)} />
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} />
        ))}
      </div>
      <div className="fixed bottom-14 left-0 right-0 bg-tg-bg border-t border-tg-hint/20">
        {messages.length > 0 && <QuickActionChips onReset={() => setResetOpen(true)} />}
        <div className="flex items-end gap-2 p-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask anything…"
            rows={1}
            className="flex-1 resize-none rounded-2xl px-3 py-2 bg-tg-secondary-bg text-tg-text outline-none text-sm max-h-32"
          />
          <button
            onClick={send}
            disabled={!input.trim() || streaming}
            className="px-3 py-2 rounded-2xl bg-tg-button text-tg-button-text text-sm font-medium disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
      <ResetConfirmModal open={resetOpen} onCancel={() => setResetOpen(false)} onConfirm={doReset} />
    </div>
  );
}
