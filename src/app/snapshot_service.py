from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..infra.paths import tools as Tools
from ..ports.kg_read_store import KGReadStore
from ..adapters.sqlite.kg_read_store import SQLiteKGReadStore


_tools = Tools()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(val: str) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _edge_time_fallback(*vals: Any) -> str:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return _utc_now_iso()


@dataclass
class SnapshotParams:
    top_entities: int = 500
    top_events: int = 500
    max_edges: int = 5000
    days_window: int = 0  # 0=all
    gap_days: int = 30  # EE_EVO 分段阈值


class SnapshotService:
    """
    五图谱快照投影服务（SQLite -> data/snapshots/*.json）
    """

    def __init__(self, *, db_path: Optional[Path] = None, out_dir: Optional[Path] = None, store: Optional[KGReadStore] = None):
        self.db_path = db_path or _tools.SQLITE_DB_FILE
        self.out_dir = out_dir or _tools.SNAPSHOTS_DIR
        self.store: KGReadStore = store or SQLiteKGReadStore(self.db_path)

    def _filter_by_days_window(self, ts: str, days_window: int) -> bool:
        if not days_window or days_window <= 0:
            return True
        dt = _parse_iso(ts)
        if not dt:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days_window))
        return dt >= cutoff

    def _load_event_map_from_rows(self, rows: List[Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
        evtid_to_abs: Dict[str, str] = {}
        abs_to_evt: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            eid = str(r.get("event_id"))
            abstract = str(r.get("abstract"))
            evtid_to_abs.setdefault(eid, abstract)
            abs_to_evt[abstract] = {
                "event_id": eid,
                "abstract": abstract,
                "event_summary": str(r.get("event_summary") or ""),
                "event_types_json": str(r.get("event_types_json") or "[]"),
                "event_start_time": str(r.get("event_start_time") or ""),
                "reported_at": str(r.get("reported_at") or ""),
                "first_seen": str(r.get("first_seen") or ""),
            }
        return evtid_to_abs, abs_to_evt

    def _load_entity_map_from_rows(self, rows: List[Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
        entid_to_name: Dict[str, str] = {}
        name_to_ent: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            eid = str(r.get("entity_id"))
            name = str(r.get("name"))
            entid_to_name[eid] = name
            name_to_ent[name] = {"entity_id": eid, "name": name, "first_seen": str(r.get("first_seen") or "")}
        return entid_to_name, name_to_ent

    # -------------------------
    # Builders
    # -------------------------
    def build_ge(self, rows_entities: List[Dict[str, Any]], rows_events: List[Dict[str, Any]], rows_parts: List[Dict[str, Any]], params: SnapshotParams) -> Dict[str, Any]:
        entid_to_name, _ = self._load_entity_map_from_rows(rows_entities)
        _, abs_to_evt = self._load_event_map_from_rows(rows_events)

        edges: List[Dict[str, Any]] = []
        deg: Dict[str, int] = {}
        nodes: Dict[str, Dict[str, Any]] = {}

        for r in rows_parts:
            t = _edge_time_fallback(str(r.get("time") or ""), str(r.get("event_start_time") or ""), str(r.get("evt_reported_at") or ""), str(r.get("first_seen") or ""))
            if not self._filter_by_days_window(t, params.days_window):
                continue
            abs_key = str(r.get("abstract") or "")
            evt_node = f"EVT:{abs_key}"
            ent_name = entid_to_name.get(str(r.get("entity_id")), "")
            if not abs_key or not ent_name:
                continue

            if evt_node not in nodes:
                evt = abs_to_evt.get(abs_key, {})
                nodes[evt_node] = {
                    "id": evt_node,
                    "label": (evt.get("event_summary") or abs_key)[:80],
                    "type": "event",
                    "color": "#ff7f0e",
                    "time": _edge_time_fallback(evt.get("event_start_time", ""), evt.get("reported_at", ""), evt.get("first_seen", "")),
                }
            if ent_name not in nodes:
                nodes[ent_name] = {"id": ent_name, "label": ent_name, "type": "entity", "color": "#1f77b4"}

            title = "involved_in"
            try:
                roles = json.loads(r.get("roles_json") or "[]")
                if isinstance(roles, list) and roles:
                    title = " / ".join([x for x in roles if isinstance(x, str) and x.strip()][:6])
            except Exception:
                pass

            edges.append({"from": ent_name, "to": evt_node, "type": "involved_in", "title": title, "time": t})
            deg[ent_name] = deg.get(ent_name, 0) + 1
            deg[evt_node] = deg.get(evt_node, 0) + 1

        top = set(sorted(deg, key=deg.get, reverse=True)[: params.top_entities + params.top_events])
        edges2 = [e for e in edges if e["from"] in top and e["to"] in top][: params.max_edges]
        nodes2 = [v for k, v in nodes.items() if k in top]
        return {"meta": {"graph_type": "GE", "generated_at": _utc_now_iso()}, "nodes": nodes2, "edges": edges2}

    def build_get(self, rows_entities: List[Dict[str, Any]], rows_events: List[Dict[str, Any]], rows_parts: List[Dict[str, Any]], params: SnapshotParams) -> Dict[str, Any]:
        entid_to_name, _ = self._load_entity_map_from_rows(rows_entities)
        _, abs_to_evt = self._load_event_map_from_rows(rows_events)

        by_ent: Dict[str, List[Tuple[str, str]]] = {}
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        for r in rows_parts:
            ent = entid_to_name.get(str(r.get("entity_id")), "")
            abs_key = str(r.get("abstract") or "")
            if not ent or not abs_key:
                continue
            t = _edge_time_fallback(str(r.get("time") or ""), str(r.get("event_start_time") or ""), str(r.get("evt_reported_at") or ""), str(r.get("first_seen") or ""))
            if not self._filter_by_days_window(t, params.days_window):
                continue
            evt_node = f"EVT:{abs_key}"
            by_ent.setdefault(ent, []).append((t, evt_node))

            nodes.setdefault(ent, {"id": ent, "label": ent, "type": "entity", "color": "#1f77b4"})
            if evt_node not in nodes:
                evt = abs_to_evt.get(abs_key, {})
                nodes[evt_node] = {
                    "id": evt_node,
                    "label": (evt.get("event_summary") or abs_key)[:80],
                    "type": "event",
                    "color": "#ff7f0e",
                    "time": _edge_time_fallback(evt.get("event_start_time", ""), evt.get("reported_at", ""), evt.get("first_seen", "")),
                }
            edges.append({"from": ent, "to": evt_node, "type": "involved_in", "title": "involved_in", "time": t})

        for ent, seq in by_ent.items():
            seq2 = sorted(seq, key=lambda x: x[0])
            for i in range(1, len(seq2)):
                edges.append({"from": seq2[i - 1][1], "to": seq2[i][1], "type": "before", "title": "before", "time": seq2[i][0]})

        deg: Dict[str, int] = {}
        for e in edges:
            deg[e["from"]] = deg.get(e["from"], 0) + 1
            deg[e["to"]] = deg.get(e["to"], 0) + 1
        top = set(sorted(deg, key=deg.get, reverse=True)[: params.top_entities + params.top_events])
        edges2 = [e for e in edges if e["from"] in top and e["to"] in top][: params.max_edges]
        nodes2 = [v for k, v in nodes.items() if k in top]
        return {"meta": {"graph_type": "GET", "generated_at": _utc_now_iso()}, "nodes": nodes2, "edges": edges2}

    def build_ee(self, rows_entities: List[Dict[str, Any]], rows_rels: List[Dict[str, Any]], params: SnapshotParams) -> Dict[str, Any]:
        entid_to_name, _ = self._load_entity_map_from_rows(rows_entities)

        agg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for r in rows_rels:
            s = entid_to_name.get(str(r.get("subject_entity_id")), "")
            o = entid_to_name.get(str(r.get("object_entity_id")), "")
            p = str(r.get("predicate") or "").strip()
            t = str(r.get("time") or "").strip() or _utc_now_iso()
            if not s or not o or not p:
                continue
            if not self._filter_by_days_window(t, params.days_window):
                continue
            key = (s, p, o)
            item = agg.get(key)
            if item is None:
                item = {"from": s, "to": o, "type": "relation", "title": p, "time_first": t, "time_last": t, "evidence": []}
                agg[key] = item
            if t < item["time_first"]:
                item["time_first"] = t
            if t > item["time_last"]:
                item["time_last"] = t
            try:
                ev = json.loads(r.get("evidence_json") or "[]")
                if isinstance(ev, list):
                    for x in ev:
                        if isinstance(x, str) and x.strip() and x not in item["evidence"]:
                            item["evidence"].append(x.strip())
            except Exception:
                pass

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        for _, v in agg.items():
            s = v["from"]
            o = v["to"]
            nodes.setdefault(s, {"id": s, "label": s, "type": "entity", "color": "#1f77b4"})
            nodes.setdefault(o, {"id": o, "label": o, "type": "entity", "color": "#1f77b4"})
            edges.append(
                {
                    "from": s,
                    "to": o,
                    "type": "relation",
                    "title": v["title"],
                    "time": v["time_first"],
                    "attrs": {"last_seen": v["time_last"], "evidence": v["evidence"][:5]},
                }
            )

        deg: Dict[str, int] = {}
        for e in edges:
            deg[e["from"]] = deg.get(e["from"], 0) + 1
            deg[e["to"]] = deg.get(e["to"], 0) + 1
        top = set(sorted(deg, key=deg.get, reverse=True)[: params.top_entities])
        edges2 = [e for e in edges if e["from"] in top and e["to"] in top][: params.max_edges]
        nodes2 = [v for k, v in nodes.items() if k in top]
        return {"meta": {"graph_type": "EE", "generated_at": _utc_now_iso()}, "nodes": nodes2, "edges": edges2}

    def build_ee_evo(self, rows_entities: List[Dict[str, Any]], rows_rels: List[Dict[str, Any]], params: SnapshotParams) -> Dict[str, Any]:
        entid_to_name, _ = self._load_entity_map_from_rows(rows_entities)

        groups: Dict[Tuple[str, str, str], List[Tuple[str, List[str]]]] = {}
        for r in rows_rels:
            s = entid_to_name.get(str(r.get("subject_entity_id")), "")
            o = entid_to_name.get(str(r.get("object_entity_id")), "")
            p = str(r.get("predicate") or "").strip()
            t = str(r.get("time") or "").strip() or _utc_now_iso()
            if not s or not o or not p:
                continue
            if not self._filter_by_days_window(t, params.days_window):
                continue
            ev_list: List[str] = []
            try:
                ev = json.loads(r.get("evidence_json") or "[]")
                if isinstance(ev, list):
                    ev_list = [x.strip() for x in ev if isinstance(x, str) and x.strip()]
            except Exception:
                ev_list = []
            groups.setdefault((s, p, o), []).append((t, ev_list))

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        gap = timedelta(days=int(params.gap_days))
        for (s, p, o), seq in groups.items():
            seq2 = sorted(seq, key=lambda x: x[0])
            intervals: List[List[Tuple[str, List[str]]]] = []
            cur: List[Tuple[str, List[str]]] = []
            last_dt: Optional[datetime] = None
            for t, evs in seq2:
                dt = _parse_iso(t)
                if last_dt and dt and (dt - last_dt) > gap and cur:
                    intervals.append(cur)
                    cur = []
                cur.append((t, evs))
                last_dt = dt or last_dt
            if cur:
                intervals.append(cur)

            nodes.setdefault(s, {"id": s, "label": s, "type": "entity", "color": "#1f77b4"})
            nodes.setdefault(o, {"id": o, "label": o, "type": "entity", "color": "#1f77b4"})

            for idx, itv in enumerate(intervals):
                t0 = itv[0][0]
                t1 = itv[-1][0]
                rel_id = f"REL:{s}|{p}|{o}|{idx}"
                evs_flat: List[str] = []
                for _, evs in itv:
                    for e in evs:
                        if e not in evs_flat:
                            evs_flat.append(e)
                nodes[rel_id] = {
                    "id": rel_id,
                    "label": p,
                    "type": "relation_state",
                    "color": "#999999",
                    "time": t0,
                    "attrs": {"valid_from": t0, "valid_to": t1, "evidence": evs_flat[:5]},
                }
                edges.append({"from": s, "to": rel_id, "type": "rel_in", "title": "rel", "time": t0})
                edges.append({"from": rel_id, "to": o, "type": "rel_out", "title": "rel", "time": t0})

        return {
            "meta": {"graph_type": "EE_EVO", "generated_at": _utc_now_iso()},
            "nodes": list(nodes.values())[: params.top_entities + params.top_events],
            "edges": edges[: params.max_edges],
        }

    def build_event_evo(self, rows_entities: List[Dict[str, Any]], rows_events: List[Dict[str, Any]], rows_edges: List[Dict[str, Any]], rows_parts: List[Dict[str, Any]], params: SnapshotParams) -> Dict[str, Any]:
        entid_to_name, _ = self._load_entity_map_from_rows(rows_entities)
        evtid_to_abs, abs_to_evt = self._load_event_map_from_rows(rows_events)

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        for r in rows_edges:
            from_id = str(r.get("from_event_id"))
            to_id = str(r.get("to_event_id"))
            a = evtid_to_abs.get(from_id, "")
            b = evtid_to_abs.get(to_id, "")
            if not a or not b:
                continue
            t = _edge_time_fallback(str(r.get("time") or ""), abs_to_evt.get(a, {}).get("event_start_time", ""), abs_to_evt.get(a, {}).get("reported_at", ""))
            if not self._filter_by_days_window(t, params.days_window):
                continue
            na = f"EVT:{a}"
            nb = f"EVT:{b}"
            if na not in nodes:
                ea = abs_to_evt.get(a, {})
                nodes[na] = {"id": na, "label": (ea.get("event_summary") or a)[:80], "type": "event", "color": "#ff7f0e", "time": _edge_time_fallback(ea.get("event_start_time",""), ea.get("reported_at",""), ea.get("first_seen",""))}
            if nb not in nodes:
                eb = abs_to_evt.get(b, {})
                nodes[nb] = {"id": nb, "label": (eb.get("event_summary") or b)[:80], "type": "event", "color": "#ff7f0e", "time": _edge_time_fallback(eb.get("event_start_time",""), eb.get("reported_at",""), eb.get("first_seen",""))}
            try:
                ev = json.loads(r.get("evidence_json") or "[]")
                if not isinstance(ev, list):
                    ev = []
            except Exception:
                ev = []
            edges.append({"from": na, "to": nb, "type": "event_edge", "title": str(r.get("edge_type") or "related"), "time": t, "confidence": float(r.get("confidence") or 0.0), "evidence": ev[:5]})

        # very light affects edges
        for r in rows_parts:
            abs_key = str(r.get("abstract") or "")
            evt_node = f"EVT:{abs_key}"
            ent_name = entid_to_name.get(str(r.get("entity_id")), "")
            if not abs_key or not ent_name:
                continue
            t = _edge_time_fallback(str(r.get("time") or ""), abs_to_evt.get(abs_key, {}).get("reported_at", ""))
            if not self._filter_by_days_window(t, params.days_window):
                continue
            try:
                roles = json.loads(r.get("roles_json") or "[]")
                if not isinstance(roles, list):
                    roles = []
            except Exception:
                roles = []
            if not any(isinstance(x, str) and ("被" in x or "受" in x or "遭" in x) for x in roles):
                continue
            nodes.setdefault(evt_node, {"id": evt_node, "label": (str(r["event_summary"] or abs_key))[:80], "type": "event", "color": "#ff7f0e"})
            nodes.setdefault(ent_name, {"id": ent_name, "label": ent_name, "type": "entity", "color": "#1f77b4"})
            edges.append({"from": evt_node, "to": ent_name, "type": "affects", "title": "affects", "time": t})

        return {"meta": {"graph_type": "EVENT_EVO", "generated_at": _utc_now_iso()}, "nodes": list(nodes.values()), "edges": edges[: params.max_edges]}

    # -------------------------
    # Public API
    # -------------------------
    def generate(
        self,
        *,
        top_entities: int = 500,
        top_events: int = 500,
        max_edges: int = 5000,
        days_window: int = 0,
        gap_days: int = 30,
    ) -> Dict[str, Any]:
        if not self.db_path.exists():
            return {"status": "error", "message": f"SQLite not found: {self.db_path}"}

        params = SnapshotParams(
            top_entities=int(top_entities),
            top_events=int(top_events),
            max_edges=int(max_edges),
            days_window=int(days_window),
            gap_days=int(gap_days),
        )
        _ensure_dir(self.out_dir)

        rows_entities = self.store.fetch_entities()
        rows_events = self.store.fetch_events()
        rows_parts = self.store.fetch_participants_with_events()
        rows_rels = self.store.fetch_relations()
        rows_edges = self.store.fetch_event_edges()

        ge = self.build_ge(rows_entities, rows_events, rows_parts, params)
        get = self.build_get(rows_entities, rows_events, rows_parts, params)
        ee = self.build_ee(rows_entities, rows_rels, params)
        ee_evo = self.build_ee_evo(rows_entities, rows_rels, params)
        event_evo = self.build_event_evo(rows_entities, rows_events, rows_edges, rows_parts, params)

        paths = {}
        for name, obj in [("GE", ge), ("GET", get), ("EE", ee), ("EE_EVO", ee_evo), ("EVENT_EVO", event_evo)]:
            p = self.out_dir / f"{name}.json"
            p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            paths[name] = str(p)

        return {"status": "ok", "paths": paths}


