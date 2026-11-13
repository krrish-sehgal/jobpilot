import type { Config } from "tailwindcss";

// Colors are CSS variables (see globals.css) holding "R G B" triplets so that
// light/dark switching is a single attribute change and Tailwind opacity
// modifiers (bg-brand/10) keep working.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: token("paper"),
        surface: token("surface"),
        sunken: token("sunken"),
        ink: token("ink"),
        muted: token("muted"),
        line: token("line"),
        brand: token("brand"),
        "brand-ink": token("brand-ink"),
        signal: token("signal"),
        good: token("good"),
        bad: token("bad"),
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      boxShadow: {
        card: "0 1px 0 rgb(var(--line) / 0.6), 0 8px 24px -12px rgb(var(--ink) / 0.18)",
      },
      keyframes: {
        rise: { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        blink: { "50%": { opacity: "0" } },
      },
      animation: {
        rise: "rise 0.35s ease-out both",
        blink: "blink 1s steps(2) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
