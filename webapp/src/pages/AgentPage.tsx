import { useEffect } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { api } from "../lib/api";
import { useUserStore } from "../stores/useUserStore";
import { useToastStore } from "../stores/useToastStore";

type MeResponse = { id: number; model: string; language: string; persona: string; connected_providers: string[] };

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
        });
      } catch (e) {
        pushToast({ type: "error", text: (e as Error).message });
      }
    })();
  }, [setMe, pushToast]);

  return <ChatPanel />;
}
