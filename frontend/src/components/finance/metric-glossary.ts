/**
 * Plain-language definitions for every finance metric surfaced in the UI
 * (Phase 15e, Section 5). Keyed by the lowercase label used in panels; look up
 * with `metricTip(label)` so an unknown label just renders no tooltip.
 */
export const METRIC_TOOLTIPS: Record<string, string> = {
  // Performance
  twr: "Time-weighted return — the portfolio's compounded return over the period, neutral to the timing of your deposits and withdrawals.",
  "mwr (irr)": "Money-weighted return (IRR/XIRR) — your actual realized return, accounting for when cash went in and out.",
  "ann. return": "Annualized return — the period return scaled to a yearly rate.",
  alpha: "Alpha — return above what the benchmark's risk (beta) would predict; annualized. Positive = outperformance.",
  beta: "Beta — sensitivity to the benchmark. 1.0 moves with the market; >1 amplifies, <1 dampens.",
  "info ratio": "Information ratio — excess return over the benchmark divided by tracking error. Higher = more consistent outperformance.",
  // Risk
  sharpe: "Sharpe ratio — excess return over the risk-free rate per unit of total volatility, annualized. Higher is better.",
  sortino: "Sortino ratio — like Sharpe but penalizes only downside volatility, ignoring upside swings.",
  calmar: "Calmar ratio — annualized return divided by the maximum drawdown. Reward per unit of worst-case loss.",
  "vol 30d": "Annualized volatility from the last 30 days of daily returns.",
  "vol 90d": "Annualized volatility from the last 90 days of daily returns.",
  "vol 12m": "Annualized volatility over the trailing 12 months.",
  "max drawdown": "Largest peak-to-trough decline over the period — the worst loss you'd have endured holding through.",
  herfindahl: "Herfindahl index — sum of squared position weights. Higher = more concentrated (1.0 = a single holding).",
  "effective bets": "Effective number of bets — 1 / Herfindahl. How many equally-weighted independent positions your concentration is equivalent to.",
  "value at risk": "Value at Risk — the loss your portfolio is not expected to exceed on a normal day at the stated confidence (e.g. 95%).",
  "cvar (es)": "Conditional VaR / Expected Shortfall — the average loss on the worst days beyond the VaR threshold.",
  // Factors
  "alpha (annual)": "Annualized alpha from the factor regression — return unexplained by the factor exposures.",
  "r²": "R-squared — share of the portfolio's return variance explained by the factor model (0–1).",
  mkt: "Market factor (MKT) — exposure to the broad equity market premium.",
  smb: "SMB (size) — exposure to small-cap minus large-cap stocks.",
  hml: "HML (value) — exposure to high book-to-market (value) minus growth stocks.",
  rmw: "RMW (profitability) — exposure to robust minus weak operating profitability.",
  cma: "CMA (investment) — exposure to conservative minus aggressive corporate investment.",
  umd: "UMD (momentum) — exposure to recent winners minus losers (Carhart momentum factor).",
  // Attribution
  allocation: "Allocation effect — value added by over/under-weighting buckets that beat or lagged the benchmark.",
  selection: "Selection effect — value added by picking better-than-benchmark holdings within each bucket.",
  interaction: "Interaction effect — the cross term between allocation and selection decisions.",
  // Currency
  "currency contribution": "How much of the unhedged return came from EUR/USD moves rather than the assets themselves.",
  hedged: "Return with currency drift removed — the assets' performance in their own currencies.",
  unhedged: "Return including currency drift — what you actually experience in your reporting currency.",
}

export function metricTip(label: string): string | undefined {
  return METRIC_TOOLTIPS[label.toLowerCase().trim()]
}
