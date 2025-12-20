from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class UserContext:
    project_id: str
    role: str  # "viewer" | "editor" | "admin"


DEFAULT_PROJECT_ID = "default"
DEFAULT_ROLE = "admin"  # local-first default


def ensure_user_context() -> None:
    if "project_id" not in st.session_state:
        st.session_state.project_id = DEFAULT_PROJECT_ID
    if "role" not in st.session_state:
        st.session_state.role = DEFAULT_ROLE


def get_user_context() -> UserContext:
    ensure_user_context()
    pid = str(st.session_state.get("project_id") or DEFAULT_PROJECT_ID).strip() or DEFAULT_PROJECT_ID
    role = str(st.session_state.get("role") or DEFAULT_ROLE).strip() or DEFAULT_ROLE
    if role not in ("viewer", "editor", "admin"):
        role = DEFAULT_ROLE
    return UserContext(project_id=pid, role=role)


def can_write() -> bool:
    """Soft permission gate placeholder."""
    return get_user_context().role in ("editor", "admin")


def render_user_context_controls() -> None:
    """Minimal sidebar controls for future multi-user deployments."""
    ensure_user_context()
    # with st.sidebar:
    #     with st.expander("🧩 工作空间 / 权限（占位）", expanded=False):
    #         st.text_input("project_id", key="project_id", help="未来公网多人：按 project_id 隔离 runs/evidence/cache。")
    #         st.selectbox("role", options=["viewer", "editor", "admin"], key="role", index=["viewer","editor","admin"].index(st.session_state.role))


