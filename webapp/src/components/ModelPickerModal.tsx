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
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-tg-bg rounded-t-2xl sm:rounded-2xl p-4 w-full sm:w-96 max-h-[80vh] shadow-xl flex flex-col" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-tg-text mb-3">Pick a model</h3>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search…"
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 mb-3"
        />
        <div className="flex-1 overflow-y-auto -mx-1">
          {loading && <p className="text-sm text-tg-hint px-1">Loading…</p>}
          {!loading && filtered.map((m) => (
            <button
              key={m.id}
              onClick={() => pick(m.id)}
              className="w-full text-left px-3 py-2 hover:bg-tg-secondary-bg rounded-lg flex items-center justify-between"
            >
              <div>
                <div className="text-sm text-tg-text">{m.name}</div>
                <div className="text-[10px] text-tg-hint">{m.id}</div>
              </div>
              {m.is_free && <span className="text-[10px] text-tg-link">free</span>}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="mt-3 px-3 py-2 rounded-lg text-sm text-tg-hint w-full">Close</button>
      </div>
    </div>
  );
}
