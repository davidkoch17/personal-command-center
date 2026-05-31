"""GitHub recent commits across the user's repos.

Returns an empty list when ``GITHUB_PAT`` / ``GITHUB_USERNAME`` are missing or
any request fails.
"""
from __future__ import annotations

import os

from core.config import get_logger

logger = get_logger(__name__)


def is_configured() -> bool:
    """True when both the PAT and username are present."""
    return bool(os.getenv("GITHUB_PAT") and os.getenv("GITHUB_USERNAME"))


def recent_commits(limit: int = 10) -> list[dict]:
    """Return recent commits across the user's most recently pushed repos."""
    pat = os.getenv("GITHUB_PAT")
    user = os.getenv("GITHUB_USERNAME")
    if not (pat and user):
        return []
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
        }
        r = httpx.get(
            f"https://api.github.com/users/{user}/repos?per_page=30&sort=pushed",
            headers=headers,
            timeout=15,
        )
        repos = r.json()
        if not isinstance(repos, list):
            return []
        out: list[dict] = []
        for repo in repos[:10]:
            r2 = httpx.get(
                f"https://api.github.com/repos/{repo['full_name']}/commits?per_page=5",
                headers=headers,
                timeout=15,
            )
            commits = r2.json()
            if not isinstance(commits, list):
                continue
            for c in commits:
                try:
                    out.append(
                        {
                            "repo": repo["name"],
                            "sha": c["sha"][:7],
                            "message": c["commit"]["message"].split("\n")[0],
                            "date": c["commit"]["author"]["date"],
                            "url": c["html_url"],
                        }
                    )
                except (KeyError, TypeError):
                    continue
        out.sort(key=lambda x: x["date"], reverse=True)
        return out[:limit]
    except Exception as e:  # noqa: BLE001
        logger.warning("github recent_commits failed: %s", e)
        return []
