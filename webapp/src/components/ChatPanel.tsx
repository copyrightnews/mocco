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
  const connectedProviders = useUserStore((s) => s.connectedProviders);
  const quota = useUserStore((s) => s.quota);
  const setMe = useUserStore((s) => s.setMe);
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
        } else if (frame.kind === "usage") {
          const cur = useUserStore.getState().quota;
          if (cur.limit > 0) {
            setMe({ quota: { ...cur, used: cur.used + frame.totalTokens } });
          }
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
      if (err.status === 429 && err.code === "quota_exceeded") {
        pushToast({
          type: "warning",
          text: "Daily limit reached. Add your own key in Profile to keep chatting.",
        });
      } else if (err.status === 400 && err.code === "no_api_key") {
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
  const onFallback = connectedProviders.length === 0 && quota.limit > 0;
  const quotaExhausted = onFallback && quota.used >= quota.limit;
  const quotaPct = quota.limit > 0 ? Math.min(100, Math.round((quota.used / quota.limit) * 100)) : 0;

  return (
    <div className="relative flex flex-col h-full mocco-agent-wallpaper overflow-hidden">
      <div ref={scrollRef} className="relative flex-1 overflow-y-auto pb-40 z-10">
        {empty && (
          <div className="px-5 pt-10">
            <h1 className="text-[32px] leading-[1.1] font-bold tracking-tight text-white">
              How can I help
              <br />
              you today?
            </h1>
            <p className="mt-3 text-[15px] text-white/60">
              Ask anything or pick a quick action below.
            </p>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} m={m} tone="dark" />
        ))}
      </div>

      <div className="fixed inset-x-0 bottom-16 z-30 pt-4 bg-gradient-to-t from-[#050a1c] via-[#050a1c]/85 to-transparent">
        {onFallback && (
          <div className="px-3 pb-2">
            <div
              className={
                "mocco-glass-pill flex items-center gap-2.5 px-3.5 py-2 text-[12.5px] text-white/90 " +
                (quotaExhausted ? "ring-1 ring-red-400/40" : "")
              }
            >
              <span
                className={
                  "w-1.5 h-1.5 rounded-full shrink-0 " +
                  (quotaExhausted ? "bg-red-400" : "bg-white/80")
                }
                aria-hidden="true"
              />
              <span className="font-medium">Mocco's key</span>
              <span className="text-white/60">
                {quota.used.toLocaleString()} / {quota.limit.toLocaleString()} tokens
              </span>
              <div className="ml-1 flex-1 h-1 rounded-full bg-white/15 overflow-hidden">
                <div
                  className={"h-full " + (quotaExhausted ? "bg-red-400/80" : "bg-white/70")}
                  style={{ width: `${quotaPct}%` }}
                />
              </div>
            </div>
          </div>
        )}
        {messages.length > 0 && (
          <div className="overflow-x-auto">
            <div className="flex gap-2 px-4 pb-2 w-max">
              <button
                onClick={() => setResetOpen(true)}
                className="mocco-glass-pill flex items-center gap-1.5 px-3.5 py-2 rounded-full text-[13px] font-medium active:scale-[0.98]"
              >
                <span>Reset</span>
              </button>
            </div>
          </div>
        )}
        <div className="px-3 pt-2 pb-3">
          <div className="mocco-glass-strong rounded-2xl flex items-center gap-2 px-2 py-1.5 shadow-[0_8px_24px_rgba(0,0,0,0.3)]">
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
              className="flex-1 resize-none bg-transparent text-white outline-none text-[15px] px-2.5 py-1.5 max-h-32 placeholder:text-white/50"
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
          <QuickActionChips onReset={() => setResetOpen(true)} tone="dark" />
        </div>
      )}

      <ResetConfirmModal open={resetOpen} onCancel={() => setResetOpen(false)} onConfirm={doReset} />
    </div>
  );
}
