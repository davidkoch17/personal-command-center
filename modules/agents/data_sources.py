"""Free data sources for the Market Researcher agent.

All sources are free and key-less (yfinance, SEC EDGAR). FRED macro data is
wired separately via ``fredapi`` once David adds a free key to ``.env``.
"""
from __future__ import annotations

from datetime import datetime

import requests
import yfinance as yf

from core.config import get_logger

logger = get_logger(__name__)

# SEC requires a descriptive User-Agent on every request.
_SEC_HEADERS = {"User-Agent": "Personal Command Center davidkoch2105@gmail.com"}


def price_snapshot(ticker: str) -> dict:
    """Friday close, week change, 30d change, plus currency context."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="35d")
        if hist.empty:
            return {"ticker": ticker, "error": "no data"}
        last = hist["Close"].iloc[-1]
        week_ago = hist["Close"].iloc[-5] if len(hist) >= 5 else hist["Close"].iloc[0]
        month_ago = hist["Close"].iloc[0]
        try:
            currency = t.info.get("currency", "USD") if t.info else "USD"
        except Exception:  # noqa: BLE001 - .info can throw on rate limit
            currency = "USD"
        return {
            "ticker": ticker,
            "last_close": float(last),
            "week_change_pct": float((last - week_ago) / week_ago * 100),
            "month_change_pct": float((last - month_ago) / month_ago * 100),
            "currency": currency,
        }
    except Exception as e:  # noqa: BLE001 - surface error to the brief, don't crash
        logger.warning("price_snapshot failed for %s: %s", ticker, e)
        return {"ticker": ticker, "error": str(e)}


def ticker_news(ticker: str, limit: int = 10) -> list[dict]:
    """Recent news headlines for a ticker from Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        news = t.news or []
        out: list[dict] = []
        for n in news[:limit]:
            # yfinance has shifted between a flat schema and a nested
            # {"content": {...}} schema; handle both.
            content = n.get("content", n)
            title = content.get("title") or n.get("title", "")
            publisher = ""
            provider = content.get("provider") or {}
            if isinstance(provider, dict):
                publisher = provider.get("displayName", "")
            publisher = publisher or n.get("publisher", "")
            link = n.get("link", "")
            if not link:
                cu = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
                if isinstance(cu, dict):
                    link = cu.get("url", "")
            ts = n.get("providerPublishTime")
            publish_time = ""
            if ts:
                try:
                    publish_time = datetime.fromtimestamp(ts).isoformat()
                except (OSError, ValueError, OverflowError):
                    publish_time = ""
            elif content.get("pubDate"):
                publish_time = str(content.get("pubDate"))
            out.append(
                {
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "publish_time": publish_time,
                }
            )
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("ticker_news failed for %s: %s", ticker, e)
        return []


def sec_filings(ticker: str, days_back: int = 30) -> list[dict]:
    """Recent SEC filings via EDGAR.

    Returns a list of dicts. EDGAR atom parsing is non-trivial, so for v1 this
    returns a pointer URL for the agent to mention rather than parsed filings.
    """
    try:
        url = (
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={ticker}&type=&dateb=&owner=include&count=20&output=atom"
        )
        resp = requests.get(url, headers=_SEC_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        return [
            {
                "note": (
                    "See https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={ticker}&type=10-K&dateb=&owner=include&count=10 for filings"
                )
            }
        ]
    except Exception as e:  # noqa: BLE001
        logger.warning("sec_filings failed for %s: %s", ticker, e)
        return []
