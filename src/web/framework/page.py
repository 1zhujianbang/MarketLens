from __future__ import annotations

from dataclasses import dataclass
import streamlit as st


@dataclass(frozen=True)
class PageSpec:
    title: str
    icon: str
    layout: str = "wide"
    sidebar_state: str = "expanded"


def init_page(spec: PageSpec, *, apply_style: bool = False, show_sidebar_header: bool = False) -> None:
    """Initialize a Streamlit page in a consistent way.

    NOTE: This must be called before any other Streamlit command on a page.
    """
    st.set_page_config(
        page_title=spec.title,
        page_icon=spec.icon,
        layout=spec.layout,
        initial_sidebar_state=spec.sidebar_state,
    )

    if apply_style:
        # Optional: only enable when you really want a custom theme.
        # Streamlit already provides consistent default styling across the app.
        from src.web.styles import load_openai_style

        load_openai_style()

    if show_sidebar_header:
        # Optional: keep default sidebar navigation style unless explicitly enabled.
        from src.web.styles import render_sidebar_header

        render_sidebar_header()


__all__ = ["PageSpec", "init_page"]
