import { AppRouter } from "./router";
import { TelegramProvider } from "./components/TelegramProvider";

export default function App() {
  return (
    <TelegramProvider>
      <AppRouter />
    </TelegramProvider>
  );
}
