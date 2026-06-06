import { create } from "zustand";
import { persist } from "zustand/middleware";

type State = {
  language: string;
  persona: string;
  gender: string;
  age: number | null;
  location: string;
  occupation: string;
  interests: string[];
  timezone: string;
  setAll: (p: Partial<State>) => void;
};

export const useProfileStore = create<State>()(
  persist(
    (set) => ({
      language: "en",
      persona: "",
      gender: "",
      age: null,
      location: "",
      occupation: "",
      interests: [],
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      setAll: (p) => set(p),
    }),
    { name: "mocco.profile" }
  )
);
