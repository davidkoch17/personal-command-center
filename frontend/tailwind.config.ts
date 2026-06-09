import type { Config } from "tailwindcss"

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Theme tokens resolve to CSS variables (space-separated RGB triplets)
        // defined in globals.css, so the dark/light toggle swaps the whole
        // palette by toggling a class on <html>. The `<alpha-value>` form keeps
        // Tailwind opacity modifiers working (e.g. `bg-accent-soft/20`).
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        "bg-panel": "rgb(var(--color-bg-panel) / <alpha-value>)",
        "bg-panel-hover": "rgb(var(--color-bg-panel-hover) / <alpha-value>)",
        border: "rgb(var(--color-border) / <alpha-value>)",
        "border-focus": "rgb(var(--color-border-focus) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        "accent-dim": "rgb(var(--color-accent-dim) / <alpha-value>)",
        "accent-soft": "rgb(var(--color-accent-soft) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        text: "rgb(var(--color-text) / <alpha-value>)",
        "text-secondary": "rgb(var(--color-text-secondary) / <alpha-value>)",
        "text-label": "rgb(var(--color-text-label) / <alpha-value>)",
        "text-disabled": "rgb(var(--color-text-disabled) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Courier New", "monospace"],
      },
      letterSpacing: {
        tight: "-0.01em",
        wider: "0.08em",
      },
      borderRadius: {
        DEFAULT: "8px",
        sm: "6px",
        lg: "12px",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        // Running indicator: scale 1 -> 1.1 -> 1 with a slight opacity dip.
        "pulse-dot": {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.1)", opacity: "0.55" },
        },
        // Live-feed blink: faint opacity blink.
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
        blink: "blink 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config
