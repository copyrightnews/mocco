import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";

type Model = { id: string; name: string; is_free: boolean; context_length: number };

export function ModelPickerModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");
  const setMe = useUserStore((s) => s.setMe);
  const pushToast = useToastStore((s) => s.push);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api<Model[]>("/models")
      .then(setModels)
      .catch((e) => pushToast({ type: "error", text: (e as Error).message }))
      .finally(() => setLoading(false));
  }, [open, pushToast]);

  if (!open) return null;
  const filtered = models.filter((m) => (m.name + m.id).toLowerCase().includes(filter.toLowerCase()));

  async function pick(id: string) {
    try {
      await api("/model", { method: "POST", body: JSON.stringify({ model_id: id }) });
      setMe({ model: id });
      pushToast({ type: "success", text: "Model updated." });
      onClose();
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40" onClick={onClose}>
      <div
        className="absolute inset-x-0 bottom-0 max-h-[85vh] bg-tg-secondary-bg rounded-t-[28px] shadow-sheet flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-10 h-1 rounded-full bg-tg-hint/30 mx-auto mt-3 mb-2" />
        <div className="flex items-center justify-between px-5 pb-3">
          <h3 className="text-[20px] font-bold text-tg-text">Pick a model</h3>
          <button onClick={onClose} className="text-tg-link text-[15px] active:opacity-50">
            Close
          </button>
        </div>
        <div className="px-5 pb-3">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search models…"
            className="w-full px-4 py-2.5 rounded-2xl bg-tg-bg text-tg-text outline-none text-[15px] placeholder:text-tg-hint"
          />
        </div>
        <div className="flex-1 overflow-y-auto px-3 pb-4">
          {loading && <p className="text-sm text-tg-hint px-3 py-4 text-center">Loading…</p>}
          {!loading && filtered.length === 0 && (
            <p className="text-sm text-tg-hint px-3 py-4 text-center">No models match.</p>
          )}
          {!loading &&
            filtered.map((m) => (
              <button
                key={m.id}
                onClick={() => pick(m.id)}
                className="w-full text-left px-3 py-3 rounded-2xl hover:bg-tg-bg active:bg-tg-bg flex items-center justify-between"
              >
                <div className="min-w-0">
                  <div className="text-[15px] text-tg-text font-medium truncate">{m.name}</div>
                  <div className="text-[11px] text-tg-hint truncate">{m.id}</div>
                </div>
                {m.is_free && (
                  <span className="text-[10px] text-tg-link font-semibold uppercase ml-2">Free</span>
                )}
              </button>
            ))}
        </div>
      </div>
    </div>
  );
}
