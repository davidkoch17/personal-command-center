import { createBrowserRouter, RouterProvider } from "react-router-dom"
import { QueryClientProvider } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import { AppShell } from "@/components/layout/app-shell"

import { Home } from "@/pages/home"
import { Tasks } from "@/pages/tasks"
import { Projects } from "@/pages/projects"
import { Ideas } from "@/pages/ideas"
import { Inbox } from "@/pages/inbox"
import { Portfolio } from "@/pages/portfolio"
import { Money } from "@/pages/money"
import { Watchlist } from "@/pages/watchlist"
import { Brand } from "@/pages/brand"
import { Career } from "@/pages/career"
import { Reading } from "@/pages/reading"
import { BackgroundRuns } from "@/pages/background-runs"
import { Settings } from "@/pages/settings"
import { Calendar } from "@/pages/calendar"

import { ProjectWorkspace } from "@/pages/workspaces/project-workspace"
import { IdeaWorkspace } from "@/pages/workspaces/idea-workspace"
import { PortfolioWorkspace } from "@/pages/workspaces/portfolio-workspace"
import { MoneyWorkspace } from "@/pages/workspaces/money-workspace"
import { WatchlistTicker } from "@/pages/workspaces/watchlist-ticker"
import { BrandVideo } from "@/pages/workspaces/brand-video"
import { CareerWorkspace } from "@/pages/workspaces/career-workspace"

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/tasks", element: <Tasks /> },
      { path: "/projects", element: <Projects /> },
      { path: "/ideas", element: <Ideas /> },
      { path: "/inbox", element: <Inbox /> },
      { path: "/portfolio", element: <Portfolio /> },
      { path: "/money", element: <Money /> },
      { path: "/watchlist", element: <Watchlist /> },
      { path: "/brand", element: <Brand /> },
      { path: "/career", element: <Career /> },
      { path: "/reading", element: <Reading /> },
      { path: "/background-runs", element: <BackgroundRuns /> },
      { path: "/settings", element: <Settings /> },
      { path: "/calendar", element: <Calendar /> },
    ],
  },
  // Hidden workspace routes — standalone full-page, no AppShell / sidebar
  // (Cockpit "deep-dive new tab" pattern).
  {
    children: [
      { path: "/workspace/project/:id", element: <ProjectWorkspace /> },
      { path: "/workspace/idea/:name", element: <IdeaWorkspace /> },
      { path: "/workspace/portfolio", element: <PortfolioWorkspace /> },
      { path: "/workspace/money", element: <MoneyWorkspace /> },
      { path: "/workspace/watchlist/:ticker", element: <WatchlistTicker /> },
      { path: "/workspace/brand/:id", element: <BrandVideo /> },
      { path: "/workspace/career", element: <CareerWorkspace /> },
    ],
  },
])

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
