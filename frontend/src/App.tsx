import { lazy, Suspense, type ReactNode } from "react"
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom"
import { QueryClientProvider } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AppShell } from "@/components/layout/app-shell"

import { Projects } from "@/pages/projects"
import { Ideas } from "@/pages/ideas"
import { Portfolio } from "@/pages/portfolio"
import { DecisionJournal } from "@/pages/decision-journal"
import { Brand } from "@/pages/brand"
import { BackgroundRuns } from "@/pages/background-runs"
import { Settings } from "@/pages/settings"
import { DebugJarvis } from "@/pages/debug-jarvis"
import { Chat } from "@/pages/chat"

// Workspaces are heavy (charts, dossiers) and opened on demand in a new tab —
// lazy-load them so they never weigh down the main shell bundle.
const ProjectWorkspace = lazy(() =>
  import("@/pages/workspaces/project-workspace").then((m) => ({ default: m.ProjectWorkspace })),
)
const IdeaWorkspace = lazy(() =>
  import("@/pages/workspaces/idea-workspace").then((m) => ({ default: m.IdeaWorkspace })),
)
const PortfolioWorkspace = lazy(() =>
  import("@/pages/workspaces/portfolio-workspace").then((m) => ({ default: m.PortfolioWorkspace })),
)
const MoneyWorkspace = lazy(() =>
  import("@/pages/workspaces/money-workspace").then((m) => ({ default: m.MoneyWorkspace })),
)
const WatchlistTicker = lazy(() =>
  import("@/pages/workspaces/watchlist-ticker").then((m) => ({ default: m.WatchlistTicker })),
)
const BrandVideo = lazy(() =>
  import("@/pages/workspaces/brand-video").then((m) => ({ default: m.BrandVideo })),
)

function Lazy({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-bg">
          <span className="font-mono text-sm text-text-secondary">loading workspace…</span>
        </div>
      }
    >
      {children}
    </Suspense>
  )
}

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      // v3 entry point is the Portfolio Hub pillar (Home archived — spec § f).
      { path: "/", element: <Navigate to="/portfolio" replace /> },
      // --- v3 sidebar: 2 pillars + Background Runs + Search + Settings --------
      { path: "/portfolio", element: <Portfolio /> },   // pillar 1 — Portfolio Hub
      { path: "/projects", element: <Projects /> },      // pillar 2 — Projects
      { path: "/background-runs", element: <BackgroundRuns /> },
      { path: "/settings", element: <Settings /> },
      // --- Refactored / legacy pages: off-sidebar, still reachable by URL -----
      // (Live deep-dive surfaces folded under the two pillars; kept routed so
      // links and the search palette never 404.)
      { path: "/ideas", element: <Ideas /> },               // Projects → Ideas pipeline
      { path: "/decision-journal", element: <DecisionJournal /> },
      { path: "/brand", element: <Brand /> },               // Projects → Personal Brand
      // --- v2 standalone pages folded into Portfolio Hub tabs (Phase H) -------
      // Pages archived to _archive/; legacy deep-links redirect to the tab so no
      // reachable route duplicates a Portfolio tab.
      { path: "/watchlist", element: <Navigate to="/portfolio?tab=watchlist" replace /> },
      { path: "/money", element: <Navigate to="/portfolio?tab=overview" replace /> },
      { path: "/inbox", element: <Navigate to="/portfolio?tab=captures" replace /> },
      // /plan /ventures /wealth /system: v2 super-pages archived (Phase H). Their
      // content lives in the two pillars + Background Runs + Settings; the task /
      // calendar / iCal BACKEND that /plan fronted stays (api/planner, api/tasks,
      // api/calendar) — only the duplicate page route is removed.
      // Hidden dev tool — reachable via direct URL or the Settings link, not the sidebar.
      { path: "/debug-jarvis", element: <DebugJarvis /> },
    ],
  },
  // Standalone chat window — opened in its own browser window (often on a
  // second monitor). No AppShell so it reads as a normal full chat surface.
  { path: "/chat", element: <Chat /> },
  // Hidden workspace routes — standalone full-page, no AppShell / sidebar
  // (Cockpit "deep-dive new tab" pattern).
  {
    children: [
      { path: "/workspace/project/:id", element: <Lazy><ProjectWorkspace /></Lazy> },
      { path: "/workspace/idea/:name", element: <Lazy><IdeaWorkspace /></Lazy> },
      { path: "/workspace/portfolio", element: <Lazy><PortfolioWorkspace /></Lazy> },
      { path: "/workspace/money", element: <Lazy><MoneyWorkspace /></Lazy> },
      { path: "/workspace/watchlist/:ticker", element: <Lazy><WatchlistTicker /></Lazy> },
      { path: "/workspace/brand/:id", element: <Lazy><BrandVideo /></Lazy> },
    ],
  },
])

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={150}>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
