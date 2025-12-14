from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from src.web import utils
from src.web.config import PROJECT_ROOT
from src.web.framework.user_context import can_write, get_user_context, render_user_context_controls
from src.web.services.pipeline_runner import get_global_pipeline_runner, append_history
from src.web.services.run_store import (
    list_runs,
    load_run_change_pack,
    load_run_context_snapshot,
    save_evidence_content_snippet,
    save_evidence_note,
)
from src.web.services.news_lookup import find_news_by_id
import hashlib


def render() -> None:
    render_user_context_controls()
    st.title("🕵️ Data Inspector")
    st.caption("用于审查与检索：默认聚焦最近24h新增（以发布时间/发现时间为准）")

    def normalize_mixed(val):
        if val is None:
            return ""
        if isinstance(val, (list, dict)):
            try:
                return json.dumps(val, ensure_ascii=False)
            except Exception:
                return str(val)
        return str(val)

    tab_recent, tab_runs, tab_entities, tab_events, tab_news, tab_tmp = st.tabs(
        ["🆕 最近24h新增", "🗂️ Runs 审查", "🧠 Entities", "🔗 Events", "📰 Raw News", "🗃️ Extracted Snapshots"]
    )

    def _parse_iso(dt_str: str):
        if not dt_str:
            return None
        try:
            # normalize Z
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def _within_last(dt_str: str, hours: int) -> bool:
        dt = _parse_iso(dt_str)
        if not dt:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= (datetime.now(timezone.utc) - timedelta(hours=hours))

    with tab_recent:
        st.subheader("🆕 最近24h新增（审查入口）")
        st.caption("默认按 published_at（若存在）否则按 first_seen 过滤。用于快速确认新增与遗漏。")

        # 1) 新增事件（优先）
        events_data = utils.load_events()
        recent_events = []
        for abstract, info in (events_data or {}).items():
            if not isinstance(info, dict):
                continue
            ts = info.get("published_at") or info.get("first_seen") or ""
            if _within_last(str(ts), 24):
                recent_events.append(
                    {
                        "abstract": abstract,
                        "event_summary": info.get("event_summary", "") or abstract,
                        "time": ts,
                        "entities": normalize_mixed(info.get("entities")),
                    }
                )
        df_recent_evt = pd.DataFrame(recent_events)
        c1, c2 = st.columns([3, 1])
        with c2:
            st.metric("最近24h事件", len(df_recent_evt))
        with c1:
            if not df_recent_evt.empty:
                st.dataframe(
                    df_recent_evt.sort_values("time", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("最近24h未检测到新增事件（或事件缺少时间戳字段）。")

        st.divider()

        # 2) 新增实体
        entities_data = utils.load_entities()
        recent_entities = []
        for name, info in (entities_data or {}).items():
            if isinstance(info, dict):
                ts = info.get("first_seen") or ""
            else:
                ts = ""
            if _within_last(str(ts), 24):
                recent_entities.append(
                    {
                        "entity": str(name),
                        "first_seen": ts,
                        "count": (info.get("count") if isinstance(info, dict) else None),
                        "sources": normalize_mixed(info.get("sources") if isinstance(info, dict) else None),
                    }
                )
        df_recent_ent = pd.DataFrame(recent_entities)

        c3, c4 = st.columns([3, 1])
        with c4:
            st.metric("最近24h实体", len(df_recent_ent))
        with c3:
            if not df_recent_ent.empty:
                st.dataframe(
                    df_recent_ent.sort_values("first_seen", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("最近24h未检测到新增实体（或实体缺少 first_seen 字段）。")

        st.divider()

        # 3) 跳转到图谱聚焦（用 session_state 传递）
        st.subheader("🔎 在图谱中聚焦实体")
        all_names = sorted(list((entities_data or {}).keys()))
        focus = st.selectbox("选择实体", options=["(请选择)"] + all_names, index=0)
        if st.button("在知识图谱中聚焦", type="primary", use_container_width=True, disabled=(focus == "(请选择)")):
            st.session_state["kg_focus_entity"] = focus
            st.switch_page("pages/4_Knowledge_Graph.py")

    with tab_runs:
        st.subheader("🗂️ 按 run_id 审查（新增实体/事件 + 证据Pin占位）")
        st.caption("每次在 Pipeline 页面运行后，会在 data/runs 下生成一个 run 变更包（新增实体/事件）。")

        project_id = get_user_context().project_id
        run_files = list_runs(project_id=project_id, limit=50)
        if not run_files:
            st.info("暂无运行记录。请先在 Pipeline 页面执行一次运行。")
        else:
            opts = [p.name for p in run_files]
            default = 0
            sel = st.selectbox("选择运行记录", options=opts, index=default)
            run_path = next(p for p in run_files if p.name == sel)
            pack = load_run_change_pack(run_path)
            run_id = str(pack.get("run_id") or "")

            st.markdown(f"**run_id**: `{run_id}`")
            st.markdown(f"**pipeline**: {pack.get('pipeline_name')}")
            st.markdown(f"**status**: {pack.get('status')}")
            if pack.get("error"):
                st.error(f"error: {pack.get('error')}")
            if pack.get("completed_steps") and pack.get("total_steps"):
                st.caption(f"steps: {pack.get('completed_steps')}/{pack.get('total_steps')}")

            new_events = pack.get("new_events") or []
            new_entities = pack.get("new_entities") or []
            dup_events = pack.get("duplicate_events") or []
            evidence_rows = pack.get("evidence_events") or []

            c1, c2 = st.columns(2)
            c1.metric("新增事件", len(new_events))
            c2.metric("新增实体", len(new_entities))
            if dup_events:
                st.warning(f"检测到可能重复事件（abstract 已存在）：{len(dup_events)}")

            st.divider()
            st.subheader("新增实体（可跳转KG聚焦）")
            if new_entities:
                ent_pick = st.selectbox("选择实体跳转", options=["(请选择)"] + new_entities, index=0)
                if st.button("跳转到KG并聚焦该实体", type="primary", use_container_width=True, disabled=(ent_pick == "(请选择)")):
                    st.session_state["kg_focus_entity"] = ent_pick
                    st.switch_page("pages/4_Knowledge_Graph.py")
            else:
                st.info("该 run 没有新增实体。")

            st.divider()
            st.subheader("新增事件（证据链 + Pin）")
            if not new_events:
                st.info("该 run 没有新增事件。")
            else:
                evt_pick = st.selectbox("选择事件", options=["(请选择)"] + new_events, index=0)
                if evt_pick != "(请选择)":
                    if evidence_rows:
                        # 解析每一行数据，处理制表符分隔的字符串
                        parsed_candidates = []
                        for r in evidence_rows:
                            if isinstance(r, dict):
                                # 已经是字典，直接添加
                                parsed_candidates.append(r)
                            elif isinstance(r, str):
                                # 按制表符分割
                                parts = r.split('\t')
                                if len(parts) >= 4:  # 确保有足够的字段
                                    json_str = parts[3].strip()  # 第4个字段是JSON
                                    # 清理可能的转义字符
                                    if json_str.startswith('"{') and json_str.endswith('}"'):
                                        json_str = json_str[1:-1]  # 去掉外层的双引号
                                    json_str = json_str.replace('\\"', '"')  # 处理转义的双引号
                                    
                                    try:
                                        parsed = json.loads(json_str)
                                        if isinstance(parsed, dict):
                                            parsed_candidates.append(parsed)
                                    except json.JSONDecodeError:
                                        continue  # 解析失败则跳过

                        # 过滤出abstract匹配的事件
                        candidates = [r for r in parsed_candidates if isinstance(r, dict) and r.get("abstract") == evt_pick]
                        if candidates:
                            st.caption("证据链（来自 extracted_events 输出 + raw_news best-effort）")
                            st.dataframe(pd.DataFrame(candidates), hide_index=True, use_container_width=True)
                        else:
                            st.info("该事件未在本次 extracted_events 输出中找到证据链（可能来自其他来源/合并逻辑）。")

                    note = st.text_area("备注（Pin）", height=120, key=f"pin_note_{run_id}_{evt_pick[:20]}")
                    pin_disabled = (not can_write()) or (not run_id)
                    if st.button("📌 Pin 备注", use_container_width=True, disabled=pin_disabled):
                        p = save_evidence_note(
                            project_id=project_id,
                            run_id=run_id or "unknown",
                            kind="event",
                            key=evt_pick,
                            note=note,
                            meta={"source": "data_inspector_runs"},
                        )
                        st.success(f"已保存：{p.name}")

                    st.divider()
                    st.subheader("保存原文片段（低存储，占位实现）")
                    if candidates:
                        news_id = str(candidates[0].get("news_id") or "")
                        item = find_news_by_id(news_id) if news_id else None
                        if item and item.content:
                            max_len = st.slider("截断长度", 300, 4000, 1500, 100)
                            snippet = (item.content or "")[: int(max_len)]
                            h = hashlib.sha256((item.content or "").encode("utf-8")).hexdigest()[:24]
                            st.text_area("预览片段（将保存）", value=snippet, height=160)
                            if st.button("💾 保存原文片段（Pin）", use_container_width=True, disabled=pin_disabled):
                                p = save_evidence_content_snippet(
                                    project_id,
                                    run_id=run_id,
                                    news_id=item.news_id,
                                    url=item.url,
                                    title=item.title,
                                    published_at=item.published_at,
                                    source=item.source,
                                    content_snippet=snippet,
                                    content_hash=h,
                                )
                                st.success(f"已保存：{p.name}")
                        else:
                            st.info("未能从 tmp/raw_news 找到该 news_id 的 content（可能被清理或不在本地）。")

            st.divider()
            st.subheader("复跑/恢复（占位实现）")
            if not can_write():
                st.info("viewer 角色不可复跑。")
            else:
                ctx_file = run_path.parent / f"run_{run_id}_context.json" if run_id else None
                pipeline_def = pack.get("pipeline_def") if isinstance(pack.get("pipeline_def"), dict) else None
                if (not pipeline_def) or (not run_id):
                    st.info("该 run 缺少 pipeline_def 或 run_id，无法复跑。")
                else:
                    runner = get_global_pipeline_runner()
                    colA, colB = st.columns(2)
                    with colA:
                        if st.button("从头复跑", type="primary", use_container_width=True, disabled=runner.is_running):
                            history_idx = append_history(pipeline_def)
                            runner.start(pipeline_def, history_idx=history_idx)
                            st.rerun()
                    with colB:
                        start_at = st.number_input("从第N步开始（实验）", min_value=0, max_value=max(0, len(pipeline_def.get("steps", [])) - 1), value=0, step=1)
                        if st.button("尝试恢复运行", use_container_width=True, disabled=runner.is_running):
                            init_data = {}
                            try:
                                if ctx_file and ctx_file.exists():
                                    init_data = load_run_context_snapshot(ctx_file)
                            except Exception:
                                init_data = {}
                            history_idx = append_history(pipeline_def)
                            runner.start(pipeline_def, history_idx=history_idx, start_at=int(start_at), initial_data=init_data)
                            st.rerun()

    with tab_entities:
        col_filter, col_stat = st.columns([3, 1])
        with col_filter:
            entity_search = st.text_input("🔍 Search Entities", placeholder="e.g. Bitcoin, SEC...")
        entities_data = utils.load_entities()

        if entities_data:
            df_ent = pd.DataFrame.from_dict(entities_data, orient="index")
            df_ent.reset_index(inplace=True)
            df_ent.rename(columns={"index": "Entity Name"}, inplace=True)
            if "sources" in df_ent.columns:
                df_ent["sources"] = df_ent["sources"].apply(normalize_mixed)

            if entity_search:
                df_ent = df_ent[df_ent["Entity Name"].str.contains(entity_search, case=False, na=False)]

            with col_stat:
                st.metric("Total Entities", len(df_ent))

            st.dataframe(
                df_ent,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Entity Name": st.column_config.TextColumn("Entity Name", width="medium"),
                    "count": st.column_config.NumberColumn("Mentions", format="%d"),
                    "first_seen": st.column_config.DatetimeColumn("First Seen", format="YYYY-MM-DD HH:mm"),
                    "sources": st.column_config.ListColumn("Sources"),
                },
            )
        else:
            st.info("未找到实体数据。")

    with tab_events:
        col_evt_search, _ = st.columns([3, 1])
        with col_evt_search:
            event_search = st.text_input("🔍 Search Events", placeholder="e.g. ETF, Regulation...")
        events_data = utils.load_events()

        if events_data:
            df_evt = pd.DataFrame.from_dict(events_data, orient="index")
            df_evt["abstract"] = df_evt.index

            cols = ["abstract", "event_summary", "entities", "sources", "first_seen"]
            existing_cols = [c for c in cols if c in df_evt.columns]
            df_evt = df_evt[existing_cols]
            if "sources" in df_evt.columns:
                df_evt["sources"] = df_evt["sources"].apply(normalize_mixed)

            if event_search:
                mask = df_evt["abstract"].str.contains(event_search, case=False, na=False) | df_evt[
                    "event_summary"
                ].str.contains(event_search, case=False, na=False)
                df_evt = df_evt[mask]

            st.dataframe(
                df_evt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "abstract": st.column_config.TextColumn("Event Abstract", width="medium"),
                    "event_summary": st.column_config.TextColumn("Summary", width="large"),
                    "entities": st.column_config.ListColumn("Involved Entities"),
                    "first_seen": st.column_config.DatetimeColumn("Detected At", format="YYYY-MM-DD"),
                },
            )
        else:
            st.info("未找到事件数据。")

    with tab_news:
        c_file, c_view = st.columns([1, 3])

        with c_file:
            st.subheader("📁 Select File")
            files = utils.get_raw_news_files()
            if files:
                files = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
                selected_file = st.radio(
                    "Available Files", files, format_func=lambda x: x.name, label_visibility="collapsed"
                )
            else:
                st.warning("未找到文件。")
                selected_file = None

        with c_view:
            if selected_file:
                st.subheader(f"📄 Content: {selected_file.name}")
                news_items = utils.load_raw_news_file(selected_file)

                if news_items:
                    items_per_page = 10
                    total_pages = max(1, (len(news_items) + items_per_page - 1) // items_per_page)

                    if "news_page" not in st.session_state:
                        st.session_state.news_page = 1

                    col_pg1, col_pg2, col_pg3 = st.columns([1, 2, 1])
                    with col_pg1:
                        if st.button("Previous", disabled=st.session_state.news_page <= 1):
                            st.session_state.news_page -= 1
                            st.rerun()
                    with col_pg2:
                        st.write(
                            f"Page {st.session_state.news_page} of {total_pages} (Total: {len(news_items)})"
                        )
                    with col_pg3:
                        if st.button("Next", disabled=st.session_state.news_page >= total_pages):
                            st.session_state.news_page += 1
                            st.rerun()

                    start_idx = (st.session_state.news_page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    page_items = news_items[start_idx:end_idx]

                    for item in page_items:
                        title = item.get("title", "No Title")
                        date = item.get("datetime") or item.get("formatted_time") or "Unknown Date"
                        source = item.get("source", "Unknown Source")
                        content = item.get("content", "")

                        with st.expander(f"**{title}** | {source} | {date}"):
                            st.markdown(f"**Content:**\n{content}")
                            st.json(item, expanded=False)
                else:
                    st.info("文件为空。")

    with tab_tmp:
        st.subheader("🗃️ Extracted Events Snapshots (tmp)")
        tmp_dir = PROJECT_ROOT / "data" / "tmp"
        files = sorted(tmp_dir.glob("extracted_events_*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)

        if not files:
            st.info("未找到提取的快照文件。")
        else:
            data = []
            for f in files:
                try:
                    count = sum(1 for _ in f.open("r", encoding="utf-8"))
                except Exception:
                    count = 0
                data.append({"file": f.name, "rows": count, "path": str(f)})
            df_snap = pd.DataFrame(data)
            st.dataframe(df_snap, hide_index=True, use_container_width=True)

            selected = st.selectbox("选择要删除的文件（仅删除 tmp 快照）", [""] + [f.name for f in files])
            if selected and st.button("🗑️ 删除所选快照", type="primary"):
                try:
                    target = tmp_dir / selected
                    if target.exists():
                        target.unlink()
                        st.success(f"已删除 {selected}")
                        st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")

            st.divider()
            preview_file = st.selectbox("选择要预览的快照文件", [""] + [f.name for f in files], index=0)
            if preview_file:
                target = tmp_dir / preview_file
                try:
                    rows = []
                    with open(target, "r", encoding="utf-8") as f:
                        for idx, line in enumerate(f):
                            if idx >= 50:
                                break
                            try:
                                obj = json.loads(line)
                                rows.append(
                                    {
                                        "abstract": obj.get("abstract") or obj.get("event_summary") or "",
                                        "event_summary": obj.get("event_summary", ""),
                                        "entities": normalize_mixed(obj.get("entities")),
                                        "source": obj.get("source", ""),
                                        "published_at": obj.get("published_at", ""),
                                        "news_id": obj.get("news_id", ""),
                                    }
                                )
                            except Exception:
                                continue
                    if rows:
                        df_preview = pd.DataFrame(rows)
                        st.write(f"预览 {preview_file} （最多 50 行）")
                        st.dataframe(df_preview, hide_index=True, use_container_width=True)
                    else:
                        st.info("文件为空或无法解析可展示字段。")
                except Exception as e:
                    st.error(f"预览失败: {e}")


