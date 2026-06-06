import { useLocation, useNavigate } from "react-router-dom";
import { useTelegramUser } from "../lib/telegram";
import { useEffect } from "react";

export function TopBar() {
  const user = useTelegramUser();
  const location = useLocation();
  const navigate = useNavigate();
  const isHome = location.pathname === "/";
  const onProfile = location.pathname === "/profile";
  const initials = (user?.first_name?.[0] || "M").toUpperCase();

  // Wire Telegram native back button on non-home routes
  useEffect(() => {
    const wa = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
    if (!wa) return;
    if (isHome) {
      wa.BackButton.hide();
      return;
    }
    wa.BackButton.show();
    const handler = () => navigate("/");
    wa.BackButton.onClick(handler);
    return () => wa.BackButton.offClick(handler);
  }, [isHome, navigate]);

  function close() {
    const wa = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
    if (wa) wa.close();
  }

  if (!isHome) {
    return (
      <header className="relative flex items-center justify-center h-14 bg-tg-bg">
        <button
          onClick={() => navigate("/")}
          className="absolute left-4 text-tg-link text-[17px] flex items-center gap-0.5 active:opacity-50"
          aria-label="Back"
        >
          <svg width="12" height="20" viewBox="0 0 12 20" fill="none" aria-hidden="true">
            <path d="M10 2L2 10L10 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Back</span>
        </button>
        <div className="flex flex-col items-center leading-tight">
          <span className="text-[15px] font-semibold text-tg-text">Mocco</span>
          <span className="text-[11px] text-tg-hint">mini app</span>
        </div>
      </header>
    );
  }

  return (
    <header className="relative flex items-center justify-center h-14 bg-tg-bg">
      <button
        onClick={close}
        className="absolute left-4 text-tg-link text-[17px] active:opacity-50"
        aria-label="Close"
      >
        Close
      </button>
      <div className="flex flex-col items-center leading-tight">
        <span className="text-[15px] font-semibold text-tg-text">Mocco</span>
        <span className="text-[11px] text-tg-hint">mini app</span>
      </div>
      <button
        onClick={() => (onProfile ? navigate("/") : navigate("/profile"))}
        className="absolute right-4 w-9 h-9 rounded-full bg-tg-secondary-bg shadow-pill flex items-center justify-center text-[13px] font-semibold text-tg-text active:scale-95 transition-transform"
        aria-label={onProfile ? "Home" : "Profile"}
      >
        {user?.photo_url ? (
          <img src={user.photo_url} alt="" className="w-full h-full rounded-full object-cover" />
        ) : (
          initials
        )}
      </button>
    </header>
  );
}
