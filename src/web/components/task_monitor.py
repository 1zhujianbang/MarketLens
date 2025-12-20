from __future__ import annotations

from datetime import datetime
from typing import Optional

import streamlit as st

from src.web.services.pipeline_runner import GlobalPipelineRunner
from src.web.services.run_store import (
    RunChangePack,
    load_run_step_records,
    save_run_change_pack,
    save_run_report,
    save_run_context_snapshot,
)
from src.web.framework.user_context import get_user_context
from src.web.services.news_lookup import find_news_by_id
from src.web import utils


def render_task_monitor(runner: GlobalPipelineRunner) -> None:
    """Render the pipeline execution console and sync completion to session_state (UI thread)."""

    def _is_important(line: str) -> bool:
        if not isinstance(line, str):
            return False
        up = line.upper()
        # 关键日志：错误/警告/失败/显著状态变化
        return (
            "[ERROR]" in up
            or "[WARN]" in up
            or "ERROR:" in up
            or "FAILED" in up
            or "EXCEPTION" in up
            or "Traceback" in line
            or "❌" in line
        )

    def _get_logs_snapshot() -> dict:
        with runner._lock:
            logs = list(runner.logs or [])
            status = dict(runner.status_info or {})
            current_step_idx = int(getattr(runner, "current_step_idx", 0) or 0)
            total_steps = int(getattr(runner, "total_steps", 0) or 0)
            last_def = dict(runner.last_pipeline_def or {}) if isinstance(runner.last_pipeline_def, dict) else None
            last_outputs = dict(runner.last_outputs or {}) if isinstance(runner.last_outputs, dict) else {}
            last_context = dict(runner.last_context_snapshot or {}) if isinstance(runner.last_context_snapshot, dict) else {}
            last_error = str(getattr(runner, "last_error", "") or "")
            final_report = str(getattr(runner, "final_report", "") or "")
        important = [x for x in logs if _is_important(x)]
        return {
            "logs": logs,
            "important": important,
            "status": status,
            "current_step_idx": current_step_idx,
            "total_steps": total_steps,
            "pipeline_def": last_def,
            "last_outputs": last_outputs,
            "last_context": last_context,
            "last_error": last_error,
            "final_report": final_report,
        }

    # 即使 idle，也允许查看最近一次运行的控制台（只要有日志/历史def）
    snap = _get_logs_snapshot()
    has_any = bool(snap["logs"]) or bool(snap["pipeline_def"]) or runner.is_running or (snap["status"].get("state") != "idle")
    if not has_any:
        return

    with st.container(border=True):
        # 顶部：运行状态条（保持与旧版兼容）
        state = snap["status"].get("state", "running")
        label = snap["status"].get("label", "Running...")
        expanded = snap["status"].get("expanded", True)
        
        # Streamlit st.status() 只接受 'running', 'complete', 'error'
        # 将其他状态映射为合法状态
        state_map = {
            "idle": "complete",
            "success": "complete",
            "completed": "complete",
            "failed": "error",
            "cancelled": "error",
        }
        mapped_state = state_map.get(state, state)
        if mapped_state not in ("running", "complete", "error"):
            mapped_state = "running"  # 默认回退
        
        st.status(label, expanded=expanded, state=mapped_state)

        col_left, col_right = st.columns([3, 7], gap="large")

        # ----------------
        # 左侧：流程/步骤导航
        # ----------------
        with col_left:
            st.subheader("流程")

            # 运行控制
            ctrl_a, ctrl_b = st.columns([1, 1])
            with ctrl_a:
                if st.button("刷新视图", key="pipeline_refresh_view_console", use_container_width=True):
                    st.rerun()
            with ctrl_b:
                if (not runner.is_running) and st.button("清空状态", key="pipeline_clear_status_console", use_container_width=True):
                    runner.status_info["state"] = "idle"
                    st.rerun()

            if runner.is_running:
                st.caption("后台运行中；建议手动刷新查看最新日志。")

            # 步骤列表
            pipeline_def = snap["pipeline_def"]
            steps = (pipeline_def or {}).get("steps", []) if isinstance(pipeline_def, dict) else []
            step_ids = []
            for i, s in enumerate(steps):
                sid = ""
                if isinstance(s, dict):
                    sid = str(s.get("id") or s.get("tool") or f"step_{i+1}")
                else:
                    sid = f"step_{i+1}"
                step_ids.append(f"{i+1:02d}. {sid}")

            cur = snap["current_step_idx"]
            tot = snap["total_steps"] or (len(step_ids) if step_ids else 0)
            if tot > 0:
                st.progress(min(1.0, max(0.0, cur / float(tot))))
                st.caption(f"进度：{cur}/{tot}")

            # 支持从“菜单”跳转：历史运行选择 + 步骤选择
            hist_opts = ["(当前/最近一次)"]
            if "pipeline_history" in st.session_state and st.session_state.pipeline_history:
                # 最近 20 次（避免过长）
                for h in reversed(st.session_state.pipeline_history[-20:]):
                    rid = h.get("run_id") or ""
                    name = h.get("name") or "Pipeline"
                    status = h.get("status") or ""
                    hist_opts.append(f"{rid} | {name} | {status}")

            selected_hist = st.selectbox("跳转到某次运行", options=hist_opts, index=0, key="pipeline_console_select_history")
            if selected_hist != "(当前/最近一次)":
                try:
                    rid = selected_hist.split("|", 1)[0].strip()
                    # 找到对应记录并展示其 pipeline_def（只影响展示，不会打断当前运行）
                    for h in reversed(st.session_state.pipeline_history[-200:]):
                        if (h.get("run_id") or "") == rid:
                            pipeline_def = h.get("pipeline_def") if isinstance(h.get("pipeline_def"), dict) else pipeline_def
                            steps = (pipeline_def or {}).get("steps", []) if isinstance(pipeline_def, dict) else steps
                            break
                except Exception:
                    pass

            if step_ids:
                default_idx = max(0, min(len(step_ids) - 1, (cur - 1) if cur > 0 else 0))
                selected_step = st.selectbox("跳转到步骤", options=step_ids, index=default_idx, key="pipeline_console_select_step")
                try:
                    sel_i = int(selected_step.split(".", 1)[0]) - 1
                except Exception:
                    sel_i = None

                if sel_i is not None and 0 <= sel_i < len(steps):
                    with st.expander("步骤详情", expanded=False):
                        st.json(steps[sel_i] if isinstance(steps[sel_i], dict) else {"raw": str(steps[sel_i])})

                        out_key = ""
                        if isinstance(steps[sel_i], dict):
                            out_key = str(steps[sel_i].get("output") or "").strip()
                        if out_key:
                            st.caption(f"输出键：{out_key}")
                            if out_key in snap["last_context"]:
                                st.write("上下文快照（最近一次）中的输出：")
                                st.json(snap["last_context"].get(out_key))

                # 若选择了历史运行，尝试加载该 run 的 step 记录（JSONL）并展示选中 step 的执行信息
                rid = ""
                if selected_hist != "(当前/最近一次)":
                    try:
                        rid = selected_hist.split("|", 1)[0].strip()
                    except Exception:
                        rid = ""
                if rid:
                    try:
                        project_id = get_user_context().project_id
                        recs = load_run_step_records(project_id, rid, limit=5000)
                        # 按 step_idx 聚合：取最后一条（running -> success/failed）
                        by_idx = {}
                        for r in recs:
                            if isinstance(r, dict) and ("step_idx" in r):
                                by_idx[int(r.get("step_idx") or 0)] = r
                        rec = by_idx.get(int(sel_i))
                        if rec:
                            with st.expander("运行记录（落盘）", expanded=False):
                                st.json(rec)
                        else:
                            st.caption("未找到该步骤的落盘记录（可能是旧运行或尚未生成）。")
                    except Exception:
                        pass

        # ----------------
        # 右侧：关键日志 + 滚动日志
        # ----------------
        with col_right:
            st.subheader("日志")

            filt = st.text_input("过滤（包含关键字）", value="", key="pipeline_console_log_filter")
            max_lines = st.slider("显示行数", 50, 2000, 300, 50, key="pipeline_console_log_max_lines")

            # 上：关键日志
            with st.container(border=True):
                st.markdown("**关键日志（错误/警告/失败）**")
                imp = snap["important"][-200:]
                if filt:
                    imp = [x for x in imp if filt in x]
                st.code("\n".join(imp) if imp else "暂无关键日志。", language="text")
                if snap["last_error"]:
                    st.caption("最近错误：")
                    st.code(snap["last_error"], language="text")

            # 下：滚动日志
            with st.container(border=True):
                st.markdown("**滚动日志（实时）**")
                logs = snap["logs"][-int(max_lines) :]
                if filt:
                    logs = [x for x in logs if filt in x]
                st.code("\n".join(logs) if logs else "暂无日志。", language="text")
                st.caption("提示：为避免阻塞与高 CPU，此处采用手动刷新。")

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


