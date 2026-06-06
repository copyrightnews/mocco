import { NavLink } from "react-router-dom";

const items = [
  {
    to: "/",
    label: "Agent",
    icon: (active: boolean) => (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"
          fill={active ? "#007aff" : "none"}
          stroke={active ? "#007aff" : "#6e6e73"}
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path
          d="M19 16l.7 1.9L21.6 18.5l-1.9.7L19 21l-.7-1.8-1.9-.7 1.9-.6L19 16z"
          fill={active ? "#007aff" : "none"}
          stroke={active ? "#007aff" : "#6e6e73"}
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    to: "/profile",
    label: "Profile",
    icon: (active: boolean) => (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="9" r="3.5" stroke={active ? "#007aff" : "#6e6e73"} strokeWidth="1.6" />
        <path
          d="M5 20c.8-3.2 3.6-5 7-5s6.2 1.8 7 5"
          stroke={active ? "#007aff" : "#6e6e73"}
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
];

export function BottomNav() {
  return (
    <nav className="flex items-stretch h-16 bg-black/30 backdrop-blur-xl border-t border-white/10 pb-[env(safe-area-inset-bottom)]">
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          end={it.to === "/"}
          className="flex-1 flex flex-col items-center justify-center gap-1"
        >
          {({ isActive }) => (
            <>
              {it.icon(isActive)}
              <span className={`text-[11px] font-medium ${isActive ? "text-tg-link" : "text-tg-hint"}`}>
                {it.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
