import { useChatStore } from "../stores/useChatStore";

export function QuickActionChips({ onReset }: { onReset: () => void }) {
  const setInput = useChatStore((s) => s.setInput);
  const input = useChatStore((s) => s.input);
  const disabled = input.trim().length > 0;
  const chip = (label: string, prefix: string) => (
    <button
      key={label}
      type="button"
      onClick={() => setInput(prefix)}
      disabled={disabled}
      className="px-3 py-1.5 rounded-full text-xs bg-tg-secondary-bg text-tg-text border border-tg-hint/30 disabled:opacity-50"
    >
      {label}
    </button>
  );
  return (
    <div className="flex flex-wrap gap-2 px-3 py-2">
      {chip("Search", "/search ")}
      {chip("Summarize", "/summarize ")}
      {chip("Translate", "/translate ")}
      <button
        type="button"
        onClick={onReset}
        className="px-3 py-1.5 rounded-full text-xs bg-tg-secondary-bg text-tg-text border border-tg-hint/30"
      >
        Reset chat
      </button>
    </div>
  );
}
