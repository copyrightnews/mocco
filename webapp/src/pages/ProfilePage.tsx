import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useProfileStore } from "../stores/useProfileStore";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";
import { ConnectKeyModal } from "../components/ConnectKeyModal";
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

export function ProfilePage() {
  const profile = useProfileStore();
  const setAll = useProfileStore((s) => s.setAll);
  const connectedProviders = useUserStore((s) => s.connectedProviders);
  const setMe = useUserStore((s) => s.setMe);
  const model = useUserStore((s) => s.model);
  const pushToast = useToastStore((s) => s.push);

  const [modelOpen, setModelOpen] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);

  // Hydrate from /v1/profile.
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

  return (
    <div className="p-4 pb-24 space-y-6">
      <Section title="LLM model">
        <button onClick={() => setModelOpen(true)} className="w-full text-left px-3 py-2 rounded-lg bg-tg-secondary-bg">
          <span className="text-sm text-tg-text">{model || "(default)"}</span>
        </button>
      </Section>

      <Section title="Language">
        <select
          value={profile.language}
          onChange={(e) => { setAll({ language: e.target.value }); patch({ language: e.target.value }); }}
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2"
        >
          <option value="en">English</option>
          <option value="bn">Bengali</option>
          <option value="es">Spanish</option>
          <option value="ar">Arabic</option>
          <option value="fr">French</option>
          <option value="de">German</option>
        </select>
      </Section>

      <Section title="Persona">
        <textarea
          value={profile.persona}
          onChange={(e) => setAll({ persona: e.target.value })}
          onBlur={() => patch({ persona: profile.persona })}
          rows={3}
          placeholder="e.g. Be concise. Max 2 sentences per reply."
          className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
        />
      </Section>

      <Section title="About You">
        <Field label="Gender">
          <select
            value={profile.gender}
            onChange={(e) => { setAll({ gender: e.target.value }); patch({ gender: e.target.value }); }}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          >
            <option value="">—</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
            <option value="prefer_not">Prefer not to say</option>
          </select>
        </Field>
        <Field label="Age">
          <input
            type="number"
            value={profile.age ?? ""}
            onChange={(e) => setAll({ age: e.target.value ? Number(e.target.value) : null })}
            onBlur={() => patch({ age: profile.age })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Location">
          <input
            value={profile.location}
            onChange={(e) => setAll({ location: e.target.value })}
            onBlur={() => patch({ location: profile.location })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Occupation">
          <input
            value={profile.occupation}
            onChange={(e) => setAll({ occupation: e.target.value })}
            onBlur={() => patch({ occupation: profile.occupation })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Interests (comma-separated)">
          <input
            value={profile.interests.join(", ")}
            onChange={(e) => setAll({ interests: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
            onBlur={() => patch({ interests: profile.interests })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
        <Field label="Timezone">
          <input
            value={profile.timezone}
            onChange={(e) => setAll({ timezone: e.target.value })}
            onBlur={() => patch({ timezone: profile.timezone })}
            className="w-full rounded-lg bg-tg-secondary-bg text-tg-text px-3 py-2 text-sm"
          />
        </Field>
      </Section>

      <Section title="API Keys">
        {connectedProviders.length === 0 && (
          <p className="text-sm text-tg-hint mb-2">No keys connected. Connect one to enable chat.</p>
        )}
        {connectedProviders.map((p) => (
          <div key={p} className="flex items-center justify-between py-2">
            <span className="text-sm text-tg-text capitalize">{p}</span>
            <button onClick={() => disconnect(p)} className="text-xs text-tg-link">Disconnect</button>
          </div>
        ))}
        <button onClick={() => { refreshKeys(); setKeyOpen(true); }} className="w-full mt-2 px-3 py-2 rounded-lg bg-tg-button text-tg-button-text text-sm">
          Connect a key
        </button>
      </Section>

      <ModelPickerModal open={modelOpen} onClose={() => setModelOpen(false)} />
      <ConnectKeyModal open={keyOpen} onClose={() => setKeyOpen(false)} onSaved={refreshKeys} />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-xs uppercase tracking-wide text-tg-hint mb-2">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[10px] text-tg-hint">{label}</label>
      {children}
    </div>
  );
}
