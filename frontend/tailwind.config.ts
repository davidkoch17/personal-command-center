import type { Config } from "tailwindcss"

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0E13",
        "bg-panel": "#11161D",
        "bg-panel-hover": "#161C25",
        border: "#1F262E",
        "border-focus": "#2563EB",
        accent: "#2563EB",
        "accent-dim": "#1D4ED8",
        "accent-soft": "#1E3A8A",
        success: "#10B981",
        danger: "#EF4444",
        warning: "#F59E0B",
        text: "#E4E6EB",
        "text-secondary": "#8A929E",
        "text-label": "#5C6470",
        "text-disabled": "#3F4651",
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
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config
