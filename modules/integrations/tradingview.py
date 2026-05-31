"""TradingView mini-chart embed helpers. No credentials required."""
from __future__ import annotations

# Best-effort map from David's holding/watchlist display names to TradingView
# symbols. Falls back to the cleaned name when unmapped.
_SYMBOL_MAP = {
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "ALIBABA": "BABA",
    "BYD": "BYDDY",
    "SOLANA": "SOLEUR",
    "SOL": "SOLEUR",
    "BITCOIN": "BTCEUR",
    "BTC": "BTCEUR",
    "ETHEREUM": "ETHEUR",
    "ETH": "ETHEUR",
    "NIKE": "NKE",
}


def guess_symbol(name_or_ticker: str) -> str:
    """Map a holding/watchlist label to a TradingView symbol (best effort)."""
    s = (name_or_ticker or "").strip()
    if not s:
        return ""
    key = s.upper()
    if key in _SYMBOL_MAP:
        return _SYMBOL_MAP[key]
    # Strip a parenthetical ticker, e.g. "Alphabet (GOOGL)" -> "GOOGL".
    if "(" in s and ")" in s:
        inner = s[s.rfind("(") + 1 : s.rfind(")")].strip()
        if inner:
            return inner.upper()
    return key


def mini_chart_html(symbol: str, width: int = 350, height: int = 220) -> str:
    """Return an HTML string for a TradingView mini chart widget."""
    return f"""
    <div class="tradingview-widget-container">
      <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_{symbol}&symbol={symbol}&interval=W&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=f1f3f6&studies=&theme=dark&style=2&timezone=Europe/Berlin&studies_overrides={{}}&overrides={{}}&enabled_features=&disabled_features=&locale=en&hide_legend=true"
        width="{width}" height="{height}" frameborder="0" allowtransparency="true" scrolling="no">
      </iframe>
    </div>
    """
