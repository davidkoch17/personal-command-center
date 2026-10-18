/**
 * Copy text to the clipboard, falling back to a hidden-textarea
 * `execCommand("copy")` when the async Clipboard API is missing or denied.
 *
 * The fallback matters for the phone: over Tailscale the app is served on
 * plain http://, which is not a secure context, so `navigator.clipboard` is
 * undefined there. Must be called from a user gesture (a click handler).
 * Returns whether the copy succeeded.
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // permission denied — try the legacy path below
  }
  const ta = document.createElement("textarea")
  ta.value = text
  ta.setAttribute("readonly", "")
  ta.style.position = "fixed"
  ta.style.opacity = "0"
  document.body.appendChild(ta)
  ta.select()
  ta.setSelectionRange(0, text.length) // iOS Safari ignores select() alone
  try {
    return document.execCommand("copy")
  } catch {
    return false
  } finally {
    document.body.removeChild(ta)
  }
}
