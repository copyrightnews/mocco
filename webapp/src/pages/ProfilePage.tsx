import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useProfileStore } from "../stores/useProfileStore";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";
import { ConnectKeyModal } from "../components/ConnectKeyModal";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ModelPickerModal } from "../components/ModelPickerModal";

type Profile = {
  language: string;
  persona: string;
  gender: string;
  age: number | null;
  location: string;
  occupation: string;
  interests: string[];
  timezone: string;
};

const LANGUAGES = [
  { v: "en", l: "English" },
  { v: "bn", l: "Bengali" },
  { v: "es", l: "Spanish" },
  { v: "ar", l: "Arabic" },
  { v: "fr", l: "French" },
  { v: "de", l: "German" },
];

const GENDERS = [
  { v: "", l: "Prefer not to say" },
  { v: "female", l: "Female" },
  { v: "male", l: "Male" },
  { v: "other", l: "Other" },
];

export function ProfilePage() {
  const profile = useProfileStore();
  const setAll = useProfileStore((s) => s.setAll);
  const connectedProviders = useUserStore((s) => s.connectedProviders);
  const setMe = useUserStore((s) => s.setMe);
  const model = useUserStore((s) => s.model);
  const pushToast = useToastStore((s) => s.push);

  const [modelOpen, setModelOpen] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);
  const [editKey, setEditKey] = useState<null | { kind: keyof Profile; label: string; type: "text" | "textarea" | "select" | "number" }>(null);
  const [draft, setDraft] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const p = await api<Profile>("/profile");
        setAll(p);
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [setAll, pushToast]);

  async function patch(body: Partial<Profile>) {
    try {
      const updated = await api<Profile>("/profile", { method: "PATCH", body: JSON.stringify(body) });
      setAll(updated);
    } catch (e) {
      const err = e as ApiError;
      pushToast({ type: "error", text: err.message });
    }
  }

  async function disconnect(provider: string) {
    try {
      await api(`/keys/${provider}`, { method: "DELETE" });
      setMe({ connectedProviders: connectedProviders.filter((p) => p !== provider) });
      pushToast({ type: "success", text: `Disconnected ${provider}.` });
    } catch (e) {
      pushToast({ type: "error", text: (e as Error).message });
    }
  }

  async function refreshKeys() {
    try {
      const keys = await api<{ provider: string }[]>("/keys");
      setMe({ connectedProviders: keys.map((k) => k.provider) });
    } catch { /* ignore */ }
  }

  function openEdit(kind: keyof Profile, label: string, type: "text" | "textarea" | "select" | "number") {
    const current = profile[kind];
    if (Array.isArray(current)) {
      setDraft(current.join(", "));
    } else if (current == null) {
      setDraft("");
    } else {
      setDraft(String(current));
    }
    setEditKey({ kind, label, type });
  }

  function closeEdit() {
    setEditKey(null);
    setDraft("");
  }

  async function saveEdit() {
    if (!editKey) return;
    const { kind, type } = editKey;
    let value: any = draft;
    if (type === "number") {
      value = draft ? Number(draft) : null;
    } else if (kind === "interests") {
      value = draft.split(",").map((s) => s.trim()).filter(Boolean);
    }
    setAll({ [kind]: value } as any);
    await patch({ [kind]: value } as any);
    closeEdit();
  }

  function displayValue(kind: keyof Profile): string {
    const v = profile[kind];
    if (v == null || v === "") return "—";
    if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
    if (kind === "gender") return GENDERS.find((g) => g.v === String(v))?.l ?? String(v);
    if (kind === "language") return LANGUAGES.find((l) => l.v === String(v))?.l ?? String(v);
    return String(v);
  }

  return (
    <ErrorBoundary>
      <div className="px-4 pt-2 pb-24 space-y-7">
        <div className="pt-2">
          <h1 className="text-[32px] leading-[1.1] font-bold tracking-tight text-tg-text">
            Profile
          </h1>
          <p className="mt-2 text-[15px] text-tg-hint">
            Tune how Mocco responds to you.
          </p>
        </div>

        <Group title="Setup">
          <Row
            label="LLM model"
            value={String(model || "(default)")}
            onClick={() => setModelOpen(true)}
          />
          <Divider />
          <Row
            label="Language"
            value={displayValue("language")}
            onClick={() => openEdit("language", "Language", "select")}
          />
          <Divider />
          <Row
            label="Persona"
            value={profile.persona || "—"}
            onClick={() => openEdit("persona", "Persona", "textarea")}
            multiline
          />
        </Group>

        <Group title="About You">
          <Row
            label="Gender"
            value={displayValue("gender")}
            onClick={() => openEdit("gender", "Gender", "select")}
          />
          <Divider />
          <Row
            label="Age"
            value={profile.age != null ? String(profile.age) : "—"}
            onClick={() => openEdit("age", "Age", "number")}
          />
          <Divider />
          <Row
            label="Location"
            value={profile.location || "—"}
            onClick={() => openEdit("location", "Location", "text")}
          />
          <Divider />
          <Row
            label="Occupation"
            value={profile.occupation || "—"}
            onClick={() => openEdit("occupation", "Occupation", "text")}
          />
          <Divider />
          <Row
            label="Interests"
            value={displayValue("interests")}
            onClick={() => openEdit("interests", "Interests", "text")}
          />
          <Divider />
          <Row
            label="Timezone"
            value={profile.timezone || "—"}
            onClick={() => openEdit("timezone", "Timezone", "text")}
          />
        </Group>

        <Group title="API Keys">
          {connectedProviders.length === 0 ? (
            <div className="px-4 py-4 text-[14px] text-tg-hint">
              No keys connected. Add one to enable chat.
            </div>
          ) : (
            connectedProviders.map((p, i) => (
              <div key={p}>
                <div className="mocco-list-row">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-semibold uppercase">
                      ON
                    </span>
                    <span className="text-[15px] text-tg-text font-medium capitalize truncate">
                      {p}
                    </span>
                  </div>
                  <button
                    onClick={() => disconnect(p)}
                    className="text-tg-link text-[14px] active:opacity-50"
                  >
                    Disconnect
                  </button>
                </div>
                {i < connectedProviders.length - 1 && <Divider />}
              </div>
            ))
          )}
          <div className="px-4 pt-3">
            <button
              onClick={() => { refreshKeys(); setKeyOpen(true); }}
              className="w-full py-3 rounded-2xl bg-tg-bg text-tg-link font-semibold text-[15px] active:scale-[0.99] transition-all"
            >
              + Connect a key
            </button>
          </div>
        </Group>
      </div>

      <ModelPickerModal open={modelOpen} onClose={() => setModelOpen(false)} />
      <ConnectKeyModal open={keyOpen} onClose={() => setKeyOpen(false)} onSaved={refreshKeys} />

      {editKey && (
        <div className="fixed inset-0 z-50 bg-black/40" onClick={closeEdit}>
          <div
            className="absolute inset-x-0 bottom-0 bg-tg-secondary-bg rounded-t-[28px] p-5 pb-8 shadow-sheet"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-10 h-1 rounded-full bg-tg-hint/30 mx-auto mb-4" />
            <h3 className="text-[20px] font-bold text-tg-text mb-1">{editKey.label}</h3>
            <p className="text-[13px] text-tg-hint mb-4">
              Saved to your profile on confirm.
            </p>

            {editKey.type === "textarea" && (
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={4}
                placeholder="e.g. Be concise. Max 2 sentences per reply."
                className="w-full px-4 py-3 rounded-2xl bg-tg-bg text-tg-text outline-none text-[15px] placeholder:text-tg-hint resize-none"
              />
            )}

            {editKey.type === "text" && (
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="w-full px-4 py-3 rounded-2xl bg-tg-bg text-tg-text outline-none text-[15px] placeholder:text-tg-hint"
              />
            )}

            {editKey.type === "number" && (
              <input
                type="number"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="w-full px-4 py-3 rounded-2xl bg-tg-bg text-tg-text outline-none text-[15px] placeholder:text-tg-hint"
              />
            )}

            {editKey.type === "select" && (
              <div className="grid grid-cols-2 gap-2">
                {(editKey.kind === "language" ? LANGUAGES : GENDERS).map((opt) => (
                  <button
                    key={opt.v}
                    onClick={() => setDraft(opt.v)}
                    className={`px-4 py-3 rounded-2xl text-[14px] font-medium transition-colors ${
                      draft === opt.v ? "bg-tg-button text-tg-button-text" : "bg-tg-bg text-tg-text"
                    }`}
                  >
                    {opt.l}
                  </button>
                ))}
              </div>
            )}

            <div className="mt-5 flex gap-2">
              <button
                onClick={closeEdit}
                className="flex-1 py-3.5 rounded-2xl bg-tg-bg text-tg-text font-semibold text-[15px] active:scale-[0.99] transition-all"
              >
                Cancel
              </button>
              <button
                onClick={saveEdit}
                className="flex-1 py-3.5 rounded-2xl bg-tg-button text-tg-button-text font-semibold text-[15px] active:scale-[0.99] transition-all"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </ErrorBoundary>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mocco-section-title">{title}</h2>
      <div className="mocco-card overflow-hidden">{children}</div>
    </div>
  );
}

function Row({
  label,
  value,
  onClick,
  multiline,
}: {
  label: string;
  value: string;
  onClick: () => void;
  multiline?: boolean;
}) {
  return (
    <button onClick={onClick} className="mocco-list-row w-full text-left gap-3">
      <div className="min-w-0 flex-1">
        <div className="text-[15px] text-tg-text font-medium">{label}</div>
        <div
          className={`text-[13px] text-tg-hint ${multiline ? "line-clamp-2 mt-0.5" : "truncate"}`}
        >
          {value}
        </div>
      </div>
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true" className="shrink-0 text-tg-hint">
        <path d="M5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

function Divider() {
  return <div className="h-px bg-tg-divider mx-4" />;
}
