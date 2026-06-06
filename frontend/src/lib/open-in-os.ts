import { api } from "@/lib/api"
import { toast } from "@/lib/toast-store"

/**
 * Open a vault file in the host OS via `POST /api/system/open` (the backend
 * runs on David's machine, so it can do what the browser sandbox can't).
 *
 * If the backend can't resolve or open the path, fall back to copying it to
 * the clipboard so the user can still get to the file by hand.
 */
export async function openInOs(path: string): Promise<void> {
  try {
    const res = await api.post<{ ok: boolean; opened: string }>("/api/system/open", { path })
    toast.show("opened in OS", { detail: res.opened })
  } catch {
    try {
      await navigator.clipboard.writeText(path)
      toast.show("could not open — path copied to clipboard", { detail: path })
    } catch {
      toast.error("could not open file", path)
    }
  }
}
