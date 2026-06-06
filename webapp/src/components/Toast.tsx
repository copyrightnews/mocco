import { useToastStore } from "../stores/useToastStore";

const COLORS: Record<string, string> = {
  success: "bg-emerald-500",
  info: "bg-tg-button",
  warning: "bg-amber-500",
  error: "bg-red-500",
};

export function Toast() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);
  return (
    <div className="fixed top-[calc(env(safe-area-inset-top)+56px)] left-3 right-3 z-[60] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => remove(t.id)}
          className={`pointer-events-auto px-4 py-3 rounded-2xl text-white text-[14px] font-medium shadow-[0_8px_24px_rgba(0,0,0,0.18)] backdrop-blur-md ${
            COLORS[t.type] || COLORS.info
          }`}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
