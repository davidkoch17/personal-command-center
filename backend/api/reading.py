"""Reading API — the reading list (to_read / reading_now / done)."""
from __future__ import annotations

from fastapi import APIRouter

from core import vault, markdown
from core.config import READING_LIST_PATH

router = APIRouter()


@router.get("")
def reading_list() -> dict:
    """Parse Reading_List.md into to_read / reading_now / done buckets."""
    buckets = markdown.parse_reading_list(vault.read_md(READING_LIST_PATH))
    return buckets
