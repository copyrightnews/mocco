import { create } from "zustand";

export type Message = { role: "user" | "assistant"; content: string; streaming?: boolean; error?: boolean };

type State = {
  messages: Message[];
  input: string;
  streaming: boolean;
  abort: AbortController | null;
  setInput: (s: string) => void;
  hydrate: (msgs: Message[]) => void;
  submit: () => Message[]; // returns the new messages to send
  appendUser: (content: string) => void;
  appendAssistant: () => void;
  appendDelta: (delta: string) => void;
  markComplete: () => void;
  markError: () => void;
  setAbort: (a: AbortController | null) => void;
  cancel: () => void;
  clear: () => void;
};

export const useChatStore = create<State>((set, get) => ({
  messages: [],
  input: "",
  streaming: false,
  abort: null,
  setInput: (s) => set({ input: s }),
  hydrate: (msgs) => set({ messages: msgs }),
  submit: () => {
    const { input, messages } = get();
    const userMsg: Message = { role: "user", content: input };
    const asstMsg: Message = { role: "assistant", content: "", streaming: true };
    set({ messages: [...messages, userMsg, asstMsg], input: "", streaming: true });
    return get().messages;
  },
  appendUser: (c) => set((s) => ({ messages: [...s.messages, { role: "user", content: c }] })),
  appendAssistant: () => set((s) => ({ messages: [...s.messages, { role: "assistant", content: "", streaming: true }] })),
  appendDelta: (d) =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], content: msgs[i].content + d };
          break;
        }
      }
      return { messages: msgs };
    }),
  markComplete: () =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], streaming: false };
          break;
        }
      }
      return { messages: msgs, streaming: false };
    }),
  markError: () =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], streaming: false, error: true };
          break;
        }
      }
      return { messages: msgs, streaming: false };
    }),
  setAbort: (a) => set({ abort: a }),
  cancel: () => {
    const a = get().abort;
    if (a) a.abort();
    set({ streaming: false, abort: null });
  },
  clear: () => set({ messages: [], streaming: false, abort: null }),
}));
