import { useState } from "react";
import { api } from "../lib/api";
import { useToastStore } from "../stores/useToastStore";

const PROVIDERS: { id: "openrouter" | "serper"; label: string; help: string }[] = [
  { id: "openrouter", label: "OpenRouter", help: "Get a key at openrouter.ai/keys" },
  { id: "serper", label: "Serper (web search)", help: "Get a key at serper.dev" },
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-tg-bg rounded-2xl p-4 w-80 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-tg-text mb-3">Connect a key</h3>
        <label className="text-xs text-tg-hint">Provider</label>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value as "openrouter" | "serper")}
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 mt-1 mb-3"
        >
          {PROVIDERS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
        <label className="text-xs text-tg-hint">API key</label>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="paste here"
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 mt-1 mb-1"
        />
        <p className="text-[10px] text-tg-hint mb-3">{current.help}</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-sm text-tg-hint">Cancel</button>
          <button onClick={save} disabled={saving || !key.trim()} className="px-3 py-1.5 rounded-lg text-sm bg-tg-button text-tg-button-text disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
