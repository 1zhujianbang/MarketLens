from __future__ import annotations

import json
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from ...infra.registry import register_tool
from ...adapters.sqlite.store import get_store, canonical_entity_id
from ...infra.serialization import extract_json_from_llm_response
from ...infra.async_utils import call_llm_with_retry, RateLimiter
from ...adapters.llm import LLMAPIPool


PROMPT_VERSION = "review-v1"

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    # 简单归一化：去掉空格与常见标点
    for ch in [" ", "\t", "\n", "\r", "·", "•", "-", "_", ".", ",", "，", "。", "（", "）", "(", ")", "[", "]", "{", "}", "\"", "'"]:
        s = s.replace(ch, "")
    return s


def _name_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm_name(a), _norm_name(b)).ratio()


def _entity_merge_review_prompt(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """
    输出必须严格 JSON（避免硬编码合并策略，交给 LLM 裁决）。
    """
    return f"""你是一名知识图谱数据治理与实体消歧专家。请判断以下两个“实体记录”是否应当合并为同一个现实世界实体。

要求：
1) 只返回 JSON，不要任何额外文本。
2) merge=true 仅在“高度确定同一实体”时给出；不确定就 merge=false。
3) 如果 merge=true，必须给出 canonical_name（推荐更标准/更完整/更官方的名称），并解释原因与置信度。

实体A：
{json.dumps(a, ensure_ascii=False, indent=2)}

实体B：
{json.dumps(b, ensure_ascii=False, indent=2)}

输出 JSON schema：
{{
  "merge": true|false,
  "canonical_name": "合并后建议的主实体名称（merge=false 也要给一个推荐名称，可为空字符串）",
  "confidence": 0.0,
  "reasons": ["原因1","原因2"],
  "evidence": ["引用的别名/来源/上下文依据，尽量短"]
}}
"""


def _event_merge_or_evolve_prompt(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    return f"""你是一名知识图谱“事件消歧/事件演化”专家。请判断两个事件是否：
1) merge：同一事件的不同表述/不同来源报道（应合并为同一个 canonical event）
2) evolve：不是同一事件，但存在明确的顺承/回应/升级/因果等发展关系（应建立事件-事件边）
3) separate：无强关系或信息不足（不合并也不连边）

要求：
- 只返回 JSON，不要任何额外文本。
- 若 decision="merge"，给出 canonical_abstract（推荐保留更标准/更信息密度的摘要）与置信度。
- 若 decision="evolve"，必须给出 edge_type（follows/responds_to/escalates/causes/related 之一）与置信度，并给出证据。
- 不确定就 separate。

事件A：
{json.dumps(a, ensure_ascii=False, indent=2)}

事件B：
{json.dumps(b, ensure_ascii=False, indent=2)}

输出 JSON schema：
{{
  "decision": "merge"|"evolve"|"separate",
  "canonical_abstract": "（merge时必填，否则空字符串）",
  "edge_type": "follows"|"responds_to"|"escalates"|"causes"|"related",
  "confidence": 0.0,
  "reasons": ["原因1","原因2"],
  "evidence": ["引用的时间/地点/实体/关系片段，尽量短"]
}}
"""


@register_tool(
    name="enqueue_entity_merge_candidates",
    description="生成实体合并候选并入队 review_tasks（只做候选生成，不做最终决策）",
    category="Review",
)
def enqueue_entity_merge_candidates(
    min_similarity: float = 0.92,
    max_pairs: int = 200,
) -> Dict[str, Any]:
    store = get_store()
    # 读取实体列表（name + original_forms）
    entities = store.export_entities_json()
    names = list(entities.keys())

    pairs: List[Tuple[str, str, float, str]] = []  # a,b,score,reason

    # 1) 强候选：通过 original_forms 映射（跨语言/别名）
    form_index: Dict[str, List[str]] = {}
    for name, rec in entities.items():
        forms = rec.get("original_forms") or []
        for f in ([name] + list(forms)):
            if not isinstance(f, str) or not f.strip():
                continue
            key = _norm_name(f)
            if not key:
                continue
            form_index.setdefault(key, []).append(name)

    for key, group in form_index.items():
        if len(pairs) >= max_pairs:
            break
        uniq = []
        for g in group:
            if g not in uniq:
                uniq.append(g)
        if len(uniq) < 2:
            continue
        # 同一 key 下的实体都视为候选（score=1.0）
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                pairs.append((a, b, 1.0, "original_forms_match"))
                if len(pairs) >= max_pairs:
                    break
            if len(pairs) >= max_pairs:
                break

    # 2) 次候选：名称相似（归一化后高相似）+ 分桶减少计算
    if len(pairs) < max_pairs:
        buckets: Dict[str, List[str]] = {}
        for n in names:
            key = _norm_name(n)[:6]
            buckets.setdefault(key, []).append(n)

        for _, group in buckets.items():
            if len(pairs) >= max_pairs:
                break
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    sim = _name_sim(a, b)
                    if sim >= float(min_similarity):
                        pairs.append((a, b, sim, "name_similarity"))
                    if len(pairs) >= max_pairs:
                        break
                if len(pairs) >= max_pairs:
                    break

    enqueued = 0
    seen_pair = set()
    for a, b, sim, why in pairs:
        k = tuple(sorted([a, b]))
        if k in seen_pair:
            continue
        seen_pair.add(k)
        payload = {"entity_a": a, "entity_b": b, "similarity": sim, "candidate_reason": why}
        store.enqueue_review_task("entity_merge_review", payload, priority=int(sim * 100))
        enqueued += 1

    return {"status": "ok", "candidates": len(seen_pair), "enqueued": enqueued}


@register_tool(
    name="enqueue_event_merge_or_evolve_candidates",
    description="生成事件候选对并入队（merge/evolve 审查）。候选规则：共享实体+时间接近优先",
    category="Review",
)
def enqueue_event_merge_or_evolve_candidates(
    max_pairs: int = 200,
    shared_entity_min: int = 2,
    days_window: int = 14,
) -> Dict[str, Any]:
    store = get_store()
    # 用 compat export 快速获取事件（后续可直接 SQL 优化）
    am = store.export_abstract_map_json()
    # 取 (event_id, abstract, time, entities)
    items = []
    for abstract, data in (am or {}).items():
        if not isinstance(data, dict):
            continue
        evt_id = str(data.get("event_id") or "").strip()
        if not evt_id:
            continue
        # time：优先 event_start_time，其次 reported_at/first_seen
        t = str(data.get("event_start_time") or data.get("reported_at") or data.get("first_seen") or "").strip()
        ents = data.get("entities") or []
        ents = [e for e in ents if isinstance(e, str) and e.strip()]
        items.append((evt_id, abstract, t, ents))

    # 简单候选：按共享实体分桶，再在桶内两两配对（限制 max_pairs）
    ent_buckets: Dict[str, List[int]] = {}
    for idx, (_, _, _, ents) in enumerate(items):
        for e in set(ents):
            ent_buckets.setdefault(e, []).append(idx)

    pair_scores: Dict[Tuple[int, int], int] = {}
    for _, idxs in ent_buckets.items():
        if len(idxs) < 2:
            continue
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                a, b = idxs[i], idxs[j]
                if a == b:
                    continue
                key = (a, b) if a < b else (b, a)
                pair_scores[key] = pair_scores.get(key, 0) + 1

    # 取共享实体数最高的 TopN
    candidates = sorted(pair_scores.items(), key=lambda x: x[1], reverse=True)[: int(max_pairs)]
    enq = 0
    for (i, j), shared in candidates:
        if shared < int(shared_entity_min):
            continue
        a = items[i]
        b = items[j]
        payload = {
            "event_a": {"event_id": a[0], "abstract": a[1], "time": a[2], "entities": a[3][:30]},
            "event_b": {"event_id": b[0], "abstract": b[1], "time": b[2], "entities": b[3][:30]},
            "shared_entities": shared,
        }
        store.enqueue_review_task("event_merge_or_evolve_review", payload, priority=min(100, shared * 10))
        enq += 1

    return {"status": "ok", "pairs_scored": len(pair_scores), "enqueued": enq}


@register_tool(
    name="run_review_worker",
    description="运行 LLM 审查 worker：从 review_tasks 领取任务→调用 LLM→写入 merge_decisions 并完成任务",
    category="Review",
)
def run_review_worker(
    task_type: str = "entity_merge_review",
    max_tasks: int = 20,
    rate_limit_per_sec: float = 0.5,
) -> Dict[str, Any]:
    store = get_store()
    limiter = RateLimiter(rate_per_sec=rate_limit_per_sec) if rate_limit_per_sec and rate_limit_per_sec > 0 else None
    llm_pool = get_llm_pool()

    done = 0
    failed = 0
    for _ in range(int(max_tasks)):
        task = store.claim_next_review_task(task_type=task_type)
        if not task:
            break
        task_id = task["task_id"]
        input_hash = task["input_hash"]
        payload = task.get("payload") or {}
        try:
            if task_type == "entity_merge_review":
                a_name = str(payload.get("entity_a") or "").strip()
                b_name = str(payload.get("entity_b") or "").strip()
                a = store.get_entity_record_by_name(a_name) or {"name": a_name}
                b = store.get_entity_record_by_name(b_name) or {"name": b_name}
                a["_name"] = a_name
                b["_name"] = b_name
                a["event_samples"] = store.get_entity_event_samples(a_name, limit=3)
                b["event_samples"] = store.get_entity_event_samples(b_name, limit=3)
                prompt = _entity_merge_review_prompt(a, b)
            elif task_type == "event_merge_or_evolve_review":
                pa = payload.get("event_a") or {}
                pb = payload.get("event_b") or {}
                a_id = str(pa.get("event_id") or "").strip()
                b_id = str(pb.get("event_id") or "").strip()
                # 从 compat map 获取更完整字段
                am = store.export_abstract_map_json()
                a_abs = str(pa.get("abstract") or "").strip()
                b_abs = str(pb.get("abstract") or "").strip()
                a_full = (am.get(a_abs) if a_abs in am else None) or {"event_id": a_id, "abstract": a_abs}
                b_full = (am.get(b_abs) if b_abs in am else None) or {"event_id": b_id, "abstract": b_abs}
                prompt = _event_merge_or_evolve_prompt(a_full, b_full)
            else:
                raise ValueError(f"Unsupported task_type: {task_type}")

            if limiter:
                limiter.acquire()
            text = call_llm_with_retry(llm_pool, prompt, max_tokens=1400, timeout=120, retries=4, limiter=None)  # limiter 已在外层
            if not text:
                raise ValueError("Empty LLM response")
            out = extract_json_from_llm_response(text)

            store.upsert_merge_decision(task_type, input_hash, out, model="auto", prompt_version=PROMPT_VERSION)
            store.complete_review_task(task_id, status="done", output=out, model="auto", prompt_version=PROMPT_VERSION)
            done += 1
        except Exception as e:
            store.complete_review_task(task_id, status="failed", error=str(e))
            failed += 1

    return {"status": "ok", "done": done, "failed": failed}


@register_tool(
    name="apply_entity_merge_decisions",
    description="应用已完成的实体合并决策：执行 from->to 合并，更新外键并导出兼容 JSON",
    category="Review",
)
def apply_entity_merge_decisions(max_actions: int = 50) -> Dict[str, Any]:
    store = get_store()
    applied = 0
    skipped = 0

    # 读取 merge_decisions（entity_merge_review）
    # 规则：merge=true 时执行；canonical_name 只做 alias 参考（主键仍是 entity_id）
    import sqlite3

    with store._lock:  # 复用 store 内锁（这里是内部调用，接受）
        conn = store._connect()
        try:
            rows = conn.execute(
                """
                SELECT input_hash, output_json
                FROM merge_decisions
                WHERE type='entity_merge_review'
                ORDER BY decision_id ASC
                """
            ).fetchall()
        finally:
            conn.close()

    # 为了从 input_hash 找回任务 payload（entity_a/entity_b），从 review_tasks 反查
    with store._lock:
        conn = store._connect()
        try:
            task_map = {
                str(r["input_hash"]): json.loads(r["payload_json"] or "{}")
                for r in conn.execute(
                    "SELECT input_hash, payload_json FROM review_tasks WHERE type='entity_merge_review'"
                ).fetchall()
            }
        finally:
            conn.close()

    for r in rows:
        if applied >= int(max_actions):
            break
        input_hash = str(r["input_hash"])
        try:
            out = json.loads(r["output_json"] or "{}")
        except Exception:
            skipped += 1
            continue

        if not isinstance(out, dict) or not out.get("merge"):
            skipped += 1
            continue

        payload = task_map.get(input_hash) or {}
        a_name = str(payload.get("entity_a") or "").strip()
        b_name = str(payload.get("entity_b") or "").strip()
        if not a_name or not b_name:
            skipped += 1
            continue

        # 选择 to_entity：优先 canonical_name 如果等于其中一个，否则选“更长更完整”的名字作为主实体
        canonical_name = str(out.get("canonical_name") or "").strip()
        if canonical_name == a_name:
            to_name, from_name = a_name, b_name
        elif canonical_name == b_name:
            to_name, from_name = b_name, a_name
        else:
            to_name, from_name = (a_name, b_name) if len(a_name) >= len(b_name) else (b_name, a_name)

        res = store.merge_entities(
            canonical_entity_id(from_name),
            canonical_entity_id(to_name),
            reason="entity_merge_review",
            decision_input_hash=input_hash,
        )
        if res.get("status") == "merged":
            applied += 1
        else:
            skipped += 1

    if applied > 0:
        store.export_compat_json_files()

    return {"status": "ok", "applied": applied, "skipped": skipped}


@register_tool(
    name="apply_event_merge_or_evolve_decisions",
    description="应用事件审查决策：merge 执行事件合并；evolve 写入 event_edges（所有边有 time）",
    category="Review",
)
def apply_event_merge_or_evolve_decisions(max_actions: int = 50) -> Dict[str, Any]:
    store = get_store()
    applied_merge = 0
    applied_edges = 0
    skipped = 0

    with store._lock:
        conn = store._connect()
        try:
            rows = conn.execute(
                "SELECT input_hash, output_json FROM merge_decisions WHERE type='event_merge_or_evolve_review' ORDER BY decision_id ASC"
            ).fetchall()
            task_map = {
                str(r["input_hash"]): json.loads(r["payload_json"] or "{}")
                for r in conn.execute(
                    "SELECT input_hash, payload_json FROM review_tasks WHERE type='event_merge_or_evolve_review'"
                ).fetchall()
            }
        finally:
            conn.close()

    for r in rows:
        if (applied_merge + applied_edges) >= int(max_actions):
            break
        input_hash = str(r["input_hash"])
        try:
            out = json.loads(r["output_json"] or "{}")
        except Exception:
            skipped += 1
            continue
        if not isinstance(out, dict):
            skipped += 1
            continue
        payload = task_map.get(input_hash) or {}
        ea = payload.get("event_a") or {}
        eb = payload.get("event_b") or {}
        a_id = str(ea.get("event_id") or "").strip()
        b_id = str(eb.get("event_id") or "").strip()
        if not a_id or not b_id:
            skipped += 1
            continue

        decision = str(out.get("decision") or "").strip().lower()
        confidence = float(out.get("confidence") or 0.0)
        evidence = out.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        evidence = [x for x in evidence if isinstance(x, str) and x.strip()]
        edge_type = str(out.get("edge_type") or "related").strip() or "related"

        # time：优先用两事件中更早的 time（用于演化边排序）
        t = str(ea.get("time") or eb.get("time") or "").strip()
        if not t:
            t = _utc_now_iso()
        rep = _utc_now_iso()

        if decision == "merge":
            # canonical_abstract 若等于其中一个 abstract，则选对应 event_id 为主；否则保留 a_id 为主（可后续优化）
            canonical_abs = str(out.get("canonical_abstract") or "").strip()
            to_id, from_id = a_id, b_id
            if canonical_abs and canonical_abs == str(eb.get("abstract") or ""):
                to_id, from_id = b_id, a_id
            res = store.merge_events(from_id, to_id, reason="event_merge_or_evolve_review", decision_input_hash=input_hash)
            if res.get("status") == "merged":
                applied_merge += 1
            else:
                skipped += 1
        elif decision == "evolve":
            # 写 event_edges（保证 time 非空）
            with store._lock:
                conn = store._connect()
                try:
                    conn.execute(
                        """
                        INSERT INTO event_edges(from_event_id,to_event_id,edge_type,time,reported_at,confidence,evidence_json,decision_input_hash)
                        VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(from_event_id,to_event_id,edge_type) DO UPDATE SET
                            time=excluded.time, reported_at=excluded.reported_at, confidence=excluded.confidence, evidence_json=excluded.evidence_json
                        """,
                        (a_id, b_id, edge_type, t, rep, confidence, json.dumps(evidence, ensure_ascii=False), input_hash),
                    )
                    conn.commit()
                finally:
                    conn.close()
            applied_edges += 1
        else:
            skipped += 1

    if (applied_merge + applied_edges) > 0:
        store.export_compat_json_files()

    return {"status": "ok", "merged": applied_merge, "edges_added": applied_edges, "skipped": skipped}


@register_tool(
    name="requeue_stale_review_tasks",
    description="将卡死的 running 审查任务回收到 pending（避免中断导致 worker 永久取不到任务）",
    category="Review",
)
def requeue_stale_review_tasks(max_age_minutes: int = 10) -> Dict[str, Any]:
    store = get_store()
    n = store.requeue_stale_review_tasks(max_age_minutes=max_age_minutes)
    return {"status": "ok", "requeued": n, "max_age_minutes": int(max_age_minutes)}


@register_tool(
    name="review_entity_merges_end_to_end",
    description="端到端：生成候选→LLM审查→应用合并→导出（SQLite为主存储，且每条元组有time）",
    category="Review",
)
def review_entity_merges_end_to_end(
    min_similarity: float = 0.92,
    max_pairs: int = 200,
    max_review_tasks: int = 30,
    rate_limit_per_sec: float = 0.5,
    max_apply: int = 30,
) -> Dict[str, Any]:
    c = enqueue_entity_merge_candidates(min_similarity=min_similarity, max_pairs=max_pairs)
    w = run_review_worker(task_type="entity_merge_review", max_tasks=max_review_tasks, rate_limit_per_sec=rate_limit_per_sec)
    a = apply_entity_merge_decisions(max_actions=max_apply)
    return {"status": "ok", "candidates": c, "review": w, "applied": a}


@register_tool(
    name="review_queue_stats",
    description="输出审查队列统计（pending/running/done/failed）与样例任务（避免 PowerShell 引号问题）",
    category="Review",
)
def review_queue_stats() -> Dict[str, Any]:
    store = get_store()
    with store._lock:
        c = store._connect()
        try:
            rows = c.execute("select status, count(1) from review_tasks group by status").fetchall()
            stats = {r[0]: int(r[1]) for r in rows}
            sample = c.execute(
                "select task_id,type,status,priority,substr(updated_at,1,19) as updated_at from review_tasks order by updated_at desc limit 5"
            ).fetchall()
        finally:
            c.close()
    sample_out = []
    for r in sample or []:
        try:
            sample_out.append(dict(r))
        except Exception:
            sample_out.append(list(r))
    return {"status": "ok", "stats": stats, "sample": sample_out}


@register_tool(
    name="review_failed_tasks",
    description="列出最近失败的审查任务（含 error 摘要）",
    category="Review",
)
def review_failed_tasks(limit: int = 10) -> Dict[str, Any]:
    store = get_store()
    with store._lock:
        c = store._connect()
        try:
            rows = c.execute(
                "select task_id,type,substr(error,1,300) as error,substr(updated_at,1,19) as updated_at from review_tasks where status='failed' order by updated_at desc limit ?",
                (int(limit),),
            ).fetchall()
        finally:
            c.close()
    out = []
    for r in rows or []:
        try:
            out.append(dict(r))
        except Exception:
            out.append(list(r))
    return {"status": "ok", "failed": out}


@register_tool(
    name="event_evolution_stats",
    description="查看事件演化投影数据统计：event_edges 数量、事件审查决策数量、待处理任务数量",
    category="Review",
)
def event_evolution_stats() -> Dict[str, Any]:
    store = get_store()
    with store._lock:
        c = store._connect()
        try:
            edges = int(c.execute("select count(1) from event_edges").fetchone()[0])
            dec = int(c.execute("select count(1) from merge_decisions where type='event_merge_or_evolve_review'").fetchone()[0])
            pending = int(c.execute("select count(1) from review_tasks where type='event_merge_or_evolve_review' and status='pending'").fetchone()[0])
            running = int(c.execute("select count(1) from review_tasks where type='event_merge_or_evolve_review' and status='running'").fetchone()[0])
            done = int(c.execute("select count(1) from review_tasks where type='event_merge_or_evolve_review' and status='done'").fetchone()[0])
            failed = int(c.execute("select count(1) from review_tasks where type='event_merge_or_evolve_review' and status='failed'").fetchone()[0])
        finally:
            c.close()
    return {
        "status": "ok",
        "event_edges": edges,
        "event_review_decisions": dec,
        "tasks": {"pending": pending, "running": running, "done": done, "failed": failed},
    }


