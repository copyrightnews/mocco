import { getInitData } from "./telegram";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public extra: Record<string, unknown> = {}) {
    super(message);
  }
  static async fromResponse(res: Response): Promise<ApiError> {
    let body: any = null;
    try { body = await res.json(); } catch { /* ignore */ }
    const err = body?.error || {};
    return new ApiError(res.status, err.code || `http_${res.status}`, err.message || res.statusText, err);
  }
}

const BASE = import.meta.env.VITE_API_BASE_URL as string;

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": getInitData(),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) throw await ApiError.fromResponse(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
