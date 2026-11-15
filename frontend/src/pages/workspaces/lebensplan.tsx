import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { useQueries } from "@tanstack/react-query"
import { FileSpreadsheet, RotateCcw, Save, Trash2, Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Toaster } from "@/components/ui/toaster"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast-store"
import {
  computePlan,
  openExcel,
  useDeleteScenario,
  useLifePlanBase,
  usePromote,
  useSaveScenario,
  useScenarios,
  type LifePlanInputs,
  type LifePlanResult,
} from "@/hooks/useLifeplan"
import { DriversPanel } from "@/components/lifeplan/drivers-panel"
import { CareerChart, CompareChart, COMPARE_COLORS, FlowsChart, WealthChart } from "@/components/lifeplan/charts"
import { DreamCosts, MilestonesTable, TimelineTable } from "@/components/lifeplan/tables"
import { eur, eurShort } from "@/components/lifeplan/format"

const BASE_ID = "__base__"
const CURRENT_ID = "__current__"

function setIn<T>(obj: T, path: (string | number)[], value: unknown): T {
  const out = structuredClone(obj) as unknown as Record<string | number, unknown>
  let cur = out
  for (const key of path.slice(0, -1)) cur = cur[key] as Record<string | number, unknown>
  cur[path[path.length - 1]] = value
  return out as unknown as T
}

function errText(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e)
  try {
    const parsed = JSON.parse(msg)
    return typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail)
  } catch {
    return msg
  }
}

/** Standalone workspace (no AppShell): interactive life / wealth plan. */
export function Lebensplan() {
  const baseQ = useLifePlanBase()
  const scenQ = useScenarios()
  const saveScenario = useSaveScenario()
  const deleteScenario = useDeleteScenario()
  const promote = usePromote()

  const [selected, setSelected] = useState<string>(BASE_ID)
  const [draft, setDraft] = useState<LifePlanInputs | null>(null)
  const [result, setResult] = useState<LifePlanResult | null>(null)
  const [computing, setComputing] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)
  const [promoteOpen, setPromoteOpen] = useState(false)
  const [scenarioName, setScenarioName] = useState("")
  const [compareIds, setCompareIds] = useState<string[]>([CURRENT_ID, BASE_ID])

  useEffect(() => {
    document.title = "Lebensplan"
  }, [])

  const scenarios = scenQ.data?.scenarios ?? []
  const selectedScenario = scenarios.find((s) => s.id === selected)
  const reference: LifePlanInputs | null =
    selected === BASE_ID ? baseQ.data?.inputs ?? null : selectedScenario?.inputs ?? null

  // Initialise / switch the playground when the reference changes.
  const refKey = reference ? `${selected}:${JSON.stringify(reference)}` : ""
  const lastRef = useRef("")
  useEffect(() => {
    if (reference && refKey !== lastRef.current) {
      lastRef.current = refKey
      setDraft(structuredClone(reference))
    }
  }, [refKey, reference])

  // Debounced recompute on every change.
  const seq = useRef(0)
  useEffect(() => {
    if (!draft) return
    const id = ++seq.current
    setComputing(true)
    const t = setTimeout(() => {
      computePlan(draft)
        .then((r) => {
          if (id === seq.current) setResult(r.result)
        })
        .catch((e) => {
          if (id === seq.current) toast.error("Berechnung fehlgeschlagen", errText(e))
        })
        .finally(() => {
          if (id === seq.current) setComputing(false)
        })
    }, 150)
    return () => clearTimeout(t)
  }, [draft])

  const set = useCallback((path: (string | number)[], value: unknown) => {
    setDraft((d) => (d ? setIn(d, path, value) : d))
  }, [])

  const dirty = useMemo(
    () => !!draft && !!reference && JSON.stringify(draft) !== JSON.stringify(reference),
    [draft, reference],
  )

  // --- comparison: compute saved scenarios on demand -------------------------
  const compareScenarioIds = compareIds.filter((id) => id !== CURRENT_ID && id !== BASE_ID)
  const compareQueries = useQueries({
    queries: compareScenarioIds.map((id) => {
      const sc = scenarios.find((s) => s.id === id)
      return {
        queryKey: ["lifeplan", "compare", id, sc?.updated ?? "", baseQ.dataUpdatedAt],
        queryFn: () => computePlan(sc?.overrides ?? {}),
        enabled: !!sc,
      }
    }),
  })
  const compareSeries = compareIds
    .map((id) => {
      if (id === CURRENT_ID) return result ? { name: dirty ? "Aktuelle Ansicht" : "Aktuell", result } : null
      if (id === BASE_ID) return baseQ.data ? { name: "Basis (Excel)", result: baseQ.data.result } : null
      const idx = compareScenarioIds.indexOf(id)
      const r = compareQueries[idx]?.data?.result
      const sc = scenarios.find((s) => s.id === id)
      return r && sc ? { name: sc.name, result: r } : null
    })
    .filter((x): x is { name: string; result: LifePlanResult } => x !== null)

  const toggleCompare = (id: string) =>
    setCompareIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : ids.length >= 3 ? ids : [...ids, id],
    )

  // --- actions -------------------------------------------------------------
  const onSave = () => {
    if (!draft || !scenarioName.trim()) return
    const existing = scenarios.find((s) => s.name === scenarioName.trim())
    saveScenario.mutate(
      { name: scenarioName.trim(), inputs: draft, id: existing?.id },
      {
        onSuccess: (s) => {
          toast.success(`Szenario „${s.name}“ gespeichert`)
          setSaveOpen(false)
          lastRef.current = `${s.id}:${JSON.stringify(s.inputs)}`
          setSelected(s.id)
        },
        onError: (e) => toast.error("Speichern fehlgeschlagen", errText(e)),
      },
    )
  }

  const onDelete = () => {
    if (!selectedScenario) return
    if (!window.confirm(`Szenario „${selectedScenario.name}“ löschen?`)) return
    deleteScenario.mutate(selectedScenario.id, {
      onSuccess: () => {
        toast.show("Szenario gelöscht")
        setCompareIds((ids) => ids.filter((x) => x !== selectedScenario.id))
        setSelected(BASE_ID)
      },
      onError: (e) => toast.error("Löschen fehlgeschlagen", errText(e)),
    })
  }

  const onPromote = () => {
    if (!draft) return
    promote.mutate(draft, {
      onSuccess: (r) => {
        toast.success("In die Excel übernommen", `${r.changed.length} Zellen · Backup: ${r.backup.split(/[\\/]/).pop()}`)
        setPromoteOpen(false)
        setSelected(BASE_ID)
        scenQ.refetch()
      },
      onError: (e) => toast.error("Übernehmen fehlgeschlagen", errText(e)),
    })
  }

  const onOpenExcel = () =>
    openExcel()
      .then(() => toast.show("Excel wird geöffnet"))
      .catch((e) => toast.error("Konnte Excel nicht öffnen", errText(e)))

  // --- render --------------------------------------------------------------
  if (baseQ.isError) {
    return (
      <Shell>
        <div className="panel text-sm text-danger">Lebensplan konnte nicht geladen werden: {errText(baseQ.error)}</div>
      </Shell>
    )
  }
  if (!draft || !result || !baseQ.data) {
    return (
      <Shell>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-[480px] w-full" />
      </Shell>
    )
  }

  const s = result.summary
  return (
    <Shell>
      {/* 1. Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="page-title">Lebensplan</h1>
          <span className="text-xs text-text-label">Alle Beträge in heutiger Kaufkraft (real)</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="h-8 w-[220px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={BASE_ID}>Basis (Excel)</SelectItem>
              {scenarios.map((sc) => (
                <SelectItem key={sc.id} value={sc.id}>
                  {sc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {dirty && <span className="rounded-sm bg-warning/15 px-2 py-1 text-[11px] text-warning">Ungespeicherte Änderungen</span>}
          {computing && <span className="text-[11px] text-text-label">rechnet…</span>}
          <Button size="sm" variant="ghost" disabled={!dirty} onClick={() => reference && setDraft(structuredClone(reference))}>
            <RotateCcw className="h-3.5 w-3.5" /> Zurücksetzen
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setScenarioName(selectedScenario?.name ?? "")
              setSaveOpen(true)
            }}
          >
            <Save className="h-3.5 w-3.5" /> Szenario speichern
          </Button>
          {selectedScenario && (
            <Button size="sm" variant="ghost" onClick={onDelete} aria-label="Szenario löschen">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => setPromoteOpen(true)}>
            <Upload className="h-3.5 w-3.5" /> Als Basis übernehmen
          </Button>
          <Button size="sm" variant="ghost" onClick={onOpenExcel}>
            <FileSpreadsheet className="h-3.5 w-3.5" /> Excel öffnen
          </Button>
        </div>
      </div>

      {/* 2. KPI cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Kpi label="Ziel-Vermögen" value={eurShort(s.target)} title={eur(s.target)} />
        <Kpi
          label="Ziel erreicht mit"
          value={s.goal_age == null ? "nicht bis 75" : `${s.goal_age} (${s.goal_year})`}
          tone={s.goal_age == null ? "danger" : "success"}
        />
        {[40, 45, 50].map((age) => (
          <Kpi key={age} label={`Nettovermögen mit ${age}`} value={eurShort(s.net_worth_at[String(age)])} title={eur(s.net_worth_at[String(age)])} />
        ))}
        <Kpi label="Tiefster Stand liquide" value={eurShort(s.min_liquid)} title={eur(s.min_liquid)} tone={s.min_liquid < 0 ? "danger" : undefined} />
        <Kpi label="Warnjahre" value={String(s.warnings)} tone={s.warnings > 0 ? "danger" : "success"} />
      </div>

      {/* 3–5. Drivers left, chart + tabs right */}
      <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto lg:pr-1">
          <DriversPanel inputs={draft} set={set} live={baseQ.data.live_wealth} />
        </aside>

        <div className="min-w-0 space-y-4">
          <div className="panel">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-medium tracking-wider text-text-label">Vermögen über Alter</span>
              <span className="text-[11px] text-text-label">rot hinterlegt = Warnjahr · gestrichelt = Ziel / Käufe</span>
            </div>
            <WealthChart result={result} />
          </div>

          <div className="panel">
            <Tabs defaultValue="timeline">
              <TabsList className="[&>button]:normal-case">
                <TabsTrigger value="timeline">Zeitachse</TabsTrigger>
                <TabsTrigger value="flows">Einkommen und Ausgaben</TabsTrigger>
                <TabsTrigger value="milestones">Meilensteine</TabsTrigger>
                <TabsTrigger value="career">Karriere</TabsTrigger>
                <TabsTrigger value="costs">Traumleben-Kosten</TabsTrigger>
                <TabsTrigger value="compare">Szenario-Vergleich</TabsTrigger>
              </TabsList>
              <TabsContent value="timeline">
                <TimelineTable result={result} />
              </TabsContent>
              <TabsContent value="flows">
                <FlowsChart result={result} />
              </TabsContent>
              <TabsContent value="milestones">
                <MilestonesTable result={result} />
              </TabsContent>
              <TabsContent value="career">
                <CareerChart result={result} />
              </TabsContent>
              <TabsContent value="costs">
                <DreamCosts inputs={draft} result={result} set={set} />
              </TabsContent>
              <TabsContent value="compare">
                <div className="mb-3 flex flex-wrap gap-2">
                  {[{ id: CURRENT_ID, name: "Aktuelle Ansicht" }, { id: BASE_ID, name: "Basis (Excel)" }, ...scenarios].map((o) => {
                    const on = compareIds.includes(o.id)
                    const idx = compareIds.indexOf(o.id)
                    return (
                      <button
                        key={o.id}
                        type="button"
                        onClick={() => toggleCompare(o.id)}
                        disabled={!on && compareIds.length >= 3}
                        className={cn(
                          "flex items-center gap-1.5 rounded-sm border px-2 py-1 text-xs transition-colors disabled:opacity-40",
                          on ? "border-accent text-text" : "border-border text-text-secondary hover:text-text",
                        )}
                      >
                        <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: on ? COMPARE_COLORS[idx] : "transparent", border: on ? "none" : "1px solid currentColor" }} />
                        {o.name}
                      </button>
                    )
                  })}
                  <span className="self-center text-[11px] text-text-label">max. 3</span>
                </div>
                {compareSeries.length > 0 ? (
                  <>
                    <CompareChart series={compareSeries} />
                    <CompareTable series={compareSeries} />
                  </>
                ) : (
                  <p className="text-xs text-text-label">Szenarien auswählen.</p>
                )}
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Szenario speichern</DialogTitle>
            <DialogDescription>Gleicher Name überschreibt das bestehende Szenario.</DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSave()}
            placeholder="z. B. Grünwald mit 40 + Gymnasium"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSaveOpen(false)}>
              Abbrechen
            </Button>
            <Button onClick={onSave} disabled={!scenarioName.trim() || saveScenario.isPending}>
              Speichern
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={promoteOpen} onOpenChange={setPromoteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Als Basis übernehmen?</DialogTitle>
            <DialogDescription>
              Die aktuellen Werte werden in die Eingabezellen von Traumleben_Plan.xlsx geschrieben (Formeln bleiben unverändert).
              Vorher wird ein Backup im Ordner „backup“ angelegt. Die Excel muss dafür geschlossen sein.
            </DialogDescription>
          </DialogHeader>
          {(draft.career.bonus_factor !== 1 || draft.career.md_age != null || draft.start.wealth_source === "dashboard") && (
            <p className="text-xs text-text-secondary">
              Bonus-Faktor / MD-Regler werden in die Gehaltstabelle eingerechnet
              {draft.start.wealth_source === "dashboard" && baseQ.data.live_wealth
                ? `; Startvermögen = ${eur(baseQ.data.live_wealth.total)} (Dashboard)`
                : ""}
              .
            </p>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPromoteOpen(false)}>
              Abbrechen
            </Button>
            <Button onClick={onPromote} disabled={promote.isPending}>
              In Excel schreiben
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Shell>
  )
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg p-4 text-text sm:p-6">
      <div className="mx-auto max-w-[1600px] space-y-4">{children}</div>
      <Toaster />
    </div>
  )
}

function Kpi({ label, value, title, tone }: { label: string; value: string; title?: string; tone?: "danger" | "success" }) {
  return (
    <div className="panel !p-3" title={title}>
      <div className="text-[11px] font-medium tracking-wider text-text-label mb-1">{label}</div>
      <div className={cn("font-mono text-lg font-semibold tabular-nums", tone === "danger" && "text-danger", tone === "success" && "text-success")}>
        {value}
      </div>
    </div>
  )
}

function CompareTable({ series }: { series: { name: string; result: LifePlanResult }[] }) {
  const rows: [string, (r: LifePlanResult) => string][] = [
    ["Ziel-Vermögen", (r) => eurShort(r.summary.target)],
    ["Ziel erreicht mit", (r) => (r.summary.goal_age == null ? "nicht bis 75" : String(r.summary.goal_age))],
    ...[30, 35, 40, 45, 50, 55].map(
      (a) => [`Nettovermögen mit ${a}`, (r: LifePlanResult) => eurShort(r.summary.net_worth_at[String(a)])] as [string, (r: LifePlanResult) => string],
    ),
    ["Tiefster Stand liquide", (r) => eurShort(r.summary.min_liquid)],
    ["Warnjahre", (r) => String(r.summary.warnings)],
  ]
  return (
    <div className="mt-3 overflow-auto rounded border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="px-2 py-1.5 text-left font-medium text-text-label">Kennzahl</th>
            {series.map((s, j) => (
              <th key={j} className="px-2 py-1.5 text-right font-medium" style={{ color: COMPARE_COLORS[j] }}>
                {s.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, f]) => (
            <tr key={label} className="border-b border-border/50">
              <td className="px-2 py-1 text-text-secondary">{label}</td>
              {series.map((s, j) => (
                <td key={j} className="px-2 py-1 text-right font-mono tabular-nums">
                  {f(s.result)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
