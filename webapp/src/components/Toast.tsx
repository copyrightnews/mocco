import { useToastStore } from "../stores/useToastStore";

const COLORS: Record<string, string> = {
  success: "bg-green-500",
  info: "bg-tg-button",
  warning: "bg-yellow-500",
  error: "bg-red-500",
};

export function Toast() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);
  return (
    <div className="fixed top-2 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => remove(t.id)}
          className={`pointer-events-auto px-4 py-2 rounded-full text-white text-sm shadow-lg ${COLORS[t.type] || COLORS.info}`}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
