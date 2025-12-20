from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, Optional

import streamlit as st

from src.app.pipeline.context import PipelineContext
from src.app.pipeline.engine import PipelineEngine
from src.web.services.run_store import append_run_step_record, save_run_step_context_snapshot
from src.app.pipeline.models import PipelineRunState


@dataclass
class PipelineRunResult:
    status: str  # "running" | "success" | "failed"
    report_md: Optional[str] = None
    error: Optional[str] = None


class GlobalPipelineRunner:
    """Thread-safe pipeline runner for Streamlit.

    Background thread MUST NOT read/write st.session_state.
    UI thread can pull runner status + logs and update session_state.
    """

    def __init__(self):
        self.is_running = False
        self.logs: list[str] = []
        self.status_info = {"label": "Idle", "state": "idle", "expanded": False}
        self.current_step_idx = 0
        self.total_steps = 0

        self.history_idx: Optional[int] = None
        self.completed_status: Optional[str] = None  # "success" | "failed" | None
        self.final_report: Optional[str] = None
        self.last_error: Optional[str] = None

        self._lock = threading.Lock()
        self.last_pipeline_def: Optional[Dict[str, Any]] = None
        self.last_outputs: Dict[str, Any] = {}
        self.last_context_snapshot: Dict[str, Any] = {}

    def start(
        self,
        pipeline_def: Dict[str, Any],
        *,
        history_idx: Optional[int],
        start_at: int = 0,
        initial_data: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> bool:
        if self.is_running:
            return False

        with self._lock:
            self.is_running = True
            self.logs = []
            self.status_info = {"label": "Starting...", "state": "running", "expanded": True}
            self.final_report = None
            self.last_error = None
            self.history_idx = history_idx
            self.completed_status = None
            self.current_step_idx = 0
            steps = pipeline_def.get("steps", [])
            self.total_steps = len(steps)
            self.last_pipeline_def = pipeline_def
            self.last_outputs = {}
            self.last_context_snapshot = initial_data.copy() if isinstance(initial_data, dict) else {}
            self._start_at = max(0, int(start_at))
            self._initial_data = initial_data.copy() if isinstance(initial_data, dict) else None
            self._run_id = str(run_id or "")
            self._project_id = str(project_id or "")

        def _worker():
            asyncio.run(self._run_async(pipeline_def))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return True

    async def _run_async(self, pipeline_def: Dict[str, Any]) -> None:
        def log_callback(entry: Dict[str, Any]) -> None:
            with self._lock:
                ts = entry.get("timestamp", "").split("T")[1][:8] if entry.get("timestamp") else ""
                msg = f"[{ts}] [{entry.get('level','INFO')}] {entry.get('message','')}"
                self.logs.append(msg)
                if len(self.logs) > 1000:
                    self.logs.pop(0)

        steps = pipeline_def.get("steps", [])
        init = self._initial_data if isinstance(getattr(self, "_initial_data", None), dict) else None
        context = PipelineContext(initial_data=init, log_callback=log_callback)
        project_id = str(getattr(self, "_project_id", "") or "")
        if not project_id:
            project_id = "default"
        run_id = str(getattr(self, "_run_id", "") or "")
        if not run_id:
            # fallback（不应发生：run_id 通常来自 append_history）
            run_id = uuid4().hex[:12]
        run_state = PipelineRunState(
            run_id=run_id,
            project_id=project_id,
            pipeline_name=str(pipeline_def.get("name") or "Pipeline"),
            total_steps=len(steps or []),
        )

        def on_step_start(run_state, step_state, ctx):
            try:
                append_run_step_record(
                    project_id,
                    run_id,
                    {
                        "step_idx": step_state.step_idx,
                        "step_id": step_state.step_id,
                        "tool": step_state.tool,
                        "output_key": step_state.output_key,
                        "status": step_state.status,
                        "started_at": step_state.started_at,
                        "ended_at": step_state.ended_at,
                        "duration_ms": step_state.duration_ms,
                        "inputs_resolved": step_state.inputs_resolved,
                        "error": step_state.error,
                    },
                )
            except Exception:
                pass

        def on_step_end(run_state, step_state, ctx):
            try:
                append_run_step_record(
                    project_id,
                    run_id,
                    {
                        "step_idx": step_state.step_idx,
                        "step_id": step_state.step_id,
                        "tool": step_state.tool,
                        "output_key": step_state.output_key,
                        "status": step_state.status,
                        "started_at": step_state.started_at,
                        "ended_at": step_state.ended_at,
                        "duration_ms": step_state.duration_ms,
                        "inputs_resolved": step_state.inputs_resolved,
                        "error": step_state.error,
                    },
                )
                # per-step context snapshot（best-effort）
                save_run_step_context_snapshot(project_id, run_id, step_state.step_idx, ctx.get_all())
            except Exception:
                pass

        engine = PipelineEngine(context, on_step_start=on_step_start, on_step_end=on_step_end)

        try:
            start_at = max(0, int(getattr(self, "_start_at", 0)))
            for i, step in enumerate(steps):
                if i < start_at:
                    continue
                step_id = step.get("id")
                with self._lock:
                    self.current_step_idx = i + 1
                    self.status_info = {
                        "label": f"Executing Step {self.current_step_idx}/{self.total_steps}: **{step_id}**",
                        "state": "running",
                        "expanded": True,
                    }

                # 让 engine 执行单步（可被 hooks 记录）
                await engine.run_step(
                    run_state=run_state,
                    step_idx=i,
                    step=step,
                )

                # capture outputs + context snapshot for UI
                try:
                    out_key = step.get("output")
                    if out_key:
                        out_val = context.get(out_key)
                        with self._lock:
                            self.last_outputs[out_key] = out_val
                    snap = context.get_all()
                    with self._lock:
                        self.last_context_snapshot = snap
                except Exception:
                    pass

            with self._lock:
                self.status_info = {"label": "✅ Pipeline Execution Completed!", "state": "complete", "expanded": False}
                self.final_report = context.get("final_report_md")
                self.completed_status = "success"
        except Exception as e:  # noqa: BLE001
            with self._lock:
                self.status_info = {"label": f"❌ Execution Failed: {str(e)}", "state": "error", "expanded": True}
                self.logs.append(f"[System] Error: {str(e)}")
                self.completed_status = "failed"
                self.last_error = str(e)
        finally:
            with self._lock:
                self.is_running = False

    def consume_completion(self) -> Optional[tuple[Optional[int], PipelineRunResult]]:
        """Consume completion signal once (UI thread)."""
        with self._lock:
            if not self.completed_status:
                return None
            idx = self.history_idx
            status = self.completed_status
            report = self.final_report
            err = self.last_error

            # consume
            self.completed_status = None
            self.history_idx = None

        return idx, PipelineRunResult(status=status, report_md=report, error=err)


def get_pipeline_runner() -> GlobalPipelineRunner:
    """Session-scoped runner (preferred for Streamlit multi-user deployments)."""
    if "_pipeline_runner" not in st.session_state:
        st.session_state["_pipeline_runner"] = GlobalPipelineRunner()
    return st.session_state["_pipeline_runner"]


# Backward-compatible alias (kept for older imports)
def get_global_pipeline_runner() -> GlobalPipelineRunner:
    return get_pipeline_runner()


def append_history(pipeline_def: Dict[str, Any]) -> int:
    """Append a pipeline history record (UI thread) and return its index."""
    if "pipeline_history" not in st.session_state:
        st.session_state.pipeline_history = []

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    st.session_state.pipeline_history.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_id": run_id,
            "name": pipeline_def.get("name", "Unknown Pipeline"),
            "steps": len(pipeline_def.get("steps", [])),
            "status": "running",
            "pipeline_def": pipeline_def,
        }
    )
    return len(st.session_state.pipeline_history) - 1


