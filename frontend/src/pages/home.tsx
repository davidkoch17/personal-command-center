import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { DecisionAlerts } from "@/components/finance/decision-alerts"
import { FocusAreaCard } from "@/components/home/focus-area-card"
import { BrainSystemCard } from "@/components/home/brain-system-card"
import { HardDeadlineBar } from "@/components/home/hard-deadline-bar"
import { AskClaudeBar } from "@/components/home/ask-claude-bar"
import { PortfolioTopLine } from "@/components/home/portfolio-topline"
import { WatchlistSignals } from "@/components/home/watchlist-signals"
import { NotgroschenInbox } from "@/components/home/notgroschen-inbox"
import { TasksOverview } from "@/components/home/tasks-overview"
import { SkillsAgentsDirectory } from "@/components/home/skills-directory"
import { ManualTasksCard } from "@/components/home/ManualTasksCard"
import { WeekStrip } from "@/components/calendar/week-strip"
import { useFocusAreas } from "@/hooks/useHome"
import { useCalendar } from "@/hooks/useCalendar"
import { isoDate } from "@/lib/utils"

/**
 * Home tab — Item #4, per the locked Home_Redesign_Spec.md (2026-06-05).
 *
 * A STATE view, not a working surface. Three zones top-to-bottom:
 * - NOW:    7 focus area cards + hard deadlines bar — what do I act on?
 * - STATE:  portfolio + decision alerts + watchlist signals + notgroschen/inbox
 * - GROUND: week calendar + tasks overview + skills & agents directory
 *
 * Between NOW and STATE sits the Ask Claude bar (text + voice via Jarvis).
 * Removed per spec: streaks, recent vault activity, principle, weather, Whoop.
 */
export function Home() {
  return (
    <div className="space-y-6">
      <HomeHeader />

      {/* --- Zone 1: NOW ------------------------------------------------- */}
      <section className="space-y-3">
        <ZoneLabel>now</ZoneLabel>
        <FocusAreasRow />
        <HardDeadlineBar />
      </section>

      {/* --- Ask Claude bar ------------------------------------------------ */}
      <AskClaudeBar />

      {/* --- Zone 2: STATE ------------------------------------------------- */}
      <section className="space-y-3">
        <ZoneLabel>state</ZoneLabel>
        <div className="grid gap-4 md:grid-cols-2">
          <PortfolioTopLine />
          {/* Decision alerts preserved from the old dashboard (rebalance /
              concentration / harvest counts) — also read aloud by Jarvis. */}
          <DecisionAlerts />
          <WatchlistSignals />
          <NotgroschenInbox />
        </div>
      </section>

      {/* --- Zone 3: GROUND ------------------------------------------------ */}
      <section className="space-y-3">
        <ZoneLabel>ground</ZoneLabel>
        <WeekCalendarPanel />
        <div className="grid gap-4 md:grid-cols-2">
          <TasksOverview />
          <SkillsAgentsDirectory />
        </div>
      </section>

      {/* --- Awaiting your input (after GROUND; auto-hides when all clear) -- */}
      <ManualTasksCard />
    </div>
  )
}

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "good morning, david"
  if (h < 18) return "good afternoon, david"
  return "good evening, david"
}

function HomeHeader() {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <h1 className="text-3xl font-semibold tracking-tight">{greeting()}</h1>
      <span className="font-mono text-sm text-text-secondary">{isoDate()}</span>
    </div>
  )
}

function ZoneLabel({ children }: { children: string }) {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-label">
      {children}
    </div>
  )
}

// --- NOW: 7 focus area cards --------------------------------------------------
function FocusAreasRow() {
  const { data, isLoading } = useFocusAreas()

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
        {Array.from({ length: 7 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    )
  }
  const cards = data?.cards ?? []
  if (cards.length === 0) return null

  // 7-up row on wide desktop; reflows 2-4 per row on smaller viewports.
  // The Brain/System slot renders its dedicated real-data card
  // (Brain_System_Card_Spec.md); the rest use the generic focus card.
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
      {cards.map((c) =>
        c.key === "brain" ? <BrainSystemCard key={c.key} /> : <FocusAreaCard key={c.key} card={c} />,
      )}
    </div>
  )
}

// --- GROUND: Mo–Su week calendar (shared WeekStrip component) ------------------
function WeekCalendarPanel() {
  const { data, isLoading } = useCalendar(7)
  const navigate = useNavigate()

  return (
    <Panel title="this week" statusDotColor="accent">
      {isLoading ? (
        <Skeleton className="h-28" />
      ) : !data?.configured ? (
        <p className="text-sm text-text-label">calendar not configured</p>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[640px]">
            <WeekStrip
              events={data.events}
              start="monday"
              onSelect={() => navigate("/calendar")}
            />
          </div>
        </div>
      )}
    </Panel>
  )
}
