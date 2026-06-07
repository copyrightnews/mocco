import { useEffect } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { api } from "../lib/api";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";

type MeResponse = {
  id: number;
  model: string;
  language: string;
  persona: string;
  connected_providers: string[];
  quota: { used: number; limit: number; resets_at: string };
};

export function AgentPage() {
  const setMe = useUserStore((s) => s.setMe);
  const pushToast = useToastStore((s) => s.push);

  useEffect(() => {
    (async () => {
      try {
        const me = await api<MeResponse>("/me");
        setMe({
          telegramId: me.id,
          model: me.model,
          language: me.language || "en",
          persona: me.persona,
          connectedProviders: me.connected_providers,
          quota: {
            used: me.quota.used,
            limit: me.quota.limit,
            resetsAt: me.quota.resets_at,
          },
        });
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [setMe, pushToast]);

  return <ErrorBoundary><ChatPanel /></ErrorBoundary>;
}
