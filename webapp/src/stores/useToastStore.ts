import { create } from "zustand";

export type Toast = { id: string; type: "success" | "info" | "warning" | "error"; text: string; sticky?: boolean };

type State = {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">) => void;
  remove: (id: string) => void;
};

export const useToastStore = create<State>((set, get) => ({
  toasts: [],
  push: (t) => {
    const id = Math.random().toString(36).slice(2);
    set((s) => ({ toasts: [...s.toasts, { id, ...t }] }));
    if (!t.sticky) setTimeout(() => get().remove(id), 4000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
