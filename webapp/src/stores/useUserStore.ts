import { create } from "zustand";
import { persist } from "zustand/middleware";

type State = {
  telegramId: number | null;
  model: string;
  language: string;
  persona: string;
  connectedProviders: string[];
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
      setMe: (m) => set(m),
    }),
    { name: "mocco.user" }
  )
);
