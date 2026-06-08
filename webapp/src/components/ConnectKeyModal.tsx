import { useState } from "react";
import { api } from "../lib/api";
import { useToastStore } from "../stores/useToastStore";

const PROVIDERS: { id: "openrouter" | "serper"; label: string; help: string }[] = [
  { id: "openrouter", label: "OpenRouter", help: "Get a key at openrouter.ai/keys" },
  { id: "serper", label: "Serper", help: "Get a key at serper.dev" },
];

export function ConnectKeyModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const [provider, setProvider] = useState<"openrouter" | "serper">("openrouter");
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const pushToast = useToastStore((s) => s.push);

  if (!open) return null;
  const current = PROVIDERS.find((p) => p.id === provider)!;

  async function save() {
    if (!key.trim()) return;
    setSaving(true);
    try {
      await api(`/keys/${provider}`, { method: "POST", body: JSON.stringify({ api_key: key }) });
      pushToast({ type: "success", text: `${current.label} key saved.` });
      setKey("");
      onSaved();
      onClose();
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40" onClick={onClose}>
      <div
        className="absolute inset-x-0 bottom-0 bg-tg-secondary-bg rounded-t-[28px] p-5 pb-8 shadow-sheet"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-10 h-1 rounded-full bg-tg-hint/30 mx-auto mb-4" />
        <h3 className="text-[20px] font-bold text-tg-text text-center mb-1">Connect a key</h3>
        <p className="text-[13px] text-tg-hint text-center mb-5">
          Add an API key to use Mocco for chat and search.
        </p>

        <div className="grid grid-cols-2 gap-2 mb-4">
          {PROVIDERS.map((p) => (
            <button
              key={p.id}
              onClick={() => setProvider(p.id)}
              className={`px-4 py-3 rounded-2xl text-[14px] font-medium transition-colors ${
                provider === p.id
                  ? "bg-tg-button text-tg-button-text"
                  : "bg-tg-bg text-tg-text"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <label className="text-[12px] text-tg-hint font-medium">API key</label>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="paste here"
          className="w-full mt-1 mb-1 px-4 py-3 rounded-2xl bg-tg-bg text-tg-text outline-none text-[15px] placeholder:text-tg-hint"
        />
        <p className="text-[11px] text-tg-hint mb-5">{current.help}</p>

        <button
          onClick={save}
          disabled={saving || !key.trim()}
          className="w-full py-3.5 rounded-2xl bg-tg-button text-tg-button-text font-semibold text-[15px] disabled:opacity-40 active:scale-[0.99] transition-all"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          onClick={onClose}
          className="w-full py-3.5 rounded-2xl bg-tg-bg text-tg-text font-semibold text-[15px] mt-2 active:scale-[0.99] transition-all"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
