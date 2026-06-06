import { useEffect, useState, useCallback } from "react";

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string;
        initDataUnsafe: { user?: TelegramUser };
        ready: () => void;
        expand: () => void;
        close: () => void;
        themeParams: ThemeParams;
        MainButton: {
          setText: (t: string) => void;
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
          showProgress: (leave: boolean) => void;
          hideProgress: () => void;
        };
        BackButton: {
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
        };
        HapticFeedback: {
          impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
          notificationOccurred: (t: "success" | "warning" | "error") => void;
          selectionChanged: () => void;
        };
        onEvent: (e: string, cb: () => void) => void;
        offEvent: (e: string, cb: () => void) => void;
      };
    };
  }
}

export type TelegramUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
};

export type ThemeParams = {
  bg_color?: string;
  secondary_bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
};

function getWA() {
  return typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
}

export function getInitData(): string {
  return getWA()?.initData ?? "";
}

export function useTelegramUser(): TelegramUser | null {
  const [user, setUser] = useState<TelegramUser | null>(null);
  useEffect(() => {
    setUser(getWA()?.initDataUnsafe.user ?? null);
  }, []);
  return user;
}

const DEFAULTS: Required<ThemeParams> = {
  bg_color: "#ffffff",
  secondary_bg_color: "#f4f4f5",
  text_color: "#0f172a",
  hint_color: "#6b7280",
  link_color: "#2563eb",
  button_color: "#2563eb",
  button_text_color: "#ffffff",
};

function applyTheme(t: ThemeParams) {
  const root = document.documentElement;
  const merged = { ...DEFAULTS, ...t };
  root.style.setProperty("--tg-bg", merged.bg_color);
  root.style.setProperty("--tg-secondary-bg", merged.secondary_bg_color);
  root.style.setProperty("--tg-text", merged.text_color);
  root.style.setProperty("--tg-hint", merged.hint_color);
  root.style.setProperty("--tg-link", merged.link_color);
  root.style.setProperty("--tg-button", merged.button_color);
  root.style.setProperty("--tg-button-text", merged.button_text_color);
}

export function useTelegramTheme(): void {
  useEffect(() => {
    const wa = getWA();
    if (!wa) {
      applyTheme(DEFAULTS);
      return;
    }
    applyTheme(wa.themeParams);
    const handler = () => applyTheme(wa.themeParams);
    wa.onEvent("themeChanged", handler);
    return () => {
      wa.offEvent("themeChanged", handler);
    };
  }, []);
}

export function useTelegramReady(): void {
  useEffect(() => {
    const wa = getWA();
    if (!wa) return;
    wa.ready();
    wa.expand();
  }, []);
}

export function useMainButton(label: string | null, onClick: () => void, deps: unknown[] = []) {
  useEffect(() => {
    const wa = getWA();
    if (!wa) return;
    if (!label) {
      wa.MainButton.hide();
      return;
    }
    wa.MainButton.setText(label);
    wa.MainButton.show();
    wa.MainButton.onClick(onClick);
    return () => {
      wa.MainButton.offClick(onClick);
      wa.MainButton.hide();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export function useBackButton(onClick: () => void, show: boolean) {
  useEffect(() => {
    const wa = getWA();
    if (!wa) return;
    if (!show) {
      wa.BackButton.hide();
      return;
    }
    wa.BackButton.show();
    wa.BackButton.onClick(onClick);
    return () => {
      wa.BackButton.offClick(onClick);
      wa.BackButton.hide();
    };
  }, [onClick, show]);
}

export const haptic = {
  impact: (style: "light" | "medium" | "heavy" = "light") => getWA()?.HapticFeedback.impactOccurred(style),
  notify: (t: "success" | "warning" | "error") => getWA()?.HapticFeedback.notificationOccurred(t),
};
