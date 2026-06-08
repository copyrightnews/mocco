import { create } from "zustand";
import { persist } from "zustand/middleware";

type Quota = { used: number; limit: number; resetsAt: string };

type State = {
  telegramId: number | null;
  model: string;
  language: string;
  persona: string;
  connectedProviders: string[];
  quota: Quota;
  setMe: (m: Partial<State>) => void;
};

export const useUserStore = create<State>()(
  persist(
    (set) => ({
      telegramId: null,
      model: "",
      language: "en",
      persona: "",
      connectedProviders: [],
      quota: { used: 0, limit: 0, resetsAt: "" },
      setMe: (m) => set(m),
    }),
    { name: "mocco.user" }
  )
);
