import { create } from "zustand"

export type ToastTone = "default" | "success" | "danger"

export interface Toast {
  id: number
  message: string
  tone: ToastTone
  /** Optional secondary line (monospace), e.g. a run id or path. */
  detail?: string
}

interface ToastState {
  toasts: Toast[]
  push: (message: string, opts?: { tone?: ToastTone; detail?: string }) => number
  dismiss: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, opts) => {
    const id = nextId++
    const toast: Toast = {
      id,
      message,
      tone: opts?.tone ?? "default",
      detail: opts?.detail,
    }
    set((s) => ({ toasts: [...s.toasts, toast] }))
    return id
  },
  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

/** Imperative helper so non-component code can fire a toast. */
export const toast = {
  show: (message: string, opts?: { tone?: ToastTone; detail?: string }) =>
    useToastStore.getState().push(message, opts),
  success: (message: string, detail?: string) =>
    useToastStore.getState().push(message, { tone: "success", detail }),
  error: (message: string, detail?: string) =>
    useToastStore.getState().push(message, { tone: "danger", detail }),
}
