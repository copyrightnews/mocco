import { Message } from "../stores/useChatStore";
import { ThinkingAnimation } from "./ThinkingAnimation";

export function MessageBubble({ m, onRetry, tone = "light" }: { m: Message; onRetry?: () => void; tone?: "light" | "dark" }) {
  const isUser = m.role === "user";
  const dark = tone === "dark";
  const thinking = !isUser && m.streaming && !m.content;
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-1.5 px-3`}>
      <div
        className={`max-w-[78%] px-3.5 py-2.5 text-[15px] leading-snug whitespace-pre-wrap break-words rounded-[20px] ${
          isUser
            ? "bg-tg-button text-tg-button-text rounded-br-md"
            : dark
            ? "mocco-glass-pill rounded-bl-md text-white"
            : "bg-tg-secondary-bg text-tg-text rounded-bl-md shadow-pill"
        }`}
      >
        {thinking ? <ThinkingAnimation /> : m.content}
        {m.error && (
          <button onClick={onRetry} className="ml-2 underline text-tg-link">
            retry
          </button>
        )}
      </div>
    </div>
  );
}
