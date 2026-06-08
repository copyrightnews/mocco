import { ReactNode } from "react";
import { useTelegramReady, useTelegramTheme } from "../lib/telegram";

export function TelegramProvider({ children }: { children: ReactNode }) {
  useTelegramReady();
  useTelegramTheme();
  return <>{children}</>;
}
