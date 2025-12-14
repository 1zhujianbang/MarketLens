from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.web.config import DATA_DIR
from src.web.framework.user_context import DEFAULT_PROJECT_ID


def _proj_dir(project_id: str) -> Path:
    pid = (project_id or DEFAULT_PROJECT_ID).strip() or DEFAULT_PROJECT_ID
    return DATA_DIR / "projects" / pid


def runs_dir(project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return _proj_dir(project_id) / "runs"


def evidence_dir(project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return _proj_dir(project_id) / "evidence"


def cache_dir(project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return _proj_dir(project_id) / "cache"


@dataclass
class RunChangePack:
    run_id: str
    created_at: str
    pipeline_name: str
    status: str  # running/success/failed
    error: Optional[str]
    new_entities: List[str]
    new_events: List[str]
    duplicate_events: List[str]
    evidence_events: List[Dict[str, Any]]
    pipeline_def: Optional[Dict[str, Any]] = None
    completed_steps: Optional[int] = None
    total_steps: Optional[int] = None


def ensure_dirs(project_id: str = DEFAULT_PROJECT_ID) -> None:
    runs_dir(project_id).mkdir(parents=True, exist_ok=True)
    evidence_dir(project_id).mkdir(parents=True, exist_ok=True)
    (cache_dir(project_id) / "pyvis").mkdir(parents=True, exist_ok=True)


def list_runs(project_id: str = DEFAULT_PROJECT_ID, limit: int = 50) -> List[Path]:
    # backward compat: also show old data/runs if exists and project_id=default
    files: List[Path] = []
    rd = runs_dir(project_id)
    if rd.exists():
        files.extend(list(rd.glob("run_*.json")))
    if project_id == DEFAULT_PROJECT_ID:
        legacy = DATA_DIR / "runs"
        if legacy.exists():
            files.extend(list(legacy.glob("run_*.json")))
    files = sorted(set(files), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def save_run_report(project_id: str, run_id: str, report_md: str) -> Path:
    ensure_dirs(project_id)
    p = runs_dir(project_id) / f"run_{run_id}.md"
    p.write_text(report_md or "", encoding="utf-8")
    return p


def save_run_change_pack(project_id: str, pack: RunChangePack) -> Path:
    ensure_dirs(project_id)
    p = runs_dir(project_id) / f"run_{pack.run_id}.json"
    p.write_text(json.dumps(pack.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_run_change_pack(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_run_context_snapshot(project_id: str, run_id: str, snapshot: Dict[str, Any]) -> Path:
    """Persist a context snapshot for possible resume/debug.

    This is best-effort: keep it JSON-serializable and avoid huge payloads.
    """
    ensure_dirs(project_id)
    p = runs_dir(project_id) / f"run_{run_id}_context.json"
    try:
        p.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # fallback: try stringifying
        p.write_text(json.dumps({"_non_serializable": str(snapshot)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_run_context_snapshot(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_evidence_note(
    project_id: str, run_id: str, kind: str, key: str, note: str, meta: Optional[Dict[str, Any]] = None
) -> Path:
    """Save a lightweight evidence note (placeholder for future content persistence).

    This avoids storing full raw content by default; only pinned notes are persisted.
    """
    ensure_dirs(project_id)
    safe_key = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in key])[:120]
    p = evidence_dir(project_id) / f"{run_id}_{kind}_{safe_key}.json"
    obj = {
        "run_id": run_id,
        "kind": kind,
        "key": key,
        "note": note,
        "meta": meta or {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def save_evidence_content_snippet(
    project_id: str,
    *,
    run_id: str,
    news_id: str,
    url: str,
    title: str,
    published_at: str,
    source: Dict[str, Any],
    content_snippet: str,
    content_hash: str,
) -> Path:
    """Persist pinned content snippet with de-dup by (news_id, content_hash)."""
    ensure_dirs(project_id)
    safe_news = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in str(news_id)])[:64]
    safe_hash = "".join([c if c.isalnum() else "_" for c in str(content_hash)])[:64]
    p = evidence_dir(project_id) / f"{run_id}_news_{safe_news}_{safe_hash}.json"
    obj = {
        "run_id": run_id,
        "news_id": news_id,
        "url": url,
        "title": title,
        "published_at": published_at,
        "source": source,
        "content_snippet": content_snippet,
        "content_hash": content_hash,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if not p.exists():
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


