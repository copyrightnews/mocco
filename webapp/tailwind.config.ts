import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "tg-bg": "var(--tg-bg)",
        "tg-secondary-bg": "var(--tg-secondary-bg)",
        "tg-text": "var(--tg-text)",
        "tg-hint": "var(--tg-hint)",
        "tg-link": "var(--tg-link)",
        "tg-button": "var(--tg-button)",
        "tg-button-text": "var(--tg-button-text)",
        "tg-divider": "var(--tg-divider)",
      },
      fontFamily: {
        sans: ["var(--tg-font, system-ui)", "sans-serif"],
      },
      borderRadius: {
        card: "24px",
        sheet: "28px",
      },
      boxShadow: {
        card: "0 2px 12px rgba(0, 0, 0, 0.06)",
        sheet: "0 -8px 32px rgba(0, 0, 0, 0.12)",
        pill: "0 2px 8px rgba(0, 0, 0, 0.04)",
      },
    },
  },
  plugins: [],
} satisfies Config;
