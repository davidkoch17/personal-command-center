import type { ReactNode } from "react"
import { Collapsible } from "@/components/ui/collapsible"
import { Toggle } from "@/components/ui/toggle"
import type { LifePlanInputs, LiveWealth, MilestoneKey } from "@/hooks/useLifeplan"
import { Check, NumField, NumInput, Section, SliderField, type NumKind } from "./controls"
import { eur, pct } from "./format"

export type SetPath = (path: (string | number)[], value: unknown) => void

const NEVER = 999
const SCHOOL_INTL = 2300
const SCHOOL_GYM = 600

export const MILESTONE_LABELS: Record<MilestoneKey, string> = {
  main_car: "Main Car",
  fun_car: "Spaßauto / Oldtimer",
  house_munich: "Familienhaus Grünwald",
  sports_car: "Sportwagen",
  house_cape: "Haus Kapstadt",
}
const MILESTONE_ORDER: MilestoneKey[] = ["main_car", "fun_car", "house_munich", "sports_car", "house_cape"]

/** "Weitere Annahmen": every Annahmen input not shown as a main driver. */
const MORE_ASSUMPTIONS: { group: string; items: [string, string, NumKind][] }[] = [
  {
    group: "Rendite & Entnahme",
    items: [
      ["return_liquid", "Rendite liquides Vermögen (real, n. St.)", "pct"],
      ["withdrawal_rate", "Entnahmerate Depot", "pct"],
      ["withdrawal_tax", "Steuer-/Kostenabzug auf Entnahmen", "pct"],
      ["reserve_months", "Notgroschen (Monatsausgaben)", "num"],
    ],
  },
  {
    group: "Immobilien & Kredit",
    items: [
      ["mortgage_rate", "Bauzins 10 J.", "pct"],
      ["amortization", "Anfangstilgung", "pct"],
      ["ltv", "Beleihung (Finanzierungsanteil)", "pct"],
      ["de_transfer_tax", "Grunderwerbsteuer Bayern", "pct"],
      ["de_notary", "Notar & Grundbuch", "pct"],
      ["de_broker", "Makler (Käuferanteil)", "pct"],
      ["fx_eur_zar", "Wechselkurs EUR/ZAR", "num"],
      ["za_transfer_duty", "ZA Transfer Duty", "pct"],
      ["za_legal", "ZA Anwalt & Gebühren", "pct"],
      ["za_equity_share", "ZA Eigenkapitalanteil Kapstadt", "pct"],
    ],
  },
  {
    group: "Steuern & Sozialabgaben",
    items: [
      ["werbungskosten", "Werbungskostenpauschale", "eur"],
      ["health_deductible", "Abzugsf. KV/PV je Erwachsener (€/J.)", "eur"],
      ["bbg", "BBG Renten-/ALV (€/J.)", "eur"],
      ["pension_rate", "Rentenversicherung AN", "pct"],
      ["unemployment_rate", "Arbeitslosenversicherung AN", "pct"],
      ["soli_threshold", "Soli-Freigrenze (ledig)", "eur"],
      ["church_tax", "Kirchensteuer (auf ESt)", "pct"],
    ],
  },
  {
    group: "Versicherungen (€/Monat)",
    items: [
      ["employer_pkv", "AG-Zuschuss PKV/PV", "eur"],
      ["pkv_self", "PKV eigen", "eur"],
      ["pkv_partner", "PKV Partnerin (ab Heirat)", "eur"],
      ["pkv_child", "PKV je Kind", "eur"],
      ["bu_insurance", "BU / Risiko-LV", "eur"],
    ],
  },
  {
    group: "Wohnen & Leben (€/Monat)",
    items: [
      ["rent_today", "Miete heute", "eur"],
      ["rent_family", "Miete Familienwohnung (ab 1. Kind)", "eur"],
      ["min_living", "Mindest-Lebenshaltung ohne Miete", "eur"],
      ["living_today", "Leben heute (nur Meilensteine)", "eur"],
      ["travel_before_cape", "Reisen vor Kapstadt-Haus", "eur"],
    ],
  },
  {
    group: "Kinder (€/Monat je Kind)",
    items: [
      ["child_0_5", "Kind 0–5: Betreuung & Kosten", "eur"],
      ["child_6_18", "Kind 6–18: Schule & Kosten", "eur"],
      ["child_19_24", "Kind 19–24: Studium", "eur"],
    ],
  },
  {
    group: "Autos",
    items: [
      ["upkeep_main_car", "Unterhalt Main Car (€/Mon.)", "eur"],
      ["upkeep_sports_car", "Unterhalt Sportwagen (€/Mon.)", "eur"],
      ["upkeep_fun_car", "Unterhalt Oldtimer (€/Mon.)", "eur"],
      ["depr_main_car", "Wertverlust Main Car p.a.", "pct"],
      ["depr_sports_car", "Wertverlust Sportwagen p.a.", "pct"],
      ["depr_fun_car", "Wertverlust Oldtimer p.a.", "pct"],
    ],
  },
  {
    group: "Nur Tab Meilensteine",
    items: [
      ["net_ratio", "Netto-Quote (Netto/Brutto)", "pct"],
      ["partner_net_monthly", "Einkommen Partnerin netto (€/Mon.)", "eur"],
    ],
  },
]

/** Age field with a "nie / kein" checkbox that maps to 999. */
function AgeOrNever({
  label,
  value,
  onChange,
  min,
  max,
  neverLabel = "nie",
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  neverLabel?: string
}) {
  const never = value >= NEVER
  return (
    <SliderField
      label={label}
      value={never ? max : value}
      onChange={onChange}
      min={min}
      max={max}
      kind="age"
      disabled={never}
      display={never ? neverLabel : undefined}
      right={
        <Check
          checked={never}
          onChange={(v) => onChange(v ? NEVER : Math.round((min + max) / 2))}
          label={neverLabel}
        />
      }
    />
  )
}

export function DriversPanel({
  inputs,
  set,
  live,
}: {
  inputs: LifePlanInputs
  set: SetPath
  live: LiveWealth | null
}) {
  const a = inputs.assumptions
  const path = inputs.career.path
  const stages = inputs.career.paths[path] ?? []
  const mdIdx = stages.findIndex((s) => s.name.trim().toUpperCase() === "MD")
  const mdTableAge = mdIdx >= 0 ? stages[mdIdx].age : 37
  const school = a.child_6_18 === SCHOOL_INTL ? "intl" : a.child_6_18 === SCHOOL_GYM ? "gym" : "custom"
  const fromDashboard = inputs.start.wealth_source === "dashboard"

  return (
    <div className="space-y-3">
      <div className="panel space-y-3">
        <Section title="Start">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs text-text-secondary">Startvermögen</span>
            <Toggle
              value={inputs.start.wealth_source}
              onChange={(v) => set(["start", "wealth_source"], v)}
              options={[
                { value: "dashboard", label: "aus Dashboard" },
                { value: "manual", label: "manuell" },
              ]}
            />
          </div>
          {fromDashboard ? (
            <p className="py-1 text-right font-mono text-xs text-text">
              {live ? (
                <>
                  {eur(live.total)} <span className="text-text-label">· Stand {live.date}</span>
                </>
              ) : (
                <span className="text-warning">kein Snapshot – nutze manuellen Wert</span>
              )}
            </p>
          ) : (
            <NumField label="Vermögen heute" kind="eur" value={inputs.start.start_wealth} onChange={(v) => set(["start", "start_wealth"], v)} />
          )}
          <NumField label="Startjahr der Planung" value={inputs.start.start_year} onChange={(v) => set(["start", "start_year"], Math.round(v))} />
          <NumField label="Geburtsjahr" value={inputs.start.birth_year} onChange={(v) => set(["start", "birth_year"], Math.round(v))} />
        </Section>

        <Section title="Karriere" meta={path}>
          <SliderField
            label="Bonus-Faktor"
            value={inputs.career.bonus_factor}
            onChange={(v) => set(["career", "bonus_factor"], v)}
            min={0.5}
            max={1.5}
            step={0.05}
            display={pct(inputs.career.bonus_factor, 0)}
          />
          <SliderField
            label="MD ab Alter"
            value={inputs.career.md_age ?? mdTableAge}
            onChange={(v) => set(["career", "md_age"], v === mdTableAge ? null : v)}
            min={30}
            max={50}
            kind="age"
          />
          <SliderField
            label="Arbeiten bis Alter"
            value={inputs.career.work_until_age}
            onChange={(v) => set(["career", "work_until_age"], v)}
            min={35}
            max={75}
            kind="age"
          />
          <details className="mt-1">
            <summary className="cursor-pointer text-[11px] text-text-label hover:text-text">
              Gehaltstabelle bearbeiten ({stages.length} Stufen)
            </summary>
            <div className="mt-2 grid grid-cols-[1fr_44px_78px_78px] gap-1 text-[10px] text-text-label">
              <span>Stufe</span>
              <span className="text-right">ab</span>
              <span className="text-right">Fix</span>
              <span className="text-right">Bonus</span>
              {stages.map((s, i) => (
                <StageRow key={i} name={s.name}>
                  <NumInput kind="num" value={s.age} onChange={(v) => set(["career", "paths", path, i, "age"], v)} />
                  <NumInput kind="eur" value={s.fix} onChange={(v) => set(["career", "paths", path, i, "fix"], v)} />
                  <NumInput kind="eur" value={s.bonus} onChange={(v) => set(["career", "paths", path, i, "bonus"], v)} />
                </StageRow>
              ))}
            </div>
            <p className="mt-1 text-[10px] text-text-label">
              Bonus-Faktor und MD-Regler wirken auf diese Tabelle (ab Director verschoben).
            </p>
          </details>
        </Section>

        <Section title="Ausgaben" meta="% vom Traumbudget">
          {inputs.spending.bands.map((b, i) => (
            <div key={i} className="grid grid-cols-[64px_1fr] items-end gap-2">
              <div>
                <span className="text-[10px] text-text-label">ab Alter</span>
                <NumInput kind="age" value={b.age} onChange={(v) => set(["spending", "bands", i, "age"], v)} />
              </div>
              <SliderField
                label=" "
                value={b.pct}
                onChange={(v) => set(["spending", "bands", i, "pct"], v)}
                min={0}
                max={1}
                step={0.05}
                display={pct(b.pct, 0)}
              />
            </div>
          ))}
          <p className="mt-1 text-[10px] text-text-label">Ab Erreichen des Ziel-Vermögens: 100 %.</p>
        </Section>

        <Section title="Familie">
          <AgeOrNever label="Heirat ab Alter" value={inputs.family.marriage_age} onChange={(v) => set(["family", "marriage_age"], v)} min={22} max={50} />
          <SliderField
            label="Einkommen Partnerin brutto (€/J.)"
            value={inputs.family.partner_gross}
            onChange={(v) => set(["family", "partner_gross"], v)}
            min={0}
            max={250_000}
            step={5000}
            kind="eur"
          />
          <AgeOrNever label="1. Kind mit Alter" value={inputs.family.child1_age} onChange={(v) => set(["family", "child1_age"], v)} min={22} max={50} neverLabel="kein" />
          <AgeOrNever label="2. Kind mit Alter" value={inputs.family.child2_age} onChange={(v) => set(["family", "child2_age"], v)} min={22} max={50} neverLabel="kein" />
          <div className="flex items-center justify-between py-1">
            <span className="text-xs text-text-secondary">Schule (Kind 6–18)</span>
            <Toggle
              value={school}
              onChange={(v) => {
                if (v === "intl") set(["assumptions", "child_6_18"], SCHOOL_INTL)
                if (v === "gym") set(["assumptions", "child_6_18"], SCHOOL_GYM)
              }}
              options={[
                { value: "intl", label: "international" },
                { value: "gym", label: "gymnasium" },
                ...(school === "custom" ? [{ value: "custom" as const, label: eur(a.child_6_18) }] : []),
              ]}
            />
          </div>
        </Section>

        <Section title="Meilensteine" meta="Kauf mit Alter">
          {MILESTONE_ORDER.map((k) => (
            <AgeOrNever key={k} label={MILESTONE_LABELS[k]} value={inputs.milestones[k]} onChange={(v) => set(["milestones", k], v)} min={25} max={75} />
          ))}
        </Section>
      </div>

      <Collapsible title="Weitere Annahmen" meta={`${MORE_ASSUMPTIONS.reduce((n, g) => n + g.items.length, 0)} Werte`}>
        <div className="space-y-3">
          {MORE_ASSUMPTIONS.map((g) => (
            <div key={g.group}>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-text-label">{g.group}</div>
              {g.items.map(([key, label, kind]) => (
                <NumField key={key} label={label} kind={kind} value={a[key]} onChange={(v) => set(["assumptions", key], v)} />
              ))}
            </div>
          ))}
        </div>
      </Collapsible>
    </div>
  )
}

function StageRow({ name, children }: { name: string; children: ReactNode }) {
  return (
    <>
      <span className="truncate self-center text-[11px] text-text-secondary" title={name}>
        {name}
      </span>
      {children}
    </>
  )
}
