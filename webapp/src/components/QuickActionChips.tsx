import { useChatStore } from "../stores/useChatStore";

export function QuickActionChips({ onReset, tone = "light" }: { onReset: () => void; tone?: "light" | "dark" }) {
  const setInput = useChatStore((s) => s.setInput);
  const input = useChatStore((s) => s.input);
  const disabled = input.trim().length > 0;

  const baseCls =
    tone === "dark"
      ? "mocco-glass-pill flex items-center gap-1.5 px-3.5 py-2 rounded-full text-[13px] font-medium disabled:opacity-40 active:scale-[0.98] transition-all"
      : "flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-tg-secondary-bg shadow-pill text-tg-text text-[13px] font-medium disabled:opacity-40 active:scale-[0.98] transition-all";

  const chip = (label: string, prefix: string, emoji: string) => (
    <button
      key={label}
      type="button"
      onClick={() => setInput(prefix)}
      disabled={disabled}
      className={baseCls}
    >
      <span className="text-base leading-none">{emoji}</span>
      <span>{label}</span>
    </button>
  );

  return (
    <div className="flex flex-wrap gap-2 px-4 py-3">
      {chip("Search", "/search ", "🔍")}
      {chip("Summarize", "/summarize ", "📝")}
      {chip("Translate", "/translate ", "🌐")}
      <button
        type="button"
        onClick={onReset}
        className={baseCls}
      >
        <span className="text-base leading-none">🗑</span>
        <span>Reset</span>
      </button>
    </div>
  );
}
