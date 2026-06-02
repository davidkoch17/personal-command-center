import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { CategoryDonut } from "@/components/charts/finance-charts"
import { FactorBetaBars } from "@/components/charts/finance-analytics-charts"
import {
  useFF3,
  useFactorDecomposition,
  useFF5,
  useMomentumFactor,
  type FF3Response,
  type FF5Response,
  type MomentumResponse,
} from "@/hooks/useFinance"
import { CHART_COLORS } from "@/components/charts/theme"
import { InfoTip } from "@/components/ui/info-tip"
import { metricTip } from "@/components/finance/metric-glossary"

const REGIONS = ["US", "Europe", "Global"]

function pct(v: number | null | undefined, d = 1): string {
  return v == null ? "—" : `${(v * 100).toFixed(d)}%`
}

/** Significance hint: |t| ≥ 2 ≈ significant at 95%. */
function sig(t: number | undefined): string {
  if (t == null) return ""
  return Math.abs(t) >= 2 ? "significant" : "not sig."
}

export function FactorsTab() {
  const [region, setRegion] = useState("US")
  const ff3 = useFF3(region)
  const decomp = useFactorDecomposition(region)
  const r: FF3Response | undefined = ff3.data

  const variance = decomp.data?.variance_decomposition
  const pieData = variance
    ? [
        { name: "market", value: variance.market },
        { name: "size (smb)", value: variance.size_smb },
        { name: "value (hml)", value: variance.value_hml },
        { name: "idiosyncratic", value: variance.idiosyncratic },
      ]
    : []

  const betaData = r?.available
    ? [
        { factor: "MKT", beta: r.beta_mkt ?? 0 },
        { factor: "SMB", beta: r.beta_smb ?? 0 },
        { factor: "HML", beta: r.beta_hml ?? 0 },
      ]
    : []

  return (
    <div className="space-y-4">
      <div className="flex w-44 items-center">
        <Select value={region} onValueChange={setRegion}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {REGIONS.map((rg) => (
              <SelectItem key={rg} value={rg}>{rg}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {ff3.isLoading ? (
        <Skeleton className="h-48" />
      ) : !r?.available ? (
        <Panel title="fama-french 3-factor" statusDotColor="muted">
          <p className="text-sm text-text-label">{r?.reason ?? "not available"}</p>
        </Panel>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="fama-french 3-factor regression" meta={`${r.n_observations} months · ${region}`} statusDotColor="accent">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-label">
                    <th className="py-1.5 pr-2 font-normal">term</th>
                    <th className="py-1.5 px-2 text-right font-normal">coef</th>
                    <th className="py-1.5 px-2 text-right font-normal">t-stat</th>
                    <th className="py-1.5 pl-2 text-right font-normal"></th>
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  <FactorRow term="alpha (ann.)" coef={pct(r.alpha_annual)} t={r.t_alpha} />
                  <FactorRow term="β market" coef={(r.beta_mkt ?? 0).toFixed(2)} t={r.t_mkt} />
                  <FactorRow term="β size (SMB)" coef={(r.beta_smb ?? 0).toFixed(2)} t={r.t_smb} />
                  <FactorRow term="β value (HML)" coef={(r.beta_hml ?? 0).toFixed(2)} t={r.t_hml} />
                </tbody>
              </table>
              <div className="mt-3 flex gap-6 text-xs text-text-secondary">
                <span>R² {pct(r.r_squared)}</span>
                <span>n {r.n_observations}</span>
              </div>
            </Panel>

            <Panel title="factor betas" statusDotColor="muted">
              <FactorBetaBars data={betaData} />
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="variance decomposition" meta="what drives your returns" statusDotColor="accent">
              {decomp.isLoading ? (
                <Skeleton className="h-56" />
              ) : pieData.length === 0 ? (
                <p className="text-sm text-text-label">no decomposition</p>
              ) : (
                <CategoryDonut data={pieData} />
              )}
            </Panel>

            <Panel title="interpretation" statusDotColor="muted">
              <InterpretationCard ff3={r} variance={variance} />
            </Panel>
          </div>

          {/* Phase 15e — FF5 (adds RMW + CMA) and Carhart momentum (UMD). */}
          <AdvancedFactorModels region={region} />
        </>
      )}
    </div>
  )
}

const FF5_TERMS: { key: string; label: string }[] = [
  { key: "mkt", label: "β market" },
  { key: "smb", label: "β size (SMB)" },
  { key: "hml", label: "β value (HML)" },
  { key: "rmw", label: "β profitability (RMW)" },
  { key: "cma", label: "β investment (CMA)" },
]

const CARHART_TERMS: { key: string; label: string }[] = [
  { key: "mkt", label: "β market" },
  { key: "smb", label: "β size (SMB)" },
  { key: "hml", label: "β value (HML)" },
  { key: "umd", label: "β momentum (UMD)" },
]

function AdvancedFactorModels({ region }: { region: string }) {
  const ff5 = useFF5(region)
  const carhart = useMomentumFactor(region)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="fama-french 5-factor" meta="adds RMW + CMA" statusDotColor="accent">
        {ff5.isLoading ? (
          <Skeleton className="h-44" />
        ) : (
          <FactorModelTable model={ff5.data} terms={FF5_TERMS} />
        )}
      </Panel>
      <Panel title="carhart 4-factor" meta="FF3 + momentum" statusDotColor="accent">
        {carhart.isLoading ? (
          <Skeleton className="h-44" />
        ) : (
          <FactorModelTable model={carhart.data} terms={CARHART_TERMS} />
        )}
      </Panel>
    </div>
  )
}

function FactorModelTable({
  model,
  terms,
}: {
  model: FF5Response | MomentumResponse | undefined
  terms: { key: string; label: string }[]
}) {
  if (!model?.available) {
    return <p className="text-sm text-text-label">{model?.reason ?? "not available"}</p>
  }
  return (
    <>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-text-label">
            <th className="py-1.5 pr-2 font-normal">term</th>
            <th className="py-1.5 px-2 text-right font-normal">coef</th>
            <th className="py-1.5 px-2 text-right font-normal">t-stat</th>
            <th className="py-1.5 pl-2 text-right font-normal"></th>
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          <FactorRow term="alpha (ann.)" coef={pct(model.alpha_annual)} t={model.t_alpha} />
          {terms.map((t) => (
            <FactorRow
              key={t.key}
              term={t.label}
              coef={(model.betas?.[t.key] ?? 0).toFixed(2)}
              t={model.t_stats?.[t.key]}
            />
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex items-center gap-6 text-xs text-text-secondary">
        <span className="inline-flex items-center gap-1">
          R² {pct(model.r_squared)} <InfoTip text={metricTip("r²") ?? ""} />
        </span>
        <span>n {model.n_observations}</span>
      </div>
    </>
  )
}

function FactorRow({ term, coef, t }: { term: string; coef: string; t: number | undefined }) {
  const significant = t != null && Math.abs(t) >= 2
  return (
    <tr className="border-b border-border/40">
      <td className="py-1.5 pr-2 font-sans text-text">{term}</td>
      <td className="py-1.5 px-2 text-right text-text">{coef}</td>
      <td className="py-1.5 px-2 text-right text-text-secondary">{t?.toFixed(2) ?? "—"}</td>
      <td className={`py-1.5 pl-2 text-right text-[10px] ${significant ? "text-success" : "text-text-label"}`}>
        {sig(t)}
      </td>
    </tr>
  )
}

function InterpretationCard({
  ff3,
  variance,
}: {
  ff3: FF3Response
  variance?: { market: number; size_smb: number; value_hml: number; idiosyncratic: number }
}) {
  const alpha = ff3.alpha_annual ?? 0
  const alphaSig = ff3.t_alpha != null && Math.abs(ff3.t_alpha) >= 2
  const hml = ff3.beta_hml ?? 0
  const smb = ff3.beta_smb ?? 0
  const mktShare = variance?.market ?? 0

  return (
    <div className="space-y-2 text-sm text-text-secondary">
      <p>
        <span className="text-text">{pct(mktShare)}</span> of your return variance is explained
        by the <span className="text-accent">market factor</span>.
      </p>
      <p>
        Annual alpha is <span className={alpha >= 0 ? "text-success" : "text-danger"}>{pct(alpha)}</span>
        {" "}({alphaSig ? "statistically significant" : "not statistically significant"} — |t|={Math.abs(ff3.t_alpha ?? 0).toFixed(1)}).
      </p>
      <p>
        Style tilt: {hml < -0.1 ? "growth" : hml > 0.1 ? "value" : "neutral"} (HML {hml.toFixed(2)}),
        {" "}{smb > 0.1 ? "small-cap" : smb < -0.1 ? "large-cap" : "size-neutral"} (SMB {smb.toFixed(2)}).
      </p>
      <p className="text-xs text-text-label" style={{ color: CHART_COLORS.axis }}>
        FF data: Ken French library, monthly, regressed on excess portfolio returns.
      </p>
    </div>
  )
}
