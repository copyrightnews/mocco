import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";
import { Toast } from "./components/Toast";

function ShellWrapper({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter shell={ShellWrapper} />
      <Toast />
    </TelegramProvider>
  );
}
