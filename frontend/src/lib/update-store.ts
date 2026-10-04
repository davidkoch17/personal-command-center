import { create } from "zustand"

interface UpdateState {
  available: boolean
  markAvailable: () => void
}

/** Chunk 9.8 — set when a new deploy's service worker has taken over an
 * already-open tab (see main.tsx's controllerchange listener). Separate from
 * the generic toast-store: this needs to persist until the user acts (not
 * auto-dismiss after 5s like a normal toast) and its click reloads the page
 * rather than just dismissing. */
export const useUpdateStore = create<UpdateState>((set) => ({
  available: false,
  markAvailable: () => set({ available: true }),
}))
