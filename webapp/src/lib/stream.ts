import { getInitData } from "./telegram";
import { ApiError } from "./api";

const BASE = import.meta.env.VITE_API_BASE_URL as string;

export type ChatFrame =
  | { kind: "delta"; delta: string }
  | { kind: "usage"; totalTokens: number }
  | { kind: "done" }
  | { kind: "error"; code: string; message: string };

export async function* streamChat(
  body: { messages: { role: "system" | "user" | "assistant"; content: string }[] },
  signal: AbortSignal,
): AsyncGenerator<ChatFrame> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw await ApiError.fromResponse(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const json = JSON.parse(line.slice(6));
        if (typeof json.delta === "string") yield { kind: "delta", delta: json.delta };
        else if (json.usage && typeof json.usage.total_tokens === "number") {
          yield { kind: "usage", totalTokens: json.usage.total_tokens };
        } else if (json.done) yield { kind: "done" };
        else if (json.error) yield { kind: "error", code: json.error.code, message: json.error.message };
      } catch {
        // ignore malformed frame
      }
    }
  }
}
