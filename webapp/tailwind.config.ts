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
      },
      fontFamily: {
        sans: ["var(--tg-font, system-ui)", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
