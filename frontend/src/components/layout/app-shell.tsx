import { Outlet } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/toaster"
import { Sidebar } from "./sidebar"
import { Header } from "./header"
import { VoiceBar } from "./voice-bar"

/**
 * Overall layout container: fixed header, sidebar + scrollable main, and the
 * persistent voice bar pinned bottom-center. Workspace deep-dive routes render
 * outside this shell (full-screen, no sidebar).
 */
export function AppShell() {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen flex flex-col bg-bg text-text">
        <Header />
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <main className="flex-1 p-6 overflow-y-auto">
            <Outlet />
          </main>
        </div>
        <VoiceBar />
        <Toaster />
      </div>
    </TooltipProvider>
  )
}
