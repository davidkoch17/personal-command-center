"""Alpha Vantage news sentiment API.

Free tier: 5 req/min, 100/day — plenty for the weekly Market Researcher run.
Returns an empty list when ``ALPHA_VANTAGE_KEY`` is missing or the call fails.
"""
from __future__ import annotations

import os

from core.config import get_logger

logger = get_logger(__name__)


def is_configured() -> bool:
    """True when the Alpha Vantage key is present."""
    return bool(os.getenv("ALPHA_VANTAGE_KEY"))


def ticker_news_with_sentiment(ticker: str, limit: int = 10) -> list[dict]:
    """Return Alpha Vantage news + sentiment for a ticker."""
    key = os.getenv("ALPHA_VANTAGE_KEY")
    if not key:
        return []
    try:
        import httpx

        r = httpx.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": key,
                "limit": limit,
            },
            timeout=20,
        )
        data = r.json()
        feed = data.get("feed", []) or []
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "time_published": item.get("time_published", ""),
                "summary": item.get("summary", ""),
                "overall_sentiment": item.get("overall_sentiment_label", ""),
            }
            for item in feed
        ]
    except Exception as e:  # noqa: BLE001
        logger.warning("alpha vantage news failed for %s: %s", ticker, e)
        return []
