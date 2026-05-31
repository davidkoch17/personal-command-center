"""Run health checks on each integration."""
import os


def check_outlook() -> dict:
    url = os.getenv("OUTLOOK_ICAL_URL")
    if not url:
        return {"name": "Outlook calendar", "status": "not_configured"}
    try:
        from modules.integrations.calendar_ical import fetch_events
        events = fetch_events(days_ahead=7)
        return {"name": "Outlook calendar", "status": "ok", "detail": f"{len(events)} events in next 7 days"}
    except Exception as e:  # noqa: BLE001
        return {"name": "Outlook calendar", "status": "error", "detail": str(e)[:200]}


def check_github() -> dict:
    if not (os.getenv("GITHUB_PAT") and os.getenv("GITHUB_USERNAME")):
        return {"name": "GitHub", "status": "not_configured"}
    try:
        from modules.integrations.github import recent_commits
        commits = recent_commits(limit=1)
        return {"name": "GitHub", "status": "ok", "detail": f"{len(commits)} recent commits"}
    except Exception as e:  # noqa: BLE001
        return {"name": "GitHub", "status": "error", "detail": str(e)[:200]}


def check_alpha_vantage() -> dict:
    if not os.getenv("ALPHA_VANTAGE_KEY"):
        return {"name": "Alpha Vantage", "status": "not_configured"}
    try:
        from modules.integrations.news_api import ticker_news_with_sentiment
        news = ticker_news_with_sentiment("AAPL", limit=1)  # noqa: F841
        return {"name": "Alpha Vantage", "status": "ok", "detail": "API reachable"}
    except Exception as e:  # noqa: BLE001
        return {"name": "Alpha Vantage", "status": "error", "detail": str(e)[:200]}


# stubs (placeholders for skipped integrations — still show in diagnostics)
def check_kraken() -> dict:
    return _generic_check("Kraken", "KRAKEN_API_KEY", "modules.integrations.kraken", "balance")


def check_whoop() -> dict:
    return _generic_check("Whoop", "WHOOP_REFRESH_TOKEN", "modules.integrations.whoop", "latest_recovery")


def check_youtube() -> dict:
    if not os.getenv("YOUTUBE_API_KEY"):
        return {"name": "YouTube", "status": "not_configured"}
    return {"name": "YouTube", "status": "ok", "detail": "Key present"}


def _generic_check(name: str, env_var: str, module: str, func: str) -> dict:
    if not os.getenv(env_var):
        return {"name": name, "status": "not_configured"}
    try:
        m = __import__(module, fromlist=[func])
        getattr(m, func)()
        return {"name": name, "status": "ok"}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "status": "error", "detail": str(e)[:200]}


def run_all() -> list[dict]:
    return [
        check_outlook(),
        check_github(),
        check_alpha_vantage(),
        check_kraken(),
        check_whoop(),
        check_youtube(),
    ]
