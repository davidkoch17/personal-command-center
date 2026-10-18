import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { NumberDisplay } from "@/components/ui/number-display"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn, formatCurrency } from "@/lib/utils"
import { copyText } from "@/lib/copy-text"
import {
  type KapLine,
  type LossPot,
  type LossPotKey,
  useCarryforwards,
  useKapSummary,
  useLossPots,
  useSetCarryforwards,
  useVorabpauschale,
} from "@/hooks/useFinance"

const CONFIDENCE_STYLE: Record<string, string> = {
  confirmed: "text-success",
  estimated: "text-warning",
  manual_needed: "text-danger",
}

function ConfidenceTag({ value }: { value: string }) {
  return (
    <span className={cn("font-mono text-[10px] uppercase tracking-wide", CONFIDENCE_STYLE[value] ?? "text-text-label")}>
      {value.replace("_", " ")}
    </span>
  )
}

const THIS_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = Array.from({ length: 5 }, (_, i) => THIS_YEAR - i)

/**
 * Chunk 9 — Anlage KAP summary, Verlustverrechnungstoepfe, and Vorabpauschale.
 * One shared year selector drives all three sections below the existing
 * harvest-opportunities / trade-log Tax tab content.
 */
export function TaxExtrasPanel() {
  const [year, setYear] = useState(THIS_YEAR)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="label">tax year</span>
        <div className="w-28">
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {YEAR_OPTIONS.map((y) => (
                <SelectItem key={y} value={String(y)}>{y}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <KapSummarySection year={year} />
      <LossPotsSection year={year} />
      <VorabpauschaleSection year={year} />
    </div>
  )
}

// --- Anlage KAP summary ------------------------------------------------------------------------

function kapSummaryAsText(year: number, lines: KapLine[], nonKap: { label: string; amount_eur: number }): string {
  const rows = lines.map((l) => `Zeile ${l.zeile_number}\t${l.label}\t${formatCurrency(l.amount_eur)}\t${l.computation_note}`)
  return [
    `Anlage KAP — structured summary, ${year} (not an official Elster filing)`,
    ...rows,
    `(not Anlage KAP)\t${nonKap.label}\t${formatCurrency(nonKap.amount_eur)}`,
  ].join("\n")
}

function KapSummarySection({ year }: { year: number }) {
  const { data, isLoading } = useKapSummary(year)
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle")

  async function copy() {
    if (!data) return
    const ok = await copyText(kapSummaryAsText(year, data.lines, data.non_kap_note))
    setCopyState(ok ? "copied" : "failed")
    setTimeout(() => setCopyState("idle"), 2000)
  }

  return (
    <Panel
      title="anlage kap summary"
      statusDotColor="accent"
      meta={
        data ? (
          <span className="flex items-center gap-2">
            <span>{year} · not an Elster filing</span>
            <Button size="sm" variant="ghost" onClick={copy} className="h-6 px-2 text-xs">
              {copyState === "copied" ? "copied" : copyState === "failed" ? "copy failed" : "copy as text"}
            </Button>
          </span>
        ) : undefined
      }
    >
      {isLoading ? (
        <Skeleton className="h-64" />
      ) : !data ? (
        <EmptyState message="no data" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-2 pr-3 font-normal">zeile</th>
                  <th className="py-2 px-3 font-normal">label</th>
                  <th className="py-2 px-3 text-right font-normal">amount</th>
                  <th className="py-2 pl-3 font-normal">note</th>
                </tr>
              </thead>
              <tbody>
                {data.lines.map((l) => (
                  <tr key={l.zeile_number} className="border-b border-border/50 last:border-0 align-top">
                    <td className="py-2 pr-3 font-mono text-xs text-text-secondary">{l.zeile_number}</td>
                    <td className="py-2 px-3 text-text">{l.label}</td>
                    <td className="py-2 px-3 text-right">
                      <NumberDisplay value={l.amount_eur} format="currency" signed />
                    </td>
                    <td className="py-2 pl-3 max-w-xs text-xs text-text-label">
                      <div>{l.computation_note}</div>
                      <ConfidenceTag value={l.confidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 rounded-sm border border-border bg-bg-panel px-3 py-2 text-xs text-text-label">
            <span className="font-medium text-text-secondary">{data.non_kap_note.label}: </span>
            <NumberDisplay value={data.non_kap_note.amount_eur} format="currency" signed className="text-xs" />
            {" — "}{data.non_kap_note.computation_note}
          </div>

          <p className="mt-3 text-xs text-text-label">{data.disclaimer}</p>
        </>
      )}
    </Panel>
  )
}

// --- Verlustverrechnungstoepfe -----------------------------------------------------------------

const POT_ORDER: LossPotKey[] = ["aktien", "sonstige", "spekulation_23"]

function LossPotsSection({ year }: { year: number }) {
  const { data, isLoading } = useLossPots(year)
  const carry = useCarryforwards()
  const setCarry = useSetCarryforwards()
  const [drafts, setDrafts] = useState<Partial<Record<LossPotKey, string>>>({})

  function commit(pot: LossPotKey) {
    const raw = drafts[pot]
    if (raw === undefined) return
    const value = raw.trim() === "" ? 0 : Number(raw)
    if (!Number.isFinite(value)) return
    setCarry.mutate({ [pot]: value })
    setDrafts((d) => ({ ...d, [pot]: undefined }))
  }

  return (
    <Panel title="verlustverrechnungstopf" meta={data ? `${year} · prior-year carryforward is manual` : undefined} statusDotColor="warning">
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : !data ? (
        <EmptyState message="no data" />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {POT_ORDER.map((key) => (
              <LossPotCard
                key={key}
                pot={data.pots[key]}
                draft={drafts[key] ?? String(carry.data?.[key] ?? data.pots[key].prior_carryforward)}
                onDraftChange={(v) => setDrafts((d) => ({ ...d, [key]: v }))}
                onCommit={() => commit(key)}
              />
            ))}
          </div>
          {data.tax_free_crypto_excluded_eur !== 0 && (
            <p className="mt-3 text-xs text-text-label">
              <NumberDisplay value={data.tax_free_crypto_excluded_eur} format="currency" className="text-xs" /> excluded
              as tax-free crypto (Spekulationsfrist met, held ≥ 365 days) — not counted anywhere above.
            </p>
          )}
          <p className="mt-2 text-xs text-text-label">{data.note}</p>
        </>
      )}
    </Panel>
  )
}

function LossPotCard({
  pot,
  draft,
  onDraftChange,
  onCommit,
}: {
  pot: LossPot
  draft: string
  onDraftChange: (v: string) => void
  onCommit: () => void
}) {
  const negative = pot.net_balance < 0
  return (
    <div className="rounded-sm border border-border bg-bg-panel p-3">
      <div className="mb-2 text-xs font-medium text-text-secondary">{pot.label}</div>
      <div className="space-y-1 text-xs text-text-label">
        <div className="flex justify-between">
          <span>this year gains</span>
          <NumberDisplay value={pot.this_year_gains} format="currency" className="text-xs text-text" />
        </div>
        <div className="flex justify-between">
          <span>this year losses</span>
          <NumberDisplay value={-pot.this_year_losses} format="currency" className="text-xs text-text" />
        </div>
        <div className="flex items-center justify-between gap-2">
          <span>prior carryforward</span>
          <Input
            mono
            type="number"
            step="0.01"
            className="h-6 w-20 text-right text-xs"
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            onBlur={onCommit}
            onKeyDown={(e) => e.key === "Enter" && onCommit()}
            aria-label={`${pot.label} prior-year carryforward`}
          />
        </div>
      </div>
      <div className={cn("mt-2 border-t border-border pt-2 text-right font-mono text-sm font-medium", negative ? "text-danger" : "text-success")}>
        <NumberDisplay value={pot.net_balance} format="currency" signed className="text-sm" />
      </div>
      <div className="text-right text-[10px] text-text-label">
        {negative ? "loss carries forward" : "net taxable"}
      </div>
    </div>
  )
}

// --- Vorabpauschale ----------------------------------------------------------------------------

function VorabpauschaleSection({ year }: { year: number }) {
  const { data, isLoading } = useVorabpauschale(year)

  return (
    <Panel
      title="vorabpauschale"
      meta={data ? `${year} · thesaurierende ETFs${data.basiszins != null ? ` · Basiszins ${(data.basiszins * 100).toFixed(2)}%` : ""}` : undefined}
      statusDotColor="accent"
    >
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : !data || data.rows.length === 0 ? (
        <EmptyState message="no thesaurierend ETFs held in the etf_foundation bucket" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-2 pr-3 font-normal">etf</th>
                  <th className="py-2 px-3 text-right font-normal">anfangswert</th>
                  <th className="py-2 px-3 text-right font-normal">endwert</th>
                  <th className="py-2 px-3 text-right font-normal">vorabpauschale</th>
                  <th className="py-2 px-3 text-right font-normal">teilfreistellung</th>
                  <th className="py-2 pl-3 text-right font-normal">taxable base</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.ticker} className="border-b border-border/50 last:border-0 align-top">
                    <td className="py-2 pr-3 font-mono text-text">{r.ticker}</td>
                    <td className="py-2 px-3 text-right"><NumberDisplay value={r.fondswert_anfang} format="currency" /></td>
                    <td className="py-2 px-3 text-right"><NumberDisplay value={r.fondswert_ende} format="currency" /></td>
                    <td className="py-2 px-3 text-right"><NumberDisplay value={r.vorabpauschale} format="currency" /></td>
                    <td className="py-2 px-3 text-right font-mono text-xs text-text-secondary">{(r.teilfreistellung * 100).toFixed(0)}%</td>
                    <td className="py-2 pl-3 text-right">
                      <NumberDisplay value={r.taxable_amount} format="currency" />
                      <div className="mt-0.5"><ConfidenceTag value={r.confidence} /></div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-border font-medium">
                  <td className="py-2 pr-3" colSpan={5}>total taxable base — feeds Anlage KAP Zeile 41-45</td>
                  <td className="py-2 pl-3 text-right"><NumberDisplay value={data.total_taxable_eur} format="currency" /></td>
                </tr>
              </tfoot>
            </table>
          </div>
          {data.rows.some((r) => r.confidence === "manual_needed") && (
            <p className="mt-2 text-xs text-text-label">
              {data.rows.find((r) => r.confidence === "manual_needed")?.note}
            </p>
          )}
        </>
      )}
    </Panel>
  )
}
