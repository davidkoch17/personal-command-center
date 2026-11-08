import { useEffect, useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/toaster"
import { UpdateBanner } from "@/components/ui/update-banner"
import { Sidebar, MobileNav } from "./sidebar"
import { Header } from "./header"
import { SearchPalette } from "./search-palette"
import { PageTransition } from "./page-transition"
import { JarvisDock } from "@/components/jarvis/jarvis-dock"

/**
 * Overall layout container: fixed header (with the small Jarvis ball), responsive
 * sidebar + scrollable main. The header ball runs the briefing flow inline — no
 * overlay (Phase 13.6: the ball IS the entire interaction). Workspace deep-dive
 * routes render outside this shell.
 *
 * Phase 13.5 retired the bottom-center voice bar in favour of the Jarvis ball.
 */
// Browser-tab titles per route ("To-dos · Command Center") so open tabs are
// distinguishable. Unknown paths fall back to the bare app name.
const PAGE_TITLES: Record<string, string> = {
  "/today": "Today",
  "/networth": "Net Worth",
  "/portfolio": "Portfolio",
  "/cashflow": "Cash Flow",
  "/projects": "Projects",
  "/todos": "To-dos",
  "/background-runs": "Background Runs",
  "/settings": "Settings",
  "/ideas": "Ideas",
  "/decision-journal": "Decision Journal",
  "/brand": "Brand",
}

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const page = PAGE_TITLES[location.pathname]
    document.title = page ? `${page} · Command Center` : "Command Center"
  }, [location.pathname])

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen flex flex-col bg-bg text-text">
        <Header onMenuClick={() => setNavOpen(true)} />
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <MobileNav open={navOpen} onClose={() => setNavOpen(false)} />
          <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8 lg:px-12 lg:py-10">
            {/* Capped width so lines and charts don't stretch on wide screens. */}
            <div className="mx-auto w-full max-w-[1200px]">
              {/* Re-key by path so each navigation re-runs the mount animation. */}
              <PageTransition key={location.pathname}>
                <Outlet />
              </PageTransition>
            </div>
          </main>
        </div>
        <Toaster />
        <UpdateBanner />
        <SearchPalette />
        <JarvisDock />
      </div>
    </TooltipProvider>
  )
}
