import { Message } from "../stores/useChatStore";

export function MessageBubble({ m, onRetry }: { m: Message; onRetry?: () => void }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-2 px-3`}>
      <div
        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-tg-button text-tg-button-text rounded-br-md"
            : "bg-tg-secondary-bg text-tg-text rounded-bl-md"
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
