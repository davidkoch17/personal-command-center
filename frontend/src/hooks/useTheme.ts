import { useSyncExternalStore } from "react"

/**
 * Dark/light theme, persisted to localStorage and applied as a class on
 * <html> (Tailwind class strategy). The initial class is set pre-paint by the
 * inline script in index.html; this hook keeps React in sync and writes changes.
 */
export type Theme = "dark" | "light"

const STORAGE_KEY = "cc-theme"

function current(): Theme {
  if (typeof document === "undefined") return "dark"
  return document.documentElement.classList.contains("light") ? "light" : "dark"
}

const listeners = new Set<() => void>()

function apply(theme: Theme): void {
  const el = document.documentElement
  el.classList.remove("dark", "light")
  el.classList.add(theme)
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* private mode / storage disabled — class still applied for this session */
  }
  listeners.forEach((l) => l())
}

export function setTheme(theme: Theme): void {
  apply(theme)
}

export function toggleTheme(): void {
  apply(current() === "dark" ? "light" : "dark")
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function useTheme(): { theme: Theme; setTheme: (t: Theme) => void; toggle: () => void } {
  const theme = useSyncExternalStore(subscribe, current, () => "dark" as Theme)
  return { theme, setTheme, toggle: toggleTheme }
}
