import { cn, formatCurrency } from "@/lib/utils"
import type { NetworthAccounts, NetworthHolding } from "@/hooks/useNetworth"

function pctLabel(pct: number | null): string {
  if (pct == null) return "—"
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`
}

function pctClass(pct: number | null): string {
  if (pct == null) return "text-text-label"
  return pct > 0 ? "text-invest" : pct < 0 ? "text-danger" : "text-text-label"
}

function HoldingRow({ h }: { h: NetworthHolding }) {
  return (
    <div className="flex flex-col gap-0.5 border-t border-border/60 py-2 pl-4 first:border-t-0">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-text">{h.ticker}</span>
        <span className="font-mono text-sm tabular-nums text-text">{formatCurrency(h.value)}</span>
      </div>
      <div className="flex items-center gap-3 font-mono text-xs tabular-nums text-text-secondary">
        <span>
          1M: <span className={pctClass(h.pct_1m)}>{pctLabel(h.pct_1m)}</span>
        </span>
        <span>
          1Y: <span className={pctClass(h.pct_1y)}>{pctLabel(h.pct_1y)}</span>
        </span>
        <span>
          Gain:{" "}
          <span className={cn(h.gain == null ? "text-text-label" : h.gain >= 0 ? "text-invest" : "text-danger")}>
            {h.gain == null ? "—" : `${h.gain >= 0 ? "+" : ""}${formatCurrency(h.gain)}`}
          </span>
        </span>
      </div>
    </div>
  )
}

/** Section 4 — hierarchical CASH / PORTFOLIO breakdown. Future holdings/accounts
 * are listed automatically; no per-asset wiring needed. */
export function AccountsHierarchy({ accounts }: { accounts: NetworthAccounts }) {
  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center justify-between pb-1.5">
          <span className="label">cash</span>
          <span className="font-mono text-sm tabular-nums text-text">{formatCurrency(accounts.cash.total)}</span>
        </div>
        {accounts.cash.accounts.map((a) => (
          <div key={a.name} className="flex items-center justify-between border-t border-border/60 py-2 pl-4 text-sm">
            <span className="text-text-secondary">{a.name}</span>
            <span className="font-mono tabular-nums text-text">{formatCurrency(a.value)}</span>
          </div>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between pb-1.5">
          <span className="label">portfolio</span>
          <span className="font-mono text-sm tabular-nums text-text">{formatCurrency(accounts.portfolio.total)}</span>
        </div>
        {accounts.portfolio.holdings.length === 0 ? (
          <p className="pl-4 py-2 text-sm text-text-label">no holdings yet</p>
        ) : (
          accounts.portfolio.holdings.map((h) => <HoldingRow key={h.ticker} h={h} />)
        )}
      </div>
    </div>
  )
}
