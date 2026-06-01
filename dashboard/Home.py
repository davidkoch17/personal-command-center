"""Command Center — navigation router / entry script (Streamlit MPA v2).

This module is the entry point (``streamlit run dashboard/Home.py``). It owns the
single ``st.set_page_config`` call and the explicit ``st.navigation`` config that
defines the locked sidebar order. Page *content* lives in the page modules; the
home/Mission-Control view is ``_home_view.py`` (registered as the default page).

Deep-dive pattern (Phase 9): visible pages are overviews shown in the current
tab. Each renders an "Open Workspace ↗" link (see :mod:`dashboard._workspace_link`)
that opens a *hidden* workspace page in a new browser tab. Hidden pages are
registered here with ``visibility="hidden"`` so they are URL-routable (by their
``url_path``) but never appear in the sidebar.
"""
import streamlit as st

st.set_page_config(
    page_title="Command Center",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Default landing page (root URL). Its file sits at the dashboard root, not in
# pages/, so it is never picked up as an automatic sidebar entry.
home = st.Page("_home_view.py", title="Home", default=True)

# Visible sidebar pages, grouped. Order is LOCKED (Phase 9a spec). Money sits at
# overall position 7 (Home, Tasks, Projects, Ideas, Inbox, Portfolio, Money).
visible_pages = {
    "Main": [
        home,
        st.Page("pages/02_Tasks.py", title="Tasks"),
        st.Page("pages/03_Projects.py", title="Projects"),
        st.Page("pages/04_Ideas.py", title="Ideas"),
        st.Page("pages/05_Inbox.py", title="Inbox"),
    ],
    "Finance": [
        st.Page("pages/06_Portfolio.py", title="Portfolio"),
        st.Page("pages/07_Money.py", title="Money"),
        st.Page("pages/08_Watchlist.py", title="Watchlist"),
    ],
    "Life": [
        st.Page("pages/10_Career.py", title="Career"),
        st.Page("pages/11_Brand.py", title="Brand"),
    ],
    "System": [
        st.Page("pages/14_Reading.py", title="Reading"),
        st.Page("pages/17_Settings.py", title="Settings"),
        st.Page("pages/18_Calendar.py", title="Calendar"),
        st.Page("pages/19_Background_Runs.py", title="Background Runs"),
    ],
}

# Deprecated sidebar pages (Phase 10a). Files + modules are kept and remain
# URL-routable, but they are hidden from the sidebar. Their functionality is
# surfaced contextually instead: Search → Home search bar; Skills / Agents →
# Home "Quick Run" panel + the per-ticker / per-holding workspaces; Health /
# Journal are edited directly in the vault.
deprecated_pages = [
    st.Page("pages/09_Health.py", title="Health",
            url_path="health", visibility="hidden"),
    st.Page("pages/12_Search.py", title="Search",
            url_path="search", visibility="hidden"),
    st.Page("pages/13_Journal.py", title="Journal",
            url_path="journal", visibility="hidden"),
    st.Page("pages/15_Agents.py", title="Agents",
            url_path="agents", visibility="hidden"),
    st.Page("pages/16_Skills.py", title="Skills",
            url_path="skills", visibility="hidden"),
]

# Hidden workspace pages — URL-accessible only (opened in a new tab from the
# matching overview). ``visibility="hidden"`` keeps them out of the sidebar.
hidden_pages = [
    st.Page("pages/_workspace_project.py", title="Project Workspace",
            url_path="workspace_project", visibility="hidden"),
    st.Page("pages/_workspace_idea.py", title="Idea Workspace",
            url_path="workspace_idea", visibility="hidden"),
    # Phase 9b deep-dive workspaces (placeholders for now).
    st.Page("pages/_workspace_portfolio.py", title="Portfolio Workspace",
            url_path="workspace_portfolio", visibility="hidden"),
    st.Page("pages/_workspace_money.py", title="Money Workspace",
            url_path="workspace_money", visibility="hidden"),
    st.Page("pages/_workspace_brand.py", title="Brand Workspace",
            url_path="workspace_brand", visibility="hidden"),
    st.Page("pages/_workspace_brand_video.py", title="Brand Video Workspace",
            url_path="workspace_brand_video", visibility="hidden"),
    st.Page("pages/_workspace_career.py", title="Career Workspace",
            url_path="workspace_career", visibility="hidden"),
    st.Page("pages/_workspace_watchlist.py", title="Watchlist Workspace",
            url_path="workspace_watchlist", visibility="hidden"),
]

# Register hidden + deprecated pages alongside the visible ones so they route;
# because they are hidden they add no sidebar entry (no empty section header
# appears).
nav_config = dict(visible_pages)
nav_config["System"] = nav_config["System"] + deprecated_pages + hidden_pages

nav = st.navigation(nav_config, position="sidebar")
nav.run()
