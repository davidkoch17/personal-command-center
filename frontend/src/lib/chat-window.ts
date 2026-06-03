/**
 * Opens the in-app Claude chat (`/chat`) as a *separate browser window*, placed
 * on the second monitor when one is connected, otherwise maximised on the
 * current screen.
 *
 * Second-screen placement uses the Window Management API (`getScreenDetails`),
 * which Chrome/Edge gate behind a one-time "manage windows on all your displays"
 * permission — calling it triggers that prompt. If the API is unavailable or the
 * permission is denied, we fall back to a maximised popup on the current screen.
 *
 * We keep a single chat window: a module-level handle means re-clicking the dock
 * focuses the existing window (preserving its live conversation) instead of
 * spawning a second one.
 */

let chatWin: Window | null = null

interface ScreenInfo {
  availLeft: number
  availTop: number
  availWidth: number
  availHeight: number
  left: number
  top: number
  isInternal?: boolean
}

interface ScreenDetails {
  screens: ScreenInfo[]
  currentScreen: ScreenInfo
}

/** Pick a screen that isn't the one this window is currently on, if any. */
function pickOtherScreen(details: ScreenDetails): ScreenInfo | null {
  const cur = details.currentScreen
  const other = details.screens.find(
    (s) => s.left !== cur.left || s.top !== cur.top,
  )
  return other ?? null
}

async function trySecondScreen(url: string): Promise<Window | null> {
  const getScreenDetails = (
    window as unknown as { getScreenDetails?: () => Promise<ScreenDetails> }
  ).getScreenDetails
  if (typeof getScreenDetails !== "function") return null
  try {
    const details = await getScreenDetails.call(window)
    const target = pickOtherScreen(details)
    if (!target) return null
    const features = [
      "popup=yes",
      `left=${target.availLeft}`,
      `top=${target.availTop}`,
      `width=${target.availWidth}`,
      `height=${target.availHeight}`,
    ].join(",")
    const w = window.open(url, "cc-chat", features)
    if (w) {
      // Some browsers ignore left/top in features for cross-screen moves;
      // moveTo/resizeTo after open is the reliable path.
      try {
        w.moveTo(target.availLeft, target.availTop)
        w.resizeTo(target.availWidth, target.availHeight)
      } catch {
        /* best effort */
      }
    }
    return w
  } catch {
    // Permission denied / unsupported → caller falls back.
    return null
  }
}

function openMaximised(url: string): Window | null {
  const features = [
    "popup=yes",
    "left=0",
    "top=0",
    `width=${window.screen.availWidth}`,
    `height=${window.screen.availHeight}`,
  ].join(",")
  return window.open(url, "cc-chat", features)
}

/**
 * Open (or focus) the chat window. `page` is the dashboard path the user opened
 * it from, forwarded so the chat is context-aware.
 */
export async function openChatWindow(page?: string): Promise<Window | null> {
  if (chatWin && !chatWin.closed) {
    chatWin.focus()
    return chatWin
  }
  const url = `/chat${page ? `?page=${encodeURIComponent(page)}` : ""}`
  const win = (await trySecondScreen(url)) ?? openMaximised(url)
  if (win) win.focus()
  chatWin = win
  return win
}
