/**
 * TradingView mini chart embed via the public widget iframe (no script/API key).
 * The symbol is best-effort — TradingView resolves bare tickers to a venue. For
 * names it can't resolve, the widget shows its own "invalid symbol" state.
 */
interface TradingViewProps {
  symbol: string
  height?: number
}

export function TradingView({ symbol, height = 320 }: TradingViewProps) {
  const clean = symbol.trim().toUpperCase()
  const src =
    "https://s.tradingview.com/widgetembed/?" +
    new URLSearchParams({
      symbol: clean,
      interval: "D",
      theme: "dark",
      style: "1",
      hide_side_toolbar: "1",
      hide_top_toolbar: "0",
      allow_symbol_change: "1",
      saveimage: "0",
    }).toString()

  return (
    <div className="overflow-hidden rounded border border-border">
      <iframe
        title={`tradingview-${clean}`}
        src={src}
        width="100%"
        height={height}
        frameBorder={0}
        allowTransparency
        scrolling="no"
        className="block bg-bg-panel"
      />
    </div>
  )
}
