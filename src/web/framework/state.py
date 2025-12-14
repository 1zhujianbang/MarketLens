from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st


def ensure_defaults(defaults: Dict[str, Any]) -> None:
    """Ensure session_state has default values for keys."""
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_list(key: str) -> List[Any]:
    v = st.session_state.get(key)
    return v if isinstance(v, list) else []


