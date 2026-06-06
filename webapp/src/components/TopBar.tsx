import { useTelegramUser } from "../lib/telegram";

export function TopBar() {
  const user = useTelegramUser();
  const name = user?.first_name || "Mocco";
  return (
    <header className="flex items-center justify-between px-4 h-12 border-b border-tg-hint/20 bg-tg-secondary-bg">
      <div className="flex items-center gap-2">
        {user?.photo_url ? (
          <img src={user.photo_url} alt="" className="w-7 h-7 rounded-full" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-tg-button text-tg-button-text flex items-center justify-center text-xs font-semibold">
            {name[0]?.toUpperCase() ?? "M"}
          </div>
        )}
        <span className="font-medium text-tg-text">{name}</span>
      </div>
    </header>
  );
}
