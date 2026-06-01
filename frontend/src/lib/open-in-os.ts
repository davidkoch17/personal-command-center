import { toast } from "@/lib/toast-store"

/**
 * "Open in OS" stand-in.
 *
 * The backend has no endpoint to open a file in the host OS yet (a browser
 * cannot open arbitrary local paths for security reasons), so as a graceful
 * fallback we copy the absolute path to the clipboard and explain. Wire this to
 * a real `POST /api/system/open` once that endpoint lands (backend phase).
 */
export async function openInOs(path: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(path)
    toast.show("path copied to clipboard", {
      detail: `${path} — os-open endpoint pending`,
    })
  } catch {
    toast.error("could not copy path", path)
  }
}
