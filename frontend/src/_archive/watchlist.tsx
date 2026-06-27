import { useMemo, useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { WatchlistCard } from "@/components/cards/watchlist-card"
import {
  useWatchlist,
  useWatchlistDossiers,
  useAddWatchlist,
  type WatchlistEntry,
  type WatchlistSection,
  type FormSection,
} from "@/hooks/useFinance"
import { InfoBarrierBanner } from "@/components/ui/info-barrier-banner"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

const FILTERS = ["All", "Tier 1", "Tier 2", "Tier 3"] as const
type Filter = (typeof FILTERS)[number]

const AGGREGATE_TABS = new Set(["hypotheses", "news", "filings", "signals"])

export function Watchlist() {
  const wl = useWatchlist(true)
  const [filter, setFilter] = useState<Filter>("All")
  const [tab, setTab] = useState("cards")
  const [addOpen, setAddOpen] = useState(false)

  const allEntries = useMemo<WatchlistEntry[]>(
    () => Object.values(wl.data?.tiers ?? {}).flat(),
    [wl.data],
  )
  // Cards tab renders straight from the ordered section structure, filtered by tier.
  const sections = useMemo<WatchlistSection[]>(() => wl.data?.sections ?? [], [wl.data])
  const visibleSections = useMemo(
    () =>
      filter === "All"
        ? sections
        : sections.filter((s) => (s.tier ?? "").includes(filter.replace("Tier ", ""))),
    [sections, filter],
  )
  const filtered = useMemo(
    () =>
      filter === "All"
        ? allEntries
        : allEntries.filter((e) => (e.tier ?? "").includes(filter.replace("Tier ", ""))),
    [allEntries, filter],
  )
  const tier1 = useMemo(
    () => allEntries.filter((e) => (e.tier ?? "").includes("1")),
    [allEntries],
  )

  const universe = useMemo(() => filtered.map((e) => e.ticker).filter(Boolean), [filtered])
  const dossiers = useWatchlistDossiers(universe, AGGREGATE_TABS.has(tab))
  const aggLoading = dossiers.some((d) => d.isLoading)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">watchlist</h1>
        <Button onClick={() => setAddOpen(true)}>+ add to watchlist</Button>
      </div>

      <InfoBarrierBanner message="a restricted-sector name may be involved" />

      {/* Filter strip */}
      <div className="flex gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-sm border px-3 py-1 text-xs lowercase transition-colors",
              filter === f
                ? "border-accent text-accent bg-bg-panel-hover"
                : "border-border text-text-secondary hover:text-text",
            )}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto self-center font-mono text-xs text-text-label">
          {wl.data?.count ?? 0} names
        </span>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="cards">cards</TabsTrigger>
          <TabsTrigger value="hypotheses">all hypotheses</TabsTrigger>
          <TabsTrigger value="news">all news (7d)</TabsTrigger>
          <TabsTrigger value="filings">all filings (30d)</TabsTrigger>
          <TabsTrigger value="signals">recent signals</TabsTrigger>
          <TabsTrigger value="macro">macro pulse</TabsTrigger>
          <TabsTrigger value="comps">comp tables</TabsTrigger>
        </TabsList>

        {/* 1. Cards — grouped by tier + theme section (A–N), straight from Watchlist.md */}
        <TabsContent value="cards">
          {wl.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-36" />
              ))}
            </div>
          ) : visibleSections.length === 0 ? (
            <Panel title="watchlist" meta="0 names">
              <p className="text-sm text-text-label">no names in this tier</p>
            </Panel>
          ) : (
            <div className="space-y-6">
              {visibleSections.map((s) => (
                <SectionBlock key={`${s.tier}-${s.key}`} section={s} />
              ))}
            </div>
          )}
        </TabsContent>

        {/* 2-5. Aggregate tabs */}
        <TabsContent value="hypotheses">
          <AggregatePanel
            title="all hypotheses"
            loading={aggLoading}
            rows={dossiers.flatMap((d) =>
              (d.data?.hypotheses ?? []).map((h) => ({
                ticker: d.data!.ticker,
                text: String((h as Record<string, unknown>).text ?? JSON.stringify(h)),
              })),
            )}
          />
        </TabsContent>
        <TabsContent value="news">
          <AggregatePanel
            title="all news"
            loading={aggLoading}
            rows={dossiers.flatMap((d) =>
              (d.data?.news ?? []).map((n) => {
                const o = n as Record<string, unknown>
                return {
                  ticker: d.data!.ticker,
                  text: String(o.title ?? o.headline ?? "untitled"),
                  url: typeof o.url === "string" ? o.url : (o.link as string | undefined),
                }
              }),
            )}
          />
        </TabsContent>
        <TabsContent value="filings">
          <AggregatePanel
            title="all filings"
            loading={aggLoading}
            rows={dossiers.flatMap((d) =>
              (d.data?.filings ?? []).map((f) => {
                const o = f as Record<string, unknown>
                return {
                  ticker: d.data!.ticker,
                  text: `${String(o.form ?? o.type ?? "filing")} ${String(o.date ?? o.filed ?? "")}`.trim(),
                  url: typeof o.url === "string" ? o.url : (o.link as string | undefined),
                }
              }),
            )}
          />
        </TabsContent>
        <TabsContent value="signals">
          <AggregatePanel
            title="recent signals"
            loading={aggLoading}
            rows={dossiers.flatMap((d) =>
              (d.data?.signals ?? []).map((s) => ({
                ticker: d.data!.ticker,
                text: String((s as Record<string, unknown>).text ?? JSON.stringify(s)),
              })),
            )}
          />
        </TabsContent>

        {/* 6. Macro pulse */}
        <TabsContent value="macro">
          <Panel title="macro pulse" meta="tier 1" statusDotColor="accent">
            {wl.isLoading ? (
              <Skeleton className="h-32" />
            ) : tier1.length === 0 ? (
              <p className="text-sm text-text-label">no tier 1 instruments tagged</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {tier1.map((e) => (
                  <div key={e.ticker} className="rounded border border-border p-3">
                    <div className="font-mono text-sm text-text">{e.ticker}</div>
                    <div className="truncate text-xs text-text-secondary">{e.name}</div>
                    <div className="mt-2 flex items-center justify-between">
                      <NumberDisplay value={e.price?.last_close ?? null} format="currency" />
                      <NumberDisplay value={e.price?.week_change_pct ?? null} format="percent" signed />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </TabsContent>

        {/* 7. Comp tables */}
        <TabsContent value="comps">
          <Panel title="comp tables" statusDotColor="muted">
            <p className="text-sm text-text-label">
              comp tables aggregate from per-ticker models; none built yet. build a
              model from a ticker workspace to populate this.
            </p>
          </Panel>
        </TabsContent>
      </Tabs>

      <AddWatchlistDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        formSections={wl.data?.form_sections ?? []}
      />
    </div>
  )
}

/** One tier/theme section: a header line plus a grid of ticker cards and any
 *  non-ticker topic notes (e.g. "Tom Lee", "ByteDance" in sections M/N). */
function SectionBlock({ section }: { section: WatchlistSection }) {
  const tickers = section.entries.filter((e) => e.is_ticker !== false && e.ticker)
  const notes = section.entries.filter((e) => e.is_ticker === false)
  const heading = section.letter
    ? `${section.letter}. ${section.title}`
    : section.title
  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2">
        <span className="label text-accent">{section.tier}</span>
        <span className="text-sm text-text">{heading}</span>
        <span className="ml-auto font-mono text-xs text-text-label">
          {tickers.length || ""}
        </span>
      </div>
      {tickers.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {tickers.map((e) => (
            <WatchlistCard key={e.ticker} entry={e} />
          ))}
        </div>
      )}
      {notes.map((n, i) => (
        <p key={i} className="mt-1 text-xs text-text-label">
          {n.name}
        </p>
      ))}
    </div>
  )
}

function AggregatePanel({
  title,
  loading,
  rows,
}: {
  title: string
  loading: boolean
  rows: { ticker: string; text: string; url?: string }[]
}) {
  return (
    <Panel title={title} meta={loading ? "loading..." : `${rows.length}`} statusDotColor="accent">
      {loading ? (
        <Skeleton className="h-32" />
      ) : rows.length === 0 ? (
        <p className="text-sm text-text-label">nothing across the current universe</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {rows.map((r, i) => (
            <li key={i} className="flex items-baseline gap-2">
              <span className="shrink-0 font-mono text-xs text-accent">{r.ticker}</span>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="truncate text-text hover:text-accent">
                  {r.text}
                </a>
              ) : (
                <span className="truncate text-text-secondary">{r.text}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function AddWatchlistDialog({
  open,
  onOpenChange,
  formSections,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  formSections: FormSection[]
}) {
  const add = useAddWatchlist()
  const [ticker, setTicker] = useState("")
  const [name, setName] = useState("")
  const [section, setSection] = useState("adhoc")
  const [notes, setNotes] = useState("")

  // Always offer the Ad-hoc default even before the API list arrives.
  const sections = formSections.length
    ? formSections
    : [{ key: "adhoc", label: "Tier 3 · Ad-hoc (dashboard additions)" }]

  function reset() {
    setTicker("")
    setName("")
    setSection("adhoc")
    setNotes("")
  }

  function submit() {
    const tk = ticker.trim().toUpperCase()
    if (!tk) return
    add.mutate(
      { ticker: tk, name: name.trim(), section, notes: notes.trim() },
      {
        onSuccess: (r) => {
          if (r && r.ok === false) {
            toast.show(`${tk} is already on the watchlist`, { tone: "default" })
          } else {
            toast.success("added to Watchlist.md", tk)
          }
          onOpenChange(false)
          reset()
        },
        onError: (e) => toast.error("could not add", String(e)),
      },
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o)
        if (!o) reset()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>add to watchlist</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="label mb-1">ticker</div>
              <Input value={ticker} onChange={(e) => setTicker(e.target.value)} mono placeholder="ASML" />
            </div>
            <div>
              <div className="label mb-1">name</div>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="ASML Holding" />
            </div>
          </div>
          <div>
            <div className="label mb-1">section (appends to Watchlist.md)</div>
            <Select value={section} onValueChange={setSection}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sections.map((s) => (
                  <SelectItem key={s.key} value={s.key}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="label mb-1">rationale</div>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="why watch this name..." />
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            cancel
          </Button>
          <Button onClick={submit} disabled={!ticker.trim() || add.isPending}>
            add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
