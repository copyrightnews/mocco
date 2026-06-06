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
  const hydrate = useChatStore((s) => s.hydrate);
  const appendDelta = useChatStore((s) => s.appendDelta);
  const markComplete = useChatStore((s) => s.markComplete);
  const markError = useChatStore((s) => s.markError);
  const clear = useChatStore((s) => s.clear);
  const telegramId = useUserStore((s) => s.telegramId);
  const pushToast = useToastStore((s) => s.push);

  const [resetOpen, setResetOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  const empty = messages.length === 0;

  return (
    <div className="flex flex-col h-full bg-tg-bg">
      <div ref={scrollRef} className="flex-1 overflow-y-auto pb-32">
        {empty && (
          <div className="px-5 pt-10">
            <h1 className="text-[32px] leading-[1.1] font-bold tracking-tight text-tg-text">
              How can I help
              <br />
              you today?
            </h1>
            <p className="mt-3 text-[15px] text-tg-hint">
              Ask anything or pick a quick action below.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} />
        ))}
      </div>

      <div className="fixed inset-x-0 bottom-16 z-30 bg-gradient-to-t from-tg-bg via-tg-bg to-transparent pt-4">
        {messages.length > 0 && (
          <div className="overflow-x-auto">
            <div className="flex gap-2 px-4 pb-2 w-max">
              <button
                onClick={() => setResetOpen(true)}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-tg-secondary-bg shadow-pill text-tg-text text-[13px] font-medium active:scale-[0.98]"
              >
                <span>Reset</span>
              </button>
            </div>
          </div>
        )}
        <div className="bg-tg-bg/95 backdrop-blur-md px-3 pt-2 pb-3">
          <div className="mocco-card flex items-center gap-2 px-2 py-1.5">
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
              className="flex-1 resize-none bg-transparent text-tg-text outline-none text-[15px] px-2.5 py-1.5 max-h-32 placeholder:text-tg-hint"
            />
            <button
              onClick={send}
              disabled={!input.trim() || streaming}
              aria-label="Send"
              className="w-9 h-9 rounded-full bg-tg-button text-tg-button-text flex items-center justify-center disabled:opacity-30 active:scale-95 transition-all shrink-0"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 13V3M3 8l5-5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {empty && (
        <div className="fixed inset-x-0 bottom-32 z-20">
          <QuickActionChips onReset={() => setResetOpen(true)} />
        </div>
      )}

      <ResetConfirmModal open={resetOpen} onCancel={() => setResetOpen(false)} onConfirm={doReset} />
    </div>
  );
}
