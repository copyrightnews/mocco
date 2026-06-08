import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";
import { AppShell } from "./components/AppShell";
import { Toast } from "./components/Toast";
import { Outlet } from "react-router-dom";

function ShellWrapper() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter shell={ShellWrapper} />
      <Toast />
    </TelegramProvider>
  );
}
