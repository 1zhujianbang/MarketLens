from __future__ import annotations

from datetime import datetime
from typing import Optional

import streamlit as st

from src.web.services.pipeline_runner import GlobalPipelineRunner
from src.web.services.run_store import RunChangePack, save_run_change_pack, save_run_report, save_run_context_snapshot
from src.web.framework.user_context import get_user_context
from src.web.services.news_lookup import find_news_by_id
from src.web import utils


def render_task_monitor(runner: GlobalPipelineRunner) -> None:
    """Render the global task monitor and sync completion to session_state (UI thread)."""
    if not (runner.is_running or runner.status_info.get("state") != "idle"):
        return

    with st.container(border=True):
        col_status, col_ctrl = st.columns([4, 1])

        with col_status:
            state = runner.status_info.get("state", "running")
            label = runner.status_info.get("label", "Running...")
            expanded = runner.status_info.get("expanded", True)
            status_container = st.status(label, expanded=expanded, state=state)

            with status_container:
                st.write("Recent Logs:")
                with runner._lock:
                    recent_logs = runner.logs[-10:]
                st.code("\n".join(recent_logs) if recent_logs else "Initializing...", language="text")

        with col_ctrl:
            if runner.is_running:
                st.caption("Running in background...")
                if st.button("🔄 Refresh View", key="pipeline_refresh_view_monitor", use_container_width=True):
                    st.rerun()
                st.caption("提示：Streamlit 会在每次交互时 rerun。为避免阻塞与高 CPU，这里改为手动刷新。")
            else:
                if st.button("Clear Status", key="pipeline_clear_status_monitor"):
                    runner.status_info["state"] = "idle"
                    st.rerun()

    # Sync completion and render report
    consumed = runner.consume_completion()
    if consumed is not None:
        history_idx, result = consumed
        if history_idx is not None and "pipeline_history" in st.session_state:
            if 0 <= history_idx < len(st.session_state.pipeline_history):
                st.session_state.pipeline_history[history_idx]["status"] = result.status
                run_id = st.session_state.pipeline_history[history_idx].get("run_id") or ""
                pipeline_name = st.session_state.pipeline_history[history_idx].get("name") or "Unknown Pipeline"
                pipeline_def = st.session_state.pipeline_history[history_idx].get("pipeline_def")
                completed_steps = runner.current_step_idx
                total_steps = runner.total_steps
                project_id = get_user_context().project_id

                # Compute diff (new entities/events) for this run and persist as a change pack.
                # NOTE: This is a lightweight "审查包" used by Data Inspector (runs tab).
                try:
                    st.cache_data.clear()  # ensure we see latest files
                except Exception:
                    pass

                before = st.session_state.pop("_run_baseline", None) or {}
                before_entities = set(before.get("entities") or [])
                before_events = set(before.get("events") or [])

                after_entities = set((utils.load_entities() or {}).keys())
                after_events = set((utils.load_events() or {}).keys())

                new_entities = sorted(list(after_entities - before_entities))
                new_events = sorted(list(after_events - before_events))
                # detect duplicates (extracted abstracts already exist)
                duplicate_events: list[str] = []
                evidence_events: list[dict] = []

                extracted = runner.last_outputs.get("extracted_events")
                if isinstance(extracted, list):
                    for e in extracted:
                        if not isinstance(e, dict):
                            continue
                        abstract = str(e.get("abstract") or "")
                        if abstract and abstract in before_events:
                            duplicate_events.append(abstract)
                        if abstract and abstract in new_events:
                            news_id = str(e.get("news_id") or "")
                            src = e.get("source") if isinstance(e.get("source"), dict) else {}
                            published_at = str(e.get("published_at") or "")
                            # enrich with raw news lookup (best-effort)
                            url = ""
                            title = ""
                            if news_id:
                                it = find_news_by_id(news_id)
                                if it:
                                    url = it.url
                                    title = it.title
                            evidence_events.append(
                                {
                                    "abstract": abstract,
                                    "news_id": news_id,
                                    "published_at": published_at,
                                    "source": src,
                                    "url": url,
                                    "title": title,
                                }
                            )
                duplicate_events = sorted(list(set(duplicate_events)))

                if run_id:
                    pack = RunChangePack(
                        run_id=run_id,
                        created_at=datetime.now().isoformat(timespec="seconds"),
                        pipeline_name=pipeline_name,
                        status=result.status,
                        error=result.error,
                        new_entities=new_entities,
                        new_events=new_events,
                        duplicate_events=duplicate_events,
                        evidence_events=evidence_events,
                        pipeline_def=pipeline_def if isinstance(pipeline_def, dict) else None,
                        completed_steps=int(completed_steps) if completed_steps is not None else None,
                        total_steps=int(total_steps) if total_steps is not None else None,
                    )
                    save_run_change_pack(project_id, pack)
                    # persist context snapshot for resume/debug (best-effort; can be large)
                    try:
                        snap = runner.last_context_snapshot if isinstance(runner.last_context_snapshot, dict) else {}
                        save_run_context_snapshot(project_id, run_id, snap)
                    except Exception:
                        pass
                    if result.report_md:
                        save_run_report(project_id, run_id, result.report_md)

    if (not runner.is_running) and runner.final_report:
        with st.expander("📄 Final Report Result", expanded=True):
            st.markdown(runner.final_report)
            st.download_button(
                "Download Report",
                runner.final_report,
                file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            )


