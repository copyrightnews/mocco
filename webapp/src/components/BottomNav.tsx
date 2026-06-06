import { NavLink, useLocation } from "react-router-dom";

const items = [
  {
    to: "/",
    label: "Agent",
    icon: (active: boolean, tone: "dark" | "light") => {
      const stroke = active ? "#007aff" : tone === "dark" ? "rgba(255,255,255,0.7)" : "#6e6e73";
      return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"
            fill={active ? "#007aff" : "none"}
            stroke={stroke}
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path
            d="M19 16l.7 1.9L21.6 18.5l-1.9.7L19 21l-.7-1.8-1.9-.7 1.9-.6L19 16z"
            fill={active ? "#007aff" : "none"}
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
        </svg>
      );
    },
  },
  {
    to: "/profile",
    label: "Profile",
    icon: (active: boolean, tone: "dark" | "light") => {
      const stroke = active ? "#007aff" : tone === "dark" ? "rgba(255,255,255,0.7)" : "#6e6e73";
      return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="9" r="3.5" stroke={stroke} strokeWidth="1.6" />
          <path
            d="M5 20c.8-3.2 3.6-5 7-5s6.2 1.8 7 5"
            stroke={stroke}
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      );
    },
  },
];

export function BottomNav() {
  const location = useLocation();
  const tone: "dark" | "light" = location.pathname === "/" ? "dark" : "light";
  const navCls =
    tone === "dark"
      ? "flex items-stretch h-16 bg-black/30 backdrop-blur-xl border-t border-white/10 pb-[env(safe-area-inset-bottom)]"
      : "flex items-stretch h-16 bg-tg-bg/85 backdrop-blur-xl border-t border-tg-divider pb-[env(safe-area-inset-bottom)]";
  const labelActiveCls = "text-tg-link";
  const labelIdleCls = tone === "dark" ? "text-white/70" : "text-tg-hint";

  return (
    <nav className={navCls}>
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          end={it.to === "/"}
          className="flex-1 flex flex-col items-center justify-center gap-1"
        >
          {({ isActive }) => (
            <>
              {it.icon(isActive, tone)}
              <span className={`text-[11px] font-medium ${isActive ? labelActiveCls : labelIdleCls}`}>
                {it.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
