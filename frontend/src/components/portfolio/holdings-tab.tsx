import { useState } from "react"
import { Check, Pencil, Trash2, X } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { MetricPanel } from "@/components/finance/metric-panel"
import { NumberDisplay } from "@/components/ui/number-display"
import { TransactionForm, ACTIONS } from "@/components/finance/transaction-form"
import {
  useDeleteTransaction,
  useFinanceTransactions,
  useUpdateTransaction,
  type FinanceTransaction,
  type TransactionRequest,
} from "@/hooks/useFinance"
import { useHoldingsPnl, useRealizedTrades, type PnlPosition } from "@/hooks/usePortfolioHub"
import { DecisionLogDialog, type DecisionPrefill } from "./decision-log"
import { cn, formatCurrency } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

export function HoldingsTab() {
  const pnl = useHoldingsPnl()
  const [showForm, setShowForm] = useState(false)
  // Model C: auto-prompt a decision-log entry after a buy/sell.
  const [decisionPrefill, setDecisionPrefill] = useState<DecisionPrefill | null>(null)

  function onTrade(tx?: TransactionRequest) {
    setShowForm(false)
    if (tx && (tx.action === "buy" || tx.action === "sell")) {
      setDecisionPrefill({ ticker: tx.ticker, action: tx.action, quantity: tx.quantity, price: tx.price })
    }
  }

  return (
    <div className="space-y-5">
      {/* 1) Total summary band ABOVE the table — 4 metric cards. */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricPanel
          label="total value"
          value={
            pnl.isLoading ? <Skeleton className="h-7 w-28" /> : (
              <NumberDisplay value={pnl.data?.total_value} format="currency" emphasized animate />
            )
          }
          caption={`${pnl.data?.count ?? 0} positions`}
        />
        <PnlMetric label="p&l month" value={pnl.data?.pnl_month_total} loading={pnl.isLoading} />
        <PnlMetric label="p&l ytd" value={pnl.data?.pnl_ytd_total} loading={pnl.isLoading} />
        <PnlMetric label="p&l all-time" value={pnl.data?.pnl_all_total} loading={pnl.isLoading} />
      </div>

      {/* Current positions table */}
      <Panel
        title="current positions"
        meta={pnl.data?.as_of ? `as of ${pnl.data.as_of}` : undefined}
        statusDotColor="accent"
      >
        {pnl.isLoading ? (
          <Skeleton className="h-48" />
        ) : pnl.isError ? (
          <p className="text-sm text-text-secondary">could not load holdings. backend on :8000?</p>
        ) : !pnl.data?.positions.length ? (
          <p className="text-sm text-text-label">no open positions. log a buy below.</p>
        ) : (
          <HoldingsPnlTable rows={pnl.data.positions} />
        )}
      </Panel>

      {/* Editable transaction ledger — full buy/sell/dividend/etc. history */}
      <TransactionLedger />

      {/* 2) Trade log (closed trades) */}
      <TradeLog />

      {/* Add transaction */}
      <Panel title="log transaction" statusDotColor="muted">
        {showForm ? (
          <TransactionForm onDone={onTrade} />
        ) : (
          <Button variant="secondary" size="sm" onClick={() => setShowForm(true)}>
            + add buy / sell
          </Button>
        )}
      </Panel>

      {/* Model C — auto-prompt: log the decision behind the trade just made. */}
      <DecisionLogDialog
        open={decisionPrefill != null}
        onOpenChange={(o) => !o && setDecisionPrefill(null)}
        prefill={decisionPrefill ?? undefined}
      />
    </div>
  )
}

function PnlMetric({ label, value, loading }: { label: string; value?: number; loading: boolean }) {
  return (
    <MetricPanel
      label={label}
      dotColor={value == null ? "muted" : value >= 0 ? "success" : "danger"}
      value={
        loading ? <Skeleton className="h-7 w-24" /> : <NumberDisplay value={value} format="currency" signed />
      }
    />
  )
}

/** Columns (LOCKED order): Position · Weight · Price · Value · P&L month · P&L YTD ·
 *  P&L all-time (EUR + %) · Qty (far right, muted/de-emphasized). */
function HoldingsPnlTable({ rows }: { rows: PnlPosition[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-text-label">
            <th className="py-2 pr-3 font-normal">position</th>
            <th className="py-2 px-3 text-right font-normal">weight</th>
            <th className="py-2 px-3 text-right font-normal">price</th>
            <th className="py-2 px-3 text-right font-normal">value</th>
            <th className="py-2 px-3 text-right font-normal">p&l month</th>
            <th className="py-2 px-3 text-right font-normal">p&l ytd</th>
            <th className="py-2 px-3 text-right font-normal">p&l all-time</th>
            <th className="py-2 pl-3 text-right font-normal text-text-disabled">qty</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker} className="border-b border-border/50 last:border-0">
              <td className="py-2 pr-3">
                <div className="font-mono text-text">{r.ticker}</div>
                <div className="max-w-[14rem] truncate text-xs text-text-secondary">{r.name}</div>
              </td>
              <td className="py-2 px-3 text-right">
                <span className="font-mono tabular-nums text-text-secondary">
                  {r.weight != null ? `${(r.weight * 100).toFixed(1)}%` : "—"}
                </span>
              </td>
              <td className="py-2 px-3 text-right">
                <NumberDisplay value={r.price_eur} format="currency" />
              </td>
              <td className="py-2 px-3 text-right">
                <NumberDisplay value={r.value_eur} format="currency" />
              </td>
              <PnlCell eur={r.pnl_month} pct={r.pnl_month_pct} />
              <PnlCell eur={r.pnl_ytd} pct={r.pnl_ytd_pct} />
              <PnlCell eur={r.pnl_all} pct={r.pnl_all_pct} />
              <td className="py-2 pl-3 text-right">
                <span className="font-mono text-xs tabular-nums text-text-disabled">
                  {r.qty.toLocaleString("en-US", { maximumFractionDigits: 4 })}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PnlCell({ eur, pct }: { eur: number; pct: number | null }) {
  return (
    <td className="py-2 px-3 text-right">
      <div>
        <NumberDisplay value={eur} format="currency" signed />
      </div>
      {pct != null && (
        <div className="text-xs">
          <NumberDisplay value={pct * 100} format="percent" signed />
        </div>
      )}
    </td>
  )
}

function TradeLog() {
  const { data, isLoading } = useRealizedTrades()
  return (
    <Panel
      title="trade log — closed trades"
      meta={data ? `${data.count} trades` : undefined}
      statusDotColor="accent"
    >
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : !data?.trades.length ? (
        <p className="text-sm text-text-label">no closed trades yet (FIFO-matched from the ledger).</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-text-label">
                  <th className="py-2 pr-3 font-normal">position</th>
                  <th className="py-2 px-3 font-normal">bought</th>
                  <th className="py-2 px-3 font-normal">sold</th>
                  <th className="py-2 px-3 text-right font-normal">buy €</th>
                  <th className="py-2 px-3 text-right font-normal">sell €</th>
                  <th className="py-2 px-3 text-right font-normal">realized p&l</th>
                  <th className="py-2 pl-3 text-right font-normal">held</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t, i) => (
                  <tr key={i} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-3 font-mono text-text">{t.ticker}</td>
                    <td className="py-2 px-3 font-mono text-xs text-text-secondary">{t.date_bought}</td>
                    <td className="py-2 px-3 font-mono text-xs text-text-secondary">{t.date_sold}</td>
                    <td className="py-2 px-3 text-right"><NumberDisplay value={t.buy_price_eur} format="currency" /></td>
                    <td className="py-2 px-3 text-right"><NumberDisplay value={t.sell_price_eur} format="currency" /></td>
                    <td className="py-2 px-3 text-right"><NumberDisplay value={t.realized_gain_eur} format="currency" signed /></td>
                    <td className="py-2 pl-3 text-right font-mono text-xs tabular-nums text-text-secondary">{t.holding_days}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Footer: YTD realized total — tax-relevant (German Abgeltungsteuer). */}
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
            <span className="label">ytd realized ({data.year}) — Abgeltungsteuer base</span>
            <span className={cn("font-mono font-medium tabular-nums",
              data.ytd_realized_eur >= 0 ? "text-success" : "text-danger")}>
              {formatCurrency(data.ytd_realized_eur)}
            </span>
          </div>
        </>
      )}
    </Panel>
  )
}

type TransactionDraft = {
  date: string
  ticker: string
  action: (typeof ACTIONS)[number]
  quantity: string
  price: string
  currency: string
  fees: string
  notes: string
}

function draftFrom(t: FinanceTransaction): TransactionDraft {
  return {
    date: t.date,
    ticker: t.ticker,
    action: t.action,
    quantity: String(t.quantity),
    price: String(t.price),
    currency: t.currency,
    fees: String(t.fees),
    notes: t.notes ?? "",
  }
}

/** Full editable buy/sell/dividend/etc. ledger — click a row to edit inline, or delete it.
 *  Backdated edits/deletes trigger the backend's historical backfill (see positions.py). */
function TransactionLedger() {
  const txns = useFinanceTransactions({ limit: 200 })
  const update = useUpdateTransaction()
  const del = useDeleteTransaction()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<TransactionDraft | null>(null)
  // Arm/confirm delete (click trash once to arm, again to confirm) instead of a
  // native window.confirm(), which blocks the page until dismissed.
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  function startEdit(t: FinanceTransaction) {
    setEditingId(t.id)
    setDraft(draftFrom(t))
    setConfirmDeleteId(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setDraft(null)
  }

  function saveEdit(id: string) {
    if (!draft) return
    update.mutate(
      {
        id,
        date: draft.date,
        ticker: draft.ticker.trim().toUpperCase(),
        action: draft.action,
        quantity: Number(draft.quantity),
        price: Number(draft.price),
        currency: draft.currency,
        fees: draft.fees ? Number(draft.fees) : 0,
        notes: draft.notes.trim() || null,
      },
      {
        onSuccess: () => {
          toast.success("transaction updated")
          cancelEdit()
        },
        onError: (e) => toast.error("could not update transaction", String(e)),
      },
    )
  }

  function handleDeleteClick(t: FinanceTransaction) {
    if (confirmDeleteId !== t.id) {
      setConfirmDeleteId(t.id)
      return
    }
    setConfirmDeleteId(null)
    del.mutate(t.id, {
      onSuccess: () => toast.success("transaction deleted"),
      onError: (e) => toast.error("could not delete transaction", String(e)),
    })
  }

  return (
    <Panel
      title="transaction ledger"
      meta={txns.data ? `${txns.data.total} entries` : undefined}
      statusDotColor="muted"
    >
      {txns.isLoading ? (
        <Skeleton className="h-48" />
      ) : txns.isError ? (
        <p className="text-sm text-text-secondary">could not load transactions. backend on :8000?</p>
      ) : !txns.data?.transactions.length ? (
        <p className="text-sm text-text-label">no transactions logged yet.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>date</TableHead>
                <TableHead>ticker</TableHead>
                <TableHead>action</TableHead>
                <TableHead className="text-right">qty</TableHead>
                <TableHead className="text-right">price</TableHead>
                <TableHead>ccy</TableHead>
                <TableHead className="text-right">fees</TableHead>
                <TableHead>notes</TableHead>
                <TableHead className="text-right">edit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {txns.data.transactions.map((t) =>
                editingId === t.id && draft ? (
                  <TableRow key={t.id}>
                    <TableCell>
                      <Input
                        type="date"
                        mono
                        className="h-7 w-32"
                        value={draft.date}
                        onChange={(e) => setDraft((d) => d && { ...d, date: e.target.value })}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        mono
                        className="h-7 w-20"
                        value={draft.ticker}
                        onChange={(e) => setDraft((d) => d && { ...d, ticker: e.target.value })}
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={draft.action}
                        onValueChange={(v) => setDraft((d) => d && { ...d, action: v as TransactionDraft["action"] })}
                      >
                        <SelectTrigger className="h-7 w-24">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ACTIONS.map((a) => (
                            <SelectItem key={a} value={a}>
                              {a}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        mono
                        className="h-7 w-20 text-right"
                        value={draft.quantity}
                        onChange={(e) => setDraft((d) => d && { ...d, quantity: e.target.value })}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        mono
                        className="h-7 w-20 text-right"
                        value={draft.price}
                        onChange={(e) => setDraft((d) => d && { ...d, price: e.target.value })}
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={draft.currency}
                        onValueChange={(v) => setDraft((d) => d && { ...d, currency: v })}
                      >
                        <SelectTrigger className="h-7 w-16">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {["EUR", "USD", "GBP"].map((c) => (
                            <SelectItem key={c} value={c}>
                              {c}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        mono
                        className="h-7 w-16 text-right"
                        value={draft.fees}
                        onChange={(e) => setDraft((d) => d && { ...d, fees: e.target.value })}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        className="h-7 w-32"
                        value={draft.notes}
                        onChange={(e) => setDraft((d) => d && { ...d, notes: e.target.value })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => saveEdit(t.id)}
                          disabled={update.isPending}
                          title="save"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={cancelEdit} title="cancel">
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  <TableRow key={t.id} className="cursor-pointer" onClick={() => startEdit(t)}>
                    <TableCell className="text-xs text-text-label">{t.date}</TableCell>
                    <TableCell className="text-text">{t.ticker}</TableCell>
                    <TableCell className="text-text-secondary">{t.action}</TableCell>
                    <TableCell className="text-right">
                      {t.quantity.toLocaleString("en-US", { maximumFractionDigits: 8 })}
                    </TableCell>
                    <TableCell className="text-right">
                      <NumberDisplay value={t.price} format="currency" />
                    </TableCell>
                    <TableCell className="text-text-label">{t.currency}</TableCell>
                    <TableCell className="text-right text-text-label">
                      {t.fees ? formatCurrency(t.fees) : "—"}
                    </TableCell>
                    <TableCell className="max-w-[10rem] truncate text-xs text-text-secondary">
                      {t.notes || "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {confirmDeleteId === t.id && (
                          <span className="text-xs text-danger">confirm?</span>
                        )}
                        <Pencil className="h-3.5 w-3.5 text-text-disabled" />
                        <Button
                          variant="ghost"
                          size="icon"
                          className={cn(
                            "h-7 w-7",
                            confirmDeleteId === t.id
                              ? "text-danger"
                              : "text-text-label hover:text-danger",
                          )}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDeleteClick(t)
                          }}
                          title={confirmDeleteId === t.id ? "click again to confirm delete" : "delete"}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ),
              )}
            </TableBody>
          </Table>
          <p className="mt-2 text-xs text-text-label">
            click a row to edit inline. backdated changes recompute the daily P&L history.
          </p>
        </>
      )}
    </Panel>
  )
}
