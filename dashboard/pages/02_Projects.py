"""Projects — list from Project_Index.md; expand to show README + next step."""
import streamlit as st

from core import vault, markdown
from core.config import SYSTEM_PATH, PROJECTS_PATH

PROJECT_INDEX_PATH = SYSTEM_PATH / "Project_Index.md"

st.set_page_config(page_title="Projects", layout="wide")
st.title("Projects")


def status_span(label: str, color: str) -> str:
    """Return an HTML span rendering a colored status label."""
    return (
        f'<span style="color:{color}; font-size:0.78rem; font-weight:600; '
        f'letter-spacing:0.05em;">{label}</span>'
    )


md = vault.read_md(PROJECT_INDEX_PATH)
if not md:
    st.error(f"Could not read {PROJECT_INDEX_PATH.name}: file is empty or missing")
    st.stop()

projects = markdown.parse_projects(md)
if not projects:
    st.info("No projects found in Project_Index.md.")
    st.stop()

for proj in projects:
    display_name = proj["name"].replace("_", " ")
    with st.container(border=True):
        st.markdown(f"### {proj['id']}  {display_name}")
        label, color = markdown.status_display(proj)
        st.markdown(status_span(label, color), unsafe_allow_html=True)
        if proj["status_text"]:
            st.write(proj["status_text"])
        if proj["next_step"]:
            st.markdown(f"**Next step:** {proj['next_step']}")

        with st.expander("Open README"):
            readme_path = PROJECTS_PATH / proj["folder"] / "README.md"
            content = vault.read_md(readme_path)
            if content:
                st.markdown(content)
            else:
                st.error(f"Could not read {readme_path.name}: not found at {readme_path}")
