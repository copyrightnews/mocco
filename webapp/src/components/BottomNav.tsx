import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "Agent", icon: "✦" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

export function BottomNav() {
  return (
    <nav className="flex items-center justify-around h-14 border-t border-tg-hint/20 bg-tg-secondary-bg">
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          end={it.to === "/"}
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 text-xs ${
              isActive ? "text-tg-button" : "text-tg-hint"
            }`
          }
        >
          <span className="text-lg leading-none">{it.icon}</span>
          <span>{it.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
