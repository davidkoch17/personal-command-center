import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { Search } from "lucide-react"
import { useDebounce } from "@/hooks/useDebounce"
import { useSearchVault } from "@/hooks/useSearch"
import { openInOs } from "@/lib/open-in-os"
import { cn } from "@/lib/utils"

/** Flat page list for quick-nav (mirrors the sidebar). */
const PAGES: { to: string; label: string }[] = [
  { to: "/", label: "home" },
  { to: "/plan", label: "plan" },
  { to: "/projects", label: "projects" },
  { to: "/ideas", label: "ideas" },
  { to: "/inbox", label: "inbox" },
  { to: "/portfolio", label: "portfolio" },
  { to: "/money", label: "money" },
  { to: "/watchlist", label: "watchlist" },
  { to: "/career", label: "career" },
  { to: "/brand", label: "brand" },
  { to: "/reading", label: "reading" },
  { to: "/background-runs", label: "background runs" },
  { to: "/settings", label: "settings" },
]

/**
 * Global command palette. Cmd/Ctrl+K opens it from anywhere: quick-nav to a page
 * (matches sidebar labels) or full-text vault search.
 */
export function SearchPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const navigate = useNavigate()
  const debounced = useDebounce(query, 250)
  const { data, isFetching } = useSearchVault(debounced)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  useEffect(() => {
    if (!open) setQuery("")
  }, [open])

  const pageMatches = PAGES.filter((p) =>
    p.label.includes(query.trim().toLowerCase()),
  )

  function goPage(to: string) {
    navigate(to)
    setOpen(false)
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm" />
        <DialogPrimitive.Content
          className={cn(
            "fixed left-1/2 top-[15%] z-[70] w-full max-w-xl -translate-x-1/2",
            "panel bg-bg-panel p-0 shadow-xl",
          )}
        >
          <DialogPrimitive.Title className="sr-only">search</DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="h-4 w-4 text-text-label" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search vault or jump to a page..."
              className="h-11 w-full bg-transparent text-sm text-text placeholder:text-text-label focus:outline-none"
            />
            <kbd className="font-mono text-[10px] text-text-label">esc</kbd>
          </div>

          <div className="max-h-[60vh] overflow-y-auto p-2">
            {pageMatches.length > 0 && (
              <div className="mb-2">
                <div className="label px-2 py-1">pages</div>
                {pageMatches.map((p) => (
                  <button
                    key={p.to}
                    type="button"
                    onClick={() => goPage(p.to)}
                    className="block w-full rounded-sm px-2 py-1.5 text-left text-sm text-text hover:bg-bg-panel-hover"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}

            {debounced.trim().length > 1 && (
              <div>
                <div className="label px-2 py-1">
                  vault{isFetching ? " · searching…" : ` · ${data?.results.length ?? 0}`}
                </div>
                {(data?.results ?? []).map((r) => (
                  <button
                    key={r.relative_path}
                    type="button"
                    onClick={() => {
                      openInOs(r.relative_path)
                      setOpen(false)
                    }}
                    className="block w-full rounded-sm px-2 py-1.5 text-left hover:bg-bg-panel-hover"
                  >
                    <div className="truncate font-mono text-xs text-text">{r.relative_path}</div>
                    <div className="truncate text-xs text-text-secondary">{r.snippet}</div>
                  </button>
                ))}
                {!isFetching && (data?.results.length ?? 0) === 0 && (
                  <p className="px-2 py-1.5 text-sm text-text-label">no matches</p>
                )}
              </div>
            )}

            {pageMatches.length === 0 && debounced.trim().length <= 1 && (
              <p className="px-2 py-2 text-sm text-text-label">
                type to search the vault, or a page name to jump
              </p>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
