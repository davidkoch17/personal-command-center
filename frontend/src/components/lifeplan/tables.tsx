import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import type { LifePlanInputs, LifePlanResult } from "@/hooks/useLifeplan"
import { NumInput } from "./controls"
import type { SetPath } from "./drivers-panel"
import { eur, pct } from "./format"

function Th({ children, left }: { children: ReactNode; left?: boolean }) {
  return (
    <th className={cn("sticky top-0 z-10 whitespace-nowrap bg-bg-panel px-2 py-1.5 font-medium text-text-label", left ? "text-left" : "text-right")}>
      {children}
    </th>
  )
}

function Td({ children, left, className }: { children: ReactNode; left?: boolean; className?: string }) {
  return <td className={cn("whitespace-nowrap px-2 py-1 font-mono tabular-nums", left ? "text-left" : "text-right", className)}>{children}</td>
}

/** Compact version of the Excel "Zeitachse" tab. */
export function TimelineTable({ result }: { result: LifePlanResult }) {
  return (
    <div className="max-h-[560px] overflow-auto rounded border border-border">
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr className="border-b border-border">
            <Th left>Jahr</Th>
            <Th>Alter</Th>
            <Th>Gehalt brutto</Th>
            <Th>Partnerin</Th>
            <Th>Steuern+Abg.</Th>
            <Th>Netto Haushalt</Th>
            <Th>Ausg. %</Th>
            <Th>Ausgaben</Th>
            <Th>Sparen</Th>
            <Th>Käufe (EK)</Th>
            <Th>Restschuld</Th>
            <Th>Liquide</Th>
            <Th>Sachwerte</Th>
            <Th>Nettovermögen</Th>
            <Th left>Check</Th>
          </tr>
        </thead>
        <tbody>
          {result.years.map((y) => (
            <tr key={y.year} className={cn("border-b border-border/50", y.warning && "bg-danger/10", y.goal_reached && "bg-success/10")}>
              <Td left>{y.year}</Td>
              <Td>{y.age}</Td>
              <Td>{eur(y.salary)}</Td>
              <Td>{eur(y.partner_gross)}</Td>
              <Td>{eur(y.social + y.partner_social + y.income_tax + y.soli_church)}</Td>
              <Td>{eur(y.net_income)}</Td>
              <Td>{pct(y.spend_pct, 0)}</Td>
              <Td>{eur(y.spending)}</Td>
              <Td className={y.savings < 0 ? "text-danger" : undefined}>{eur(y.savings)}</Td>
              <Td>{y.purchases ? eur(y.purchases) : "–"}</Td>
              <Td>{y.debt ? eur(y.debt) : "–"}</Td>
              <Td className={y.liquid < 0 ? "text-danger" : undefined}>{eur(y.liquid)}</Td>
              <Td>{eur(y.real_assets)}</Td>
              <Td className="font-semibold">{eur(y.net_worth)}</Td>
              <Td left className="text-danger">
                {y.goal_reached ? <span className="text-success">✅ Ziel</span> : y.warning}
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Excel "Meilensteine" tab + "financeable in the purchase year?". */
export function MilestonesTable({ result }: { result: LifePlanResult }) {
  return (
    <div className="space-y-3">
      <div className="overflow-auto rounded border border-border">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr className="border-b border-border">
              <Th left>Meilenstein</Th>
              <Th>Kauf mit</Th>
              <Th>Kaufpreis inkl. NK</Th>
              <Th>Kredit</Th>
              <Th>Eigenkapital</Th>
              <Th>davon NK weg</Th>
              <Th>Reserve danach</Th>
              <Th>Liquide nötig</Th>
              <Th>Ausgaben / Mon.</Th>
              <Th>Nötig brutto / J.</Th>
              <Th left>Finanzierbar?</Th>
            </tr>
          </thead>
          <tbody>
            {result.milestones.map((m) => (
              <tr key={m.idx} className="border-b border-border/50">
                <Td left className="font-sans">{m.label}</Td>
                <Td>{m.purchase_age == null ? "–" : m.purchase_age >= 999 ? "nie" : `${m.purchase_age} (${m.purchase_year ?? "–"})`}</Td>
                <Td>{eur(m.purchase_price)}</Td>
                <Td>{eur(m.loan)}</Td>
                <Td>{eur(m.equity)}</Td>
                <Td>{eur(m.fees_lost)}</Td>
                <Td>{eur(m.reserve)}</Td>
                <Td>{eur(m.liquid_needed)}</Td>
                <Td>{eur(m.spending)}</Td>
                <Td>{eur(m.gross_income_needed)}</Td>
                <Td left>
                  {m.financeable == null ? (
                    <span className="text-text-label">–</span>
                  ) : m.financeable ? (
                    <span className="text-success">ja</span>
                  ) : (
                    <span className="text-danger">⚠ nein</span>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-text-label">
        Ziel-Vermögen {eur(result.summary.target)} = Häuser & Autos schuldenfrei ({eur(result.one_off_total)}) + Depot für
        Lebenshaltung & Autowertverlust + Reserve. „Finanzierbar“ = im Kaufjahr keine Warnung (Liquidität ≥ 0 und ≥ 6 Monate Reserve).
      </p>
    </div>
  )
}

const RUNNING: [string, string][] = [
  ["house_munich", "Haus Grünwald: Instandhaltung, Energie, Steuer"],
  ["house_cape", "Haus Kapstadt: Rates, Instandhaltung, Security"],
  ["household_help", "Haushaltshilfe, Reinigung, Gärtner"],
  ["cars", "3 Autos: Versicherung, Steuer, Wartung (nur Info)"],
  ["groceries", "Lebensmittel & Haushalt"],
  ["dining", "Essen gehen"],
  ["kids", "Kinder: Schule, Hobbys (nur Meilensteine)"],
  ["travel", "Reisen"],
  ["leisure", "Freizeit"],
  ["insurance", "PKV Familie, BU (nur Meilensteine)"],
  ["misc", "Sonstiges"],
]

/** Editable dream-life costs: one-off purchases + running monthly costs. */
export function DreamCosts({ inputs, result, set }: { inputs: LifePlanInputs; result: LifePlanResult; set: SetPath }) {
  const oneOff = result.one_off
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <div>
        <div className="text-[11px] font-medium tracking-wider text-text-label mb-2">Einmalig</div>
        <div className="overflow-auto rounded border border-border">
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-border">
                <Th left>Was</Th>
                <Th>Spanne</Th>
                <Th>Ansatz</Th>
                <Th>NK</Th>
                <Th>Gesamt</Th>
              </tr>
            </thead>
            <tbody>
              {oneOff.map((row) => {
                const key = row.key as keyof LifePlanInputs["one_off"]
                const src = inputs.one_off[key]
                return (
                  <tr key={row.key} className="border-b border-border/50">
                    <Td left className="font-sans">{row.label}</Td>
                    <Td className="text-text-label">{src ? `${eur(src.low)} – ${eur(src.high)}` : "R 20 Mio"}</Td>
                    <Td>
                      {src ? (
                        <NumInput kind="eur" value={src.price} onChange={(v) => set(["one_off", key, "price"], v)} className="ml-auto w-[120px]" />
                      ) : (
                        eur(row.price)
                      )}
                    </Td>
                    <Td>{pct(row.fees_pct)}</Td>
                    <Td>{eur(row.total)}</Td>
                  </tr>
                )
              })}
              <tr className="font-semibold">
                <Td left className="font-sans">Summe</Td>
                <Td> </Td>
                <Td> </Td>
                <Td> </Td>
                <Td>{eur(result.one_off_total)}</Td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[10px] text-text-label">Kapstadt: R 20 Mio / Wechselkurs (Weitere Annahmen). Nebenkosten-% der Häuser ebenfalls dort.</p>
      </div>
      <div>
        <div className="text-[11px] font-medium tracking-wider text-text-label mb-2">Laufend (€/Monat, Endzustand)</div>
        <div className="rounded border border-border p-2">
          {RUNNING.map(([key, label]) => (
            <label key={key} className="grid grid-cols-[1fr_120px] items-center gap-2 py-0.5">
              <span className="text-xs text-text-secondary">{label}</span>
              <NumInput kind="eur" value={inputs.running[key]} onChange={(v) => set(["running", key], v)} />
            </label>
          ))}
          <label className="grid grid-cols-[1fr_120px] items-center gap-2 py-0.5">
            <span className="text-xs text-text-secondary">Puffer</span>
            <NumInput kind="pct" value={inputs.running.buffer} onChange={(v) => set(["running", "buffer"], v)} />
          </label>
          <div className="mt-2 flex justify-between border-t border-border pt-2 text-xs">
            <span className="text-text-secondary">Summe inkl. Puffer</span>
            <span className="font-mono font-semibold">{eur(result.running_total_monthly)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-text-secondary">davon Lifestyle variabel (100 %)</span>
            <span className="font-mono">{eur(result.lifestyle_variable_monthly)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
