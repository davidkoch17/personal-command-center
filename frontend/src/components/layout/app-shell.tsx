import { useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/toaster"
import { Sidebar, MobileNav } from "./sidebar"
import { Header } from "./header"
import { VoiceBar } from "./voice-bar"
import { SearchPalette } from "./search-palette"
import { PageTransition } from "./page-transition"

/**
 * Overall layout container: fixed header, responsive sidebar + scrollable main,
 * and the persistent voice bar pinned bottom-center. Workspace deep-dive routes
 * render outside this shell (full-screen, no sidebar).
 */
export function AppShell() {
  const [navOpen, setNavOpen] = useState(false)
  const location = useLocation()

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen flex flex-col bg-bg text-text">
        <Header onMenuClick={() => setNavOpen(true)} />
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <MobileNav open={navOpen} onClose={() => setNavOpen(false)} />
          <main className="flex-1 overflow-y-auto p-4 sm:p-6">
            {/* Re-key by path so each navigation re-runs the mount animation. */}
            <PageTransition key={location.pathname}>
              <Outlet />
            </PageTransition>
          </main>
        </div>
        <VoiceBar />
        <Toaster />
        <SearchPalette />
      </div>
    </TooltipProvider>
  )
}
