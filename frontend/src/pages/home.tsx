import { useState } from "react"
import { JarvisBall } from "@/components/jarvis/jarvis-ball"
import { useJarvisBriefing } from "@/hooks/useJarvisBriefing"
import { DailyPrioritiesPanel } from "@/components/home/DailyPrioritiesPanel"
import { Panel } from "@/components/ui/panel"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { TaskCheck } from "@/components/ui/task-check"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { StatusDot } from "@/components/ui/status-dot"
import { NumberDisplay } from "@/components/ui/number-display"
import { ProjectCard } from "@/components/cards/project-card"
import { BucketAllocation } from "@/components/finance/bucket-allocation"
import { OptimizationSignals } from "@/components/finance/optimization-signals"
import { TransactionForm } from "@/components/finance/transaction-form"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  useTasks,
  useToggleTask,
  useHardDates,
  usePrioritySuggestion,
  type TasksBySection,
} from "@/hooks/useTasks"
import { useInbox, useInboxCapture } from "@/hooks/useInbox"
import { useProjects } from "@/hooks/useProjects"
import { usePortfolioSnapshot, useMoneySnapshot, useWatchlist } from "@/hooks/useFinance"
import { useCalendar } from "@/hooks/useCalendar"
import { useRunSkill, useTaxScenario } from "@/hooks/useSkills"
import { useSearchVault } from "@/hooks/useSearch"
import { useDebounce } from "@/hooks/useDebounce"
import { formatBoth } from "@/lib/dates"
import { openInOs } from "@/lib/open-in-os"
import { isoDate } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "good morning, david"
  if (h < 18) return "good afternoon, david"
  return "good evening, david"
}

export function Home() {
  const { state, subtitle, trigger, triggerWithText } = useJarvisBriefing()
  const [textInput, setTextInput] = useState("")

  return (
    <div className="space-y-6">
      <HomeHeader />

      {/* Morning anchor: Claude-suggested priorities → curated daily todo list. */}
      <DailyPrioritiesPanel />

      <SearchBar />

      {/* Central Jarvis ball — the entire briefing UX lives here. Click to start;
          the ball's state + subtitle telegraph what Jarvis is doing. No overlay.
          Below it, a text input offers a typed alternative to voice. */}
      <div className="my-12 flex flex-col items-center gap-3">
        <JarvisBall size="large" state={state} onClick={trigger} />
        {!subtitle && (
          <p className="font-mono text-xs uppercase tracking-wider text-text-secondary">
            click for your briefing
          </p>
        )}

        {/* Typed command — paste/type a prompt as an alternative to speaking. */}
        <div className="mt-2 w-full max-w-xl">
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && textInput.trim()) {
                void triggerWithText(textInput.trim())
                setTextInput("")
              }
            }}
            placeholder="or type a command for Jarvis..."
            className="w-full rounded-lg border border-border bg-bg-panel px-4 py-3 font-mono text-sm text-text placeholder:text-text-label focus:border-accent focus:outline-none disabled:opacity-50"
            disabled={state !== "idle"}
          />
        </div>

        {/* Live captions — large, panelled, and held for the whole utterance. */}
        {subtitle && (
          <div className="mt-2 w-full max-w-3xl animate-fade-in">
            <div className="rounded-lg border border-border bg-bg-panel px-6 py-4">
              <p
                className={`font-mono text-base leading-relaxed ${
                  state === "speaking" ? "text-text" : "text-text-secondary"
                }`}
              >
                {subtitle}
              </p>
            </div>
          </div>
        )}
      </div>

      <QuickRun />
      <div className="grid gap-4 lg:grid-cols-2">
        <TodayPanel />
        <QuickCapture />
      </div>
      <PriorityPanel />
      <div className="grid gap-4 lg:grid-cols-2">
        <NextWeekPanel />
        <BiggerItemsPanel />
      </div>
      <ProjectsRow />
      <FinancesRow />
      <SignalsRow />
    </div>
  )
}

// --- Header + hard dates ----------------------------------------------------
function HomeHeader() {
  const { data: hardDates } = useHardDates()

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">{greeting()}</h1>
        <span className="font-mono text-sm text-text-secondary">{isoDate()}</span>
      </div>
      {hardDates && hardDates.length > 0 && (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          {hardDates.map((d) => (
            <div
              key={`${d.date}-${d.label}`}
              className="flex shrink-0 items-center gap-2 rounded-sm border border-border bg-bg-panel px-2.5 py-1"
            >
              <span className="text-xs text-text-secondary">{d.label}</span>
              <span className="font-mono text-xs text-accent tabular-nums">
                {formatBoth(d.date)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --- Search -----------------------------------------------------------------
function SearchBar() {
  const [query, setQuery] = useState("")
  const debounced = useDebounce(query, 300)
  const { data, isFetching } = useSearchVault(debounced)
  const show = debounced.trim().length > 1

  return (
    <div className="space-y-2">
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="search the vault..."
      />
      {show && (
        <Panel
          title="results"
          meta={isFetching ? "searching..." : `${data?.results.length ?? 0} hits`}
          statusDotColor="accent"
        >
          {!data || data.results.length === 0 ? (
            <p className="text-sm text-text-label">
              {isFetching ? "searching..." : "no matches"}
            </p>
          ) : (
            <div className="space-y-1">
              {data.results.map((r) => (
                <button
                  key={r.relative_path}
                  type="button"
                  onClick={() => openInOs(r.relative_path)}
                  className="block w-full rounded-sm px-2 py-1.5 text-left hover:bg-bg-panel-hover"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs text-text">
                      {r.relative_path}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-text-label">
                      {r.match_count}×
                    </span>
                  </div>
                  <p className="truncate text-xs text-text-secondary">{r.snippet}</p>
                </button>
              ))}
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}

// --- Quick run --------------------------------------------------------------
function QuickRun() {
  const runSkill = useRunSkill()
  const taxScenario = useTaxScenario()
  const [earningsOpen, setEarningsOpen] = useState(false)
  const [taxOpen, setTaxOpen] = useState(false)
  const [askOpen, setAskOpen] = useState(false)
  const [txOpen, setTxOpen] = useState(false)

  function started(runId?: string) {
    toast.success("started in background — see background runs", runId)
  }

  return (
    <Panel title="quick run" statusDotColor="accent">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <Button
          variant="secondary"
          onClick={() =>
            runSkill.mutate(
              { skill: "market_researcher", label: "Market research" },
              {
                onSuccess: (r) => started(r.run_id),
                onError: (e) => toast.error("failed to start", String(e)),
              },
            )
          }
          disabled={runSkill.isPending}
        >
          run market research
        </Button>
        <Button variant="secondary" onClick={() => setEarningsOpen(true)}>
          earnings reviewer
        </Button>
        <Button variant="secondary" onClick={() => setTaxOpen(true)}>
          tax scenario
        </Button>
        <Button variant="secondary" onClick={() => setAskOpen(true)}>
          ask claude
        </Button>
        <Button variant="secondary" onClick={() => setTxOpen(true)}>
          log transaction
        </Button>
      </div>

      <Dialog open={txOpen} onOpenChange={setTxOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>log transaction</DialogTitle>
          </DialogHeader>
          <TransactionForm onDone={() => setTxOpen(false)} />
        </DialogContent>
      </Dialog>

      <PromptDialog
        open={earningsOpen}
        onOpenChange={setEarningsOpen}
        title="earnings reviewer"
        label="ticker"
        placeholder="e.g. ASML"
        multiline={false}
        onSubmit={(ticker) =>
          runSkill.mutate(
            { skill: "earnings_reviewer", args: { ticker }, label: `Earnings ${ticker}` },
            {
              onSuccess: (r) => started(r.run_id),
              onError: (e) => toast.error("failed to start", String(e)),
            },
          )
        }
      />
      <PromptDialog
        open={taxOpen}
        onOpenChange={setTaxOpen}
        title="tax scenario"
        label="scenario"
        placeholder="describe the scenario..."
        multiline
        onSubmit={(text) =>
          taxScenario.mutate(
            { scenario_description: text },
            {
              onSuccess: (r) => started(r.run_id),
              onError: (e) => toast.error("failed to start", String(e)),
            },
          )
        }
      />
      <PromptDialog
        open={askOpen}
        onOpenChange={setAskOpen}
        title="ask claude"
        label="question"
        placeholder="ask anything about your vault..."
        multiline
        onSubmit={(question) =>
          runSkill.mutate(
            { skill: "ask_anything", args: { question }, label: "Ask claude" },
            {
              onSuccess: (r) => started(r.run_id),
              onError: (e) => toast.error("failed to start", String(e)),
            },
          )
        }
      />
    </Panel>
  )
}

function PromptDialog({
  open,
  onOpenChange,
  title,
  label,
  placeholder,
  multiline,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  label: string
  placeholder: string
  multiline: boolean
  onSubmit: (value: string) => void
}) {
  const [value, setValue] = useState("")
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o)
        if (!o) setValue("")
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="label mb-1">{label}</div>
        {multiline ? (
          <Textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            rows={4}
          />
        ) : (
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            mono
          />
        )}
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button
            disabled={!value.trim()}
            onClick={() => {
              onSubmit(value.trim())
              onOpenChange(false)
              setValue("")
            }}
          >
            run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Today + quick capture --------------------------------------------------
const THIS_WEEK = "This week"

function TodayPanel() {
  const { data, isLoading } = useTasks()
  const toggle = useToggleTask()

  if (isLoading) return <Skeleton className="h-48" />
  const items = (data as TasksBySection | undefined)?.[THIS_WEEK] ?? []

  return (
    <Panel title="today" meta="this week" statusDotColor="accent">
      {items.length === 0 ? (
        <p className="text-sm text-text-label">no tasks queued</p>
      ) : (
        <div className="space-y-0.5">
          {items.map((t) => (
            <TaskCheck
              key={t.line_index}
              checked={t.checked}
              disabled={toggle.isPending}
              onToggle={() =>
                toggle.mutate({ section: THIS_WEEK, line_index: t.line_index })
              }
            >
              {t.text}
            </TaskCheck>
          ))}
        </div>
      )}
    </Panel>
  )
}

function QuickCapture() {
  const capture = useInboxCapture()
  const [text, setText] = useState("")

  function save() {
    const content = text.trim()
    if (!content) return
    capture.mutate(
      { content, source: "quickcapture" },
      {
        onSuccess: (r) => {
          setText("")
          toast.success("saved to inbox", r.filename)
        },
        onError: (e) => toast.error("could not save", String(e)),
      },
    )
  }

  return (
    <Panel title="quick capture" statusDotColor="muted">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="capture a thought, link, or note..."
        rows={4}
      />
      <div className="mt-2 flex justify-end">
        <Button onClick={save} disabled={!text.trim() || capture.isPending}>
          save to inbox
        </Button>
      </div>
    </Panel>
  )
}

// --- Priority recommendation ------------------------------------------------
function PriorityPanel() {
  const { data, isLoading, isError, isFetching, refetch } = usePrioritySuggestion(14)
  const ordered = (data?.ordered ?? []).slice(0, 5)

  return (
    <Panel title="priority recommendation" meta="next 14d" statusDotColor="accent">
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : isError ? (
        <p className="text-sm text-text-label">could not compute a recommendation.</p>
      ) : (
        <>
          {data?.recommendation && (
            <p className="mb-3 text-sm text-text">{data.recommendation}</p>
          )}
          {ordered.length > 0 && (
            <ol className="space-y-2 text-sm">
              {ordered.map((item) => (
                <li key={item.rank} className="flex gap-2">
                  <span className="font-mono text-accent tabular-nums">{item.rank}.</span>
                  <span className="flex-1">
                    <span className="text-text">{item.task}</span>
                    {item.deadline && (
                      <span className="ml-2 font-mono text-xs text-text-secondary tabular-nums">
                        {formatBoth(item.deadline)}
                      </span>
                    )}
                    {item.rationale && (
                      <span className="ml-2 text-xs text-text-label">— {item.rationale}</span>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <div className="mt-3 flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              {isFetching ? "computing…" : "recompute"}
            </Button>
          </div>
        </>
      )}
    </Panel>
  )
}

// --- Next week preview + bigger items ---------------------------------------
function NextWeekPanel() {
  const { data, isLoading } = useTasks()
  const items = (data as TasksBySection | undefined)?.["Next week"] ?? []

  return (
    <Panel title="next week" meta={`${items.length} ahead`} statusDotColor="muted">
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : items.length === 0 ? (
        <p className="text-sm text-text-label">nothing scheduled yet</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {items.map((t) => (
            <li key={t.line_index} className="flex items-start gap-2">
              <StatusDot color="muted" />
              <span className="text-text-secondary">{t.text}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function BiggerItemsPanel() {
  const { data } = useTasks()
  const toggle = useToggleTask()
  const items = (data as TasksBySection | undefined)?.["Bigger items"] ?? []
  const open = items.filter((t) => !t.checked).length

  return (
    <Collapsible title="bigger items" meta={`${open} open · no weekly deadline`}>
      {items.length === 0 ? (
        <p className="text-sm text-text-label">nothing here</p>
      ) : (
        <div className="space-y-0.5">
          {items.map((t) => (
            <TaskCheck
              key={t.line_index}
              checked={t.checked}
              disabled={toggle.isPending}
              onToggle={() =>
                toggle.mutate(
                  { section: "Bigger items", line_index: t.line_index },
                  { onError: (e) => toast.error("could not toggle task", String(e)) },
                )
              }
            >
              {t.text}
            </TaskCheck>
          ))}
        </div>
      )}
    </Collapsible>
  )
}

// --- Projects row -----------------------------------------------------------
function ProjectsRow() {
  const { data, isLoading } = useProjects()
  const active = (data ?? []).filter((p) => p.status !== "done")

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold tracking-tight">projects</h2>
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : active.length === 0 ? (
        <Panel title="projects" meta="0 active">
          <p className="text-sm text-text-label">no active projects</p>
        </Panel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {active.slice(0, 8).map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}
    </div>
  )
}

// --- Finances row -----------------------------------------------------------
function FinancesRow() {
  const portfolio = usePortfolioSnapshot()
  const money = useMoneySnapshot()
  const watchlist = useWatchlist(false)

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold tracking-tight">finances</h2>
      <BucketAllocation compact />
      <OptimizationSignals />
      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="portfolio" statusDotColor="accent">
          {portfolio.isLoading ? (
            <Skeleton className="h-12" />
          ) : (
            <div>
              <NumberDisplay
                value={portfolio.data?.total_value}
                format="currency"
                emphasized
                className="text-2xl"
              />
              <div className="mt-1 flex gap-4 text-xs text-text-secondary">
                <span>{portfolio.data?.position_count ?? 0} positions</span>
                <span>
                  deployable{" "}
                  <NumberDisplay
                    value={portfolio.data?.cash_deployable}
                    format="currency"
                    className="text-xs"
                  />
                </span>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="money" statusDotColor="success">
          {money.isLoading ? (
            <Skeleton className="h-12" />
          ) : (
            <div className="flex items-end justify-between">
              <div>
                <div className="label mb-0.5">cash</div>
                <NumberDisplay
                  value={money.data?.cash_balance}
                  format="currency"
                  emphasized
                  className="text-xl"
                />
              </div>
              <div className="text-right">
                <div className="label mb-0.5">runway</div>
                <NumberDisplay
                  value={money.data?.runway_months}
                  decimals={1}
                  className="text-xl"
                />
                <span className="ml-1 text-xs text-text-secondary">mo</span>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="watchlist" statusDotColor="muted">
          {watchlist.isLoading ? (
            <Skeleton className="h-12" />
          ) : (
            <div className="flex items-end justify-between">
              <div>
                <div className="label mb-0.5">names</div>
                <NumberDisplay value={watchlist.data?.count} className="text-xl" />
              </div>
              <div className="text-right">
                <div className="label mb-0.5">tiers</div>
                <NumberDisplay
                  value={Object.keys(watchlist.data?.tiers ?? {}).length}
                  className="text-xl"
                />
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}

// --- Signals row ------------------------------------------------------------
function SignalsRow() {
  const inbox = useInbox()
  const calendar = useCalendar(30)

  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold tracking-tight">signals</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <Panel
          title="inbox"
          meta={`${inbox.data?.length ?? 0} items`}
          statusDotColor={inbox.data && inbox.data.length > 0 ? "warning" : "muted"}
        >
          {inbox.isLoading ? (
            <Skeleton className="h-16" />
          ) : !inbox.data || inbox.data.length === 0 ? (
            <p className="text-sm text-text-label">inbox zero</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {inbox.data.slice(0, 3).map((i) => (
                <li key={i.filename} className="truncate font-mono text-xs text-text-secondary">
                  {i.filename}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="recent activity" statusDotColor="muted">
          <p className="text-sm text-text-label">
            recent-files endpoint pending (backend phase)
          </p>
        </Panel>

        <Panel title="calendar next" statusDotColor="accent">
          {calendar.isLoading ? (
            <Skeleton className="h-16" />
          ) : !calendar.data?.configured ? (
            <p className="text-sm text-text-label">calendar not configured</p>
          ) : calendar.data.events.length === 0 ? (
            <p className="text-sm text-text-label">no upcoming events</p>
          ) : (
            <ul className="space-y-1.5 text-sm">
              {calendar.data.events.slice(0, 3).map((e, i) => (
                <li key={i} className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-text">{e.title}</span>
                  <span className="shrink-0 font-mono text-xs text-text-secondary">
                    {e.start?.slice(5, 10) ?? ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
