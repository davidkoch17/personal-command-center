"""Calendar — Outlook events via published iCal URL (Phase 6)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

import streamlit as st

from modules.integrations import calendar_ical

st.set_page_config(page_title="Calendar", layout="wide")
st.title("Calendar")


def _as_date(value) -> date | None:
    """Coerce an event start (date or datetime) to a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _fmt_when(value) -> str:
    """Human label for an event start."""
    if isinstance(value, datetime):
        return value.strftime("%a %Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%a %Y-%m-%d (all day)")
    return str(value)


if not calendar_ical.is_configured():
    st.info("Calendar not configured. Add `OUTLOOK_ICAL_URL` to `.env` (see README → Calendar setup).")
    st.stop()

events = calendar_ical.fetch_events(days_ahead=30)
if not events:
    st.warning("No upcoming events found (or the iCal URL could not be read).")
    st.stop()

# 1. Next 5 events ------------------------------------------------------------
st.subheader("Next 5 events")
for ev in events[:5]:
    line = f"**{ev['title'] or '(untitled)'}** — {_fmt_when(ev['start'])}"
    if ev.get("location"):
        line += f"  ·  📍 {ev['location']}"
    st.markdown(line)

st.divider()

# 2. This week (grouped by day) ----------------------------------------------
st.subheader("This week")
today = date.today()
week_end = today + timedelta(days=7)
by_day: dict[date, list[dict]] = defaultdict(list)
for ev in events:
    d = _as_date(ev["start"])
    if d and today <= d <= week_end:
        by_day[d].append(ev)

if not by_day:
    st.caption("Nothing scheduled in the next 7 days.")
else:
    for day in sorted(by_day):
        st.markdown(f"**{day.strftime('%A %Y-%m-%d')}**")
        for ev in by_day[day]:
            when = ev["start"].strftime("%H:%M") if isinstance(ev["start"], datetime) else "all day"
            st.caption(f"{when} — {ev['title']}" + (f" · {ev['location']}" if ev.get("location") else ""))

st.divider()

# 3. Next 30 days (grouped by day) -------------------------------------------
st.subheader("Next 30 days")
month_by_day: dict[date, list[dict]] = defaultdict(list)
for ev in events:
    d = _as_date(ev["start"])
    if d:
        month_by_day[d].append(ev)

for day in sorted(month_by_day):
    with st.expander(f"{day.strftime('%A %Y-%m-%d')} — {len(month_by_day[day])} event(s)"):
        for ev in month_by_day[day]:
            st.markdown(f"- **{ev['title']}** — {_fmt_when(ev['start'])}"
                        + (f" · 📍 {ev['location']}" if ev.get("location") else ""))
            if ev.get("description"):
                st.caption(ev["description"])
