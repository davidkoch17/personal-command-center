/**
 * Tiny event bus so any control (e.g. the sidebar "search" button) can open the
 * global command palette without prop-drilling. The palette is mounted once in
 * AppShell and listens via {@link onOpenSearch}; Cmd/Ctrl+K still works directly.
 */
const OPEN_SEARCH_EVENT = "cockpit:open-search"

export function openSearch(): void {
  window.dispatchEvent(new CustomEvent(OPEN_SEARCH_EVENT))
}

export function onOpenSearch(handler: () => void): () => void {
  window.addEventListener(OPEN_SEARCH_EVENT, handler)
  return () => window.removeEventListener(OPEN_SEARCH_EVENT, handler)
}
