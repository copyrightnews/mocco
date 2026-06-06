import { Message } from "../stores/useChatStore";

export function MessageBubble({ m, onRetry }: { m: Message; onRetry?: () => void }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-1.5 px-3`}>
      <div
        className={`max-w-[78%] px-3.5 py-2.5 text-[15px] leading-snug whitespace-pre-wrap break-words ${
          isUser
            ? "bg-tg-button text-tg-button-text rounded-[20px] rounded-br-md"
            : "bg-tg-secondary-bg text-tg-text rounded-[20px] rounded-bl-md shadow-pill"
        }`}
      >
        {m.content || (m.streaming ? "…" : "")}
        {m.error && (
          <button onClick={onRetry} className="ml-2 underline text-tg-link">
            retry
          </button>
        )}
      </div>
    </div>
  );
}
