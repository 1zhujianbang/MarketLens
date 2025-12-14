from __future__ import annotations

"""Generated from `pages/4_Knowledge_Graph.py`.

This module contains the page implementation as a `render()` function.
The wrapper in `pages/` is responsible for `init_page()`.
"""

import streamlit as st
import json
import networkx as nx
import streamlit.components.v1 as components
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
import altair as alt
import pandas as pd

from src.web import utils
from src.web.config import DATA_DIR
from src.web.framework.user_context import can_write, get_user_context, render_user_context_controls
from src.web.services.run_store import cache_dir
import hashlib




def render() -> None:
    render_user_context_controls()
    # --- 数据加载 ---
    kg_file = DATA_DIR / "knowledge_graph.json"
    kg_vis_file = DATA_DIR / "kg_visual.json"
    kg_timeline_file = DATA_DIR / "kg_visual_timeline.json"
    with st.spinner("Loading graph data..."):
        entities = utils.load_entities()
        events = utils.load_events()

        kg_data = {}
        if kg_file.exists():
            try:
                kg_data = json.loads(kg_file.read_text(encoding="utf-8"))
            except Exception as e:
                st.warning(f"知识图谱文件解析失败，已回退：{e}")
                kg_data = {}

        kg_vis_data = {}
        if kg_vis_file.exists():
            try:
                kg_vis_data = json.loads(kg_vis_file.read_text(encoding="utf-8"))
            except Exception as e:
                st.warning(f"快照 kg_visual.json 解析失败，已回退原始图谱：{e}")
                kg_vis_data = {}
        else:
            st.info("未找到 kg_visual.json，将使用原始知识图谱数据。")

        kg_timeline_data = []
        if kg_timeline_file.exists():
            try:
                kg_timeline_data = json.loads(kg_timeline_file.read_text(encoding="utf-8"))
            except Exception as e:
                st.warning(f"时间线快照 kg_visual_timeline.json 解析失败，已回退原始事件：{e}")
                kg_timeline_data = []
        else:
            st.info("未找到 kg_visual_timeline.json，将使用原始事件数据。")

    def parse_dt(val: str):
        if not val:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return None

    def within_last_hours(val: str, hours: int) -> bool:
        dt = parse_dt(val)
        if not dt:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= (datetime.now(timezone.utc) - timedelta(hours=hours))

    # --- 侧边栏控制 ---
    with st.sidebar:
        mode = st.radio("数据源", ["事件-实体映射 (EA)", "压缩图谱 (KG)"], index=0)
        display_window = st.radio("展示时间窗（仅影响展示/审查，不影响抓取）", ["最近24h", "最近7d", "全部"], index=0)
        window_hours = 24 if display_window == "最近24h" else (24 * 7 if display_window == "最近7d" else 0)
        seed_strategy = st.selectbox("子图种子策略（无聚焦实体时生效）", ["高关联实体（默认）", "最近事件"], index=0)
        recent_event_limit = st.slider("最近事件数（种子=最近事件）", 10, 300, 80, 10)
        all_entities = list(entities.keys()) if mode == "事件-实体映射 (EA)" else list((kg_data.get("entities") or {}).keys())
        placeholder_label = "(All / Top Nodes - EA)" if mode == "事件-实体映射 (EA)" else "(All / Top Nodes - KG)"
        # 支持从 Data Inspector 跳转聚焦实体
        focus_from_di = st.session_state.pop("kg_focus_entity", None) if "kg_focus_entity" in st.session_state else None
        options = [placeholder_label] + sorted(all_entities)
        default_index = 0
        if focus_from_di and focus_from_di in options:
            default_index = options.index(focus_from_di)

        search_query = st.selectbox(
            "Focus on Entity",
            options=options,
            index=default_index,
            help="Select an entity to view its specific connections."
        )
        hop_depth = st.slider("Hop Depth (聚焦模式)", 1, 4, 1, help="从选定实体出发，最多拓展的边数（实体-事件-实体-...）。")
        # 2. 显示设置
        max_nodes = st.slider("Max Nodes（建议≤500，否则PyVis可能很慢）", 10, 3000, 300, help="Limit total nodes for better performance")
        physics_enabled = st.checkbox("Enable Physics", value=True)
        enable_pyvis = st.checkbox("启用PyVis复杂图谱（可能较慢）", value=True)
        auto_timeline = st.checkbox("显示聚焦实体时间线", value=True, help="在下方时间线视图中自动使用当前聚焦实体（KG/EA 均可）")
        # 时间线参数
        entity_opts = sorted(list(entities.keys()))
        default_tl = "(请选择)"
        if auto_timeline and search_query not in ["(All / Top Nodes - EA)", "(All / Top Nodes - KG)", "(All / Top Nodes)"]:
            default_tl = search_query
        # 时间线实体直接复用当前聚焦实体（非 All/Top），否则为未选择
        timeline_entity = search_query if search_query not in [placeholder_label, "(All / Top Nodes)"] else "(请选择)"
        limit_events = st.slider("最多显示事件数", 10, 500, 200, 10)
        st.divider()
        if mode == "事件-实体映射 (EA)":
            st.caption(f"Total Entities: {len(entities)}")
            st.caption(f"Total Events: {len(events)}")
        else:
            if kg_vis_data:
                st.caption(f"KG (vis) Nodes: {len(kg_vis_data.get('nodes') or [])}")
                st.caption(f"KG (vis) Edges: {len(kg_vis_data.get('edges') or [])}")
            else:
                st.caption(f"KG Entities: {len(kg_data.get('entities') or {})}")
                st.caption(f"KG Events: {len(kg_data.get('events') or {})}")

    if mode == "事件-实体映射 (EA)":
        if not entities or not events:
            st.warning("知识图谱为空。请运行流水线来填充数据。")
            st.stop()
    else:
        # KG 模式优先用可视化快照
        if kg_vis_data:
            pass
        elif not kg_data or not kg_data.get("entities") or not kg_data.get("events"):
            st.warning("知识图谱(KG)为空。")
            st.stop()

    edge_list = []
    event_ids = set()
    if mode == "事件-实体映射 (EA)":
        event_ids = {f"EVT:{k}" for k in events.keys()}
        for evt_abstract, evt_data in events.items():
            # 展示时间窗过滤（优先用 published_at，否则 first_seen）
            if window_hours:
                ts = str(evt_data.get("published_at") or evt_data.get("first_seen") or "")
                if not within_last_hours(ts, window_hours):
                    continue
            evt_id = f"EVT:{evt_abstract}"  #以此区分
            evt_summary = evt_data.get('event_summary', evt_abstract)
            for ent in evt_data.get('entities', []):
                if ent in entities:
                    edge_list.append((evt_id, ent, {"title": evt_summary}))
    else:
        # KG 模式：若需要时间窗过滤，优先使用 timeline 快照构建子图（否则无法按时间过滤）
        if window_hours and kg_timeline_data:
            for evt in kg_timeline_data:
                t = parse_dt(evt.get("time"))
                if not t:
                    continue
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                if t < (datetime.now(timezone.utc) - timedelta(hours=window_hours)):
                    continue
                abstract = evt.get("abstract", "")
                evt_id = f"EVT:{abstract}"
                event_ids.add(evt_id)
                title = evt.get("event_summary", "") or abstract
                for ent in evt.get("entities", []) or []:
                    edge_list.append((evt_id, ent, {"title": title}))
        elif window_hours and (not kg_timeline_data):
            st.info("提示：当前选择了时间窗过滤，但未找到 `kg_visual_timeline.json`。KG模式将回退为不按时间过滤的展示。")
        elif kg_vis_data:
            vis_nodes = kg_vis_data.get("nodes", [])
            vis_edges = kg_vis_data.get("edges", [])
            for n in vis_nodes:
                if n.get("type") == "event":
                    event_ids.add(n.get("id"))
            for e in vis_edges:
                u, v = e.get("from"), e.get("to")
                edge_list.append((u, v, {"title": e.get("title", "")}))
        else:
            kg_entities = kg_data.get("entities", {})
            kg_events = kg_data.get("events", {})
            kg_edges = kg_data.get("edges", [])
            event_ids = set(kg_events.keys())
            for e in kg_edges:
                u = e.get("from")
                v = e.get("to")
                if not u or not v:
                    continue
                title = ""
                evt_key = v[4:] if isinstance(v, str) and v.startswith("EVT:") else v
                if evt_key in kg_events:
                    title = kg_events[evt_key].get("event_summary", "") or kg_events[evt_key].get("abstract", "")
                edge_list.append((u, v, {"title": title}))

    # --- 过滤逻辑 ---
    target_nodes = set()
    from collections import defaultdict, deque
    adj = defaultdict(set)
    for u, v, _ in edge_list:
        adj[u].add(v)
        adj[v].add(u)

    # 节点类型判断
    def is_event_node(node: str) -> bool:
        if isinstance(node, str) and node.startswith("EVT:"):
            return True
        return node in event_ids

    if search_query != "(All / Top Nodes)" and search_query != "(All / Top Nodes - EA)" and search_query != "(All / Top Nodes - KG)":
        # 1. 聚焦模式：从选定实体出发，按 hop_depth 做 BFS（实体-事件交替）
        target_nodes.add(search_query)
        frontier = {search_query}
        for _ in range(hop_depth):
            next_frontier = set()
            for node in frontier:
                next_frontier |= adj.get(node, set())
            next_frontier -= target_nodes
            target_nodes |= next_frontier
            frontier = next_frontier
    else:
        # 2. 全局模式：按度数（连接数）取 Top N 实体 + 相关事件
        if seed_strategy == "最近事件" and window_hours:
            # 以最近事件为种子：选择最近N个事件及其相关实体
            seed_events = []
            if mode == "事件-实体映射 (EA)":
                for abstract, info in (events or {}).items():
                    if isinstance(info, dict):
                        ts = str(info.get("published_at") or info.get("first_seen") or "")
                        t = parse_dt(ts)
                        if t and (t.tzinfo is None):
                            t = t.replace(tzinfo=timezone.utc)
                        if t and within_last_hours(ts, window_hours):
                            seed_events.append((t, f"EVT:{abstract}", info.get("entities") or []))
            elif kg_timeline_data:
                for evt in kg_timeline_data:
                    t = parse_dt(evt.get("time"))
                    if not t:
                        continue
                    if t.tzinfo is None:
                        t = t.replace(tzinfo=timezone.utc)
                    if t >= (datetime.now(timezone.utc) - timedelta(hours=window_hours)):
                        abstract = evt.get("abstract", "")
                        seed_events.append((t, f"EVT:{abstract}", evt.get("entities") or []))

            seed_events = sorted(seed_events, key=lambda x: x[0], reverse=True)[:recent_event_limit]
            target_nodes = set()
            for _, evt_id, ents in seed_events:
                target_nodes.add(evt_id)
                for e in ents:
                    target_nodes.add(e)
            # 再做一次 cap，避免极端爆炸
            if len(target_nodes) > max_nodes:
                target_nodes = set(list(target_nodes)[:max_nodes])
        else:
            # 默认：高关联实体（度数Top）
            temp_G = nx.Graph()
            temp_G.add_edges_from([(u, v) for u, v, _ in edge_list])
            degrees = dict(temp_G.degree())
            top_nodes = sorted(degrees, key=degrees.get, reverse=True)[:max_nodes]
            target_nodes = set(top_nodes)

    # --- 构建最终可视化图 ---
    visual_G = nx.Graph()

    count = 0
    for u, v, attr in edge_list:
        if u in target_nodes and v in target_nodes:
            # 添加节点（如果未添加）
            if u not in visual_G:
                # 判断类型
                if is_event_node(u):
                    label = u[4:20] + "..." if isinstance(u, str) and u.startswith("EVT:") else str(u)[:20] + "..."
                    visual_G.add_node(u, label=label, title=str(u)[4:] if isinstance(u, str) and u.startswith("EVT:") else str(u), group='Event', color='#ff7f0e', size=15)
                else:
                    visual_G.add_node(u, label=str(u), group='Entity', color='#1f77b4', size=25)
        
            if v not in visual_G:
                if is_event_node(v):
                    label = v[4:20] + "..." if isinstance(v, str) and v.startswith("EVT:") else str(v)[:20] + "..."
                    visual_G.add_node(v, label=label, title=str(v)[4:] if isinstance(v, str) and v.startswith("EVT:") else str(v), group='Event', color='#ff7f0e', size=15)
                else:
                    visual_G.add_node(v, label=str(v), group='Entity', color='#1f77b4', size=25)
        
            visual_G.add_edge(u, v, title=attr.get("title"))
            count += 1
        
    # 预计算时间线数据（用于 Timeline / Timeline Details）
    rows: list[dict] = []
    co_counter: dict[str, int] = {}
    if timeline_entity and timeline_entity != "(请选择)":
        # EA 模式优先使用 events.json；KG 模式在有 timeline 快照时使用 kg_visual_timeline.json
        use_timeline_snapshot = (mode == "压缩图谱 (KG)") and bool(kg_timeline_data)

        def _accept_time(t: datetime | None) -> bool:
            if not t:
                return False
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if not window_hours:
                return True
            return t >= (datetime.now(timezone.utc) - timedelta(hours=window_hours))

        if use_timeline_snapshot:
            for evt in kg_timeline_data:
                ents = evt.get("entities", []) or []
                if timeline_entity not in ents:
                    continue
                t = parse_dt(evt.get("time"))
                if not _accept_time(t):
                    continue
                co_entities = [e for e in ents if e != timeline_entity]
                for ce in co_entities:
                    co_counter[ce] = co_counter.get(ce, 0) + 1
                rows.append(
                    {
                        "abstract": evt.get("abstract", ""),
                        "event_summary": evt.get("event_summary", ""),
                        "time_dt": t,
                        "co_entities": ", ".join(co_entities[:5]),
                        "co_entities_raw": co_entities,
                    }
                )
        else:
            for abstract, evt in (events or {}).items():
                ents = evt.get("entities", []) or []
                if timeline_entity not in ents:
                    continue
                t = parse_dt(evt.get("published_at") or evt.get("first_seen"))
                if not _accept_time(t):
                    continue
                co_entities = [e for e in ents if e != timeline_entity]
                for ce in co_entities:
                    co_counter[ce] = co_counter.get(ce, 0) + 1
                rows.append(
                    {
                        "abstract": abstract,
                        "event_summary": evt.get("event_summary", "") or abstract,
                        "time_dt": t,
                        "co_entities": ", ".join(co_entities[:5]),
                        "co_entities_raw": co_entities,
                    }
                )

        # 取“最近 N 条”，但保持时间升序（便于时间线/图表）
        rows = [r for r in rows if r.get("time_dt")]
        rows_sorted_desc = sorted(rows, key=lambda x: x["time_dt"], reverse=True)
        rows_top = rows_sorted_desc[:limit_events]
        rows = sorted(rows_top, key=lambda x: x["time_dt"])


    # --- 社区/主题摘要（轻量） ---
    community_rows = []
    try:
        if visual_G.number_of_nodes() <= 800 and visual_G.number_of_edges() > 0:
            from networkx.algorithms.community import greedy_modularity_communities

            comms = list(greedy_modularity_communities(visual_G))
            deg = dict(visual_G.degree())
            for i, cset in enumerate(comms[:12]):
                nodes = list(cset)
                top = sorted(nodes, key=lambda n: deg.get(n, 0), reverse=True)[:6]
                community_rows.append(
                    {
                        "community": i + 1,
                        "size": len(nodes),
                        "top_nodes": ", ".join([str(t) for t in top]),
                    }
                )
    except Exception:
        community_rows = []

    KG, EntityDetails, Timeline, Community, TimelineDetails = st.tabs(["KG", "Entity Details", "Timeline", "社区/主题", "Timeline Details"])

    with KG:
        st.subheader("🕸️ 图谱视图（PyVis）")
        st.caption("为避免每次交互都重算导致加载很慢：只有点击“生成/刷新图谱”才会生成PyVis；否则展示轻量信息。")

        with st.expander("导出（当前子图）", expanded=False):
            try:
                # 导出当前子图（节点/边）为 JSON，便于学术/商业场景进一步处理
                nodes_payload = list(visual_G.nodes(data=True))
                edges_payload = list(visual_G.edges(data=True))
                export_obj = {"nodes": nodes_payload, "edges": edges_payload, "meta": {"window": display_window, "mode": mode}}
                st.download_button(
                    "下载当前子图 JSON",
                    data=json.dumps(export_obj, ensure_ascii=False, indent=2),
                    file_name=f"subgraph_{mode}_{display_window}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"导出失败：{e}")

            # 提供原始文件导出入口
            if not can_write():
                st.info("viewer 角色默认不提供原始文件下载（权限占位）。")
            else:
                for p in [kg_file, kg_vis_file, kg_timeline_file]:
                    if p.exists():
                        st.download_button(
                            f"下载原始文件：{p.name}",
                            data=p.read_bytes(),
                            file_name=p.name,
                            use_container_width=True,
                        )

        # 参数签名用于缓存
        cache_key = f"{mode}|{display_window}|{search_query}|{hop_depth}|{max_nodes}|{physics_enabled}|{len(edge_list)}"
        if "kg_pyvis_cache" not in st.session_state:
            st.session_state.kg_pyvis_cache = OrderedDict()
        if not isinstance(st.session_state.kg_pyvis_cache, OrderedDict):
            st.session_state.kg_pyvis_cache = OrderedDict(st.session_state.kg_pyvis_cache)

        project_id = get_user_context().project_id
        use_disk_cache = st.checkbox(
            "跨会话磁盘缓存（更快）",
            value=True,
            help="把生成的 PyVis HTML 缓存到 data/projects/<project_id>/cache/pyvis/，下次秒开。",
        )
        disk_dir = cache_dir(project_id) / "pyvis"
        disk_dir.mkdir(parents=True, exist_ok=True)
        key_hash = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16]
        disk_path = disk_dir / f"pyvis_{key_hash}.html"

        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            gen = st.button("生成/刷新图谱", type="primary", use_container_width=True, disabled=(not enable_pyvis))
            if st.button("清理PyVis缓存", use_container_width=True):
                st.session_state.kg_pyvis_cache = OrderedDict()
                st.success("已清理缓存")
        with col_info:
            st.info(f"当前子图：Nodes={visual_G.number_of_nodes()} / Edges={visual_G.number_of_edges()}（{display_window}）")

        if not enable_pyvis:
            st.warning("已关闭PyVis复杂图谱。你仍可在下方查看实体详情与时间线。")
        else:
            html_string = st.session_state.kg_pyvis_cache.get(cache_key)
            if (html_string is None) and use_disk_cache and disk_path.exists() and (not gen):
                try:
                    html_string = disk_path.read_text(encoding="utf-8")
                    st.session_state.kg_pyvis_cache[cache_key] = html_string
                    st.session_state.kg_pyvis_cache.move_to_end(cache_key)
                except Exception:
                    html_string = None
            if gen or (html_string is None):
                try:
                    from pyvis.network import Network
                    import tempfile

                    with st.spinner("Generating PyVis graph (may take time)..."):
                        net = Network(height="700px", width="100%", bgcolor="#ffffff", font_color="black")
                        net.from_nx(visual_G)
                        if physics_enabled:
                            net.force_atlas_2based()
                        else:
                            net.toggle_physics(False)

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                            net.save_graph(tmp.name)
                            with open(tmp.name, "r", encoding="utf-8") as f:
                                html_string = f.read()

                    # 缓存并限制大小，避免 session_state 无限增长
                    st.session_state.kg_pyvis_cache[cache_key] = html_string
                    st.session_state.kg_pyvis_cache.move_to_end(cache_key)
                    while len(st.session_state.kg_pyvis_cache) > 5:
                        st.session_state.kg_pyvis_cache.popitem(last=False)
                    if use_disk_cache and html_string:
                        try:
                            disk_path.write_text(html_string, encoding="utf-8")
                        except Exception:
                            pass
                except ImportError:
                    st.error("PyVis not installed. Run `pip install pyvis` to view the graph.")
                    html_string = None

            if html_string:
                components.html(html_string, height=710, scrolling=False)

    with Community:
        st.subheader("🧩 社区/主题摘要（轻量）")
        st.caption("对当前子图做社区划分（节点数过大时自动跳过）。后续可扩展为“主题标签/摘要/推送信号”。")
        if community_rows:
            st.dataframe(pd.DataFrame(community_rows), hide_index=True, use_container_width=True)
        else:
            st.info("当前子图规模较大或缺少边，已跳过社区划分。")

    # --- 节点详情面板 ---
    with EntityDetails:
        if search_query != "(All / Top Nodes)":
            st.divider()
            st.subheader(f"📘 Entity Details: {search_query}")
        
            ent_info = entities.get(search_query, {})
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Sources:**", ", ".join(ent_info.get("sources", [])))
                st.write("**First Seen:**", ent_info.get("first_seen", "N/A"))
            with c2:
                st.write("**Aliases/Forms:**", ", ".join(ent_info.get("original_forms", [])))
            
            st.write("**Related Events:**")
            # 查找关联事件摘要
            related_evts = []
            for evt_abstract, evt_data in events.items():
                if search_query in evt_data.get('entities', []):
                    related_evts.append(evt_data.get('event_summary') or evt_abstract)
                
            for evt in related_evts[:10]:
                st.text(f"• {evt}")
            if len(related_evts) > 10:
                st.caption(f"... and {len(related_evts)-10} more.")

    with Timeline:
        if timeline_entity and timeline_entity != "(请选择)" and rows:
            try:
                from pyvis.network import Network
                from pathlib import Path
                import tempfile

                net = Network(
                    height="750px",
                    width="100%",
                    bgcolor="#ffffff",
                    font_color="#333333",
                    directed=True,
                    notebook=False
                )

                # 使用自定义 physics 参数（关键：关闭 centralGravity，否则节点会整体向画布中心聚集）
                net.set_options("""
                {
                "physics": {
                    "enabled": true,
                    "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.0,
                    "springLength": 200,
                    "springStrength": 0.08,
                    "damping": 0.8,
                    "avoidOverlap": 1
                    },
                    "maxVelocity": 50,
                    "minVelocity": 10,
                    "solver": "forceAtlas2Based",
                    "timestep": 0.5,
                    "stabilization": {
                    "enabled": true,
                    "iterations": 200,
                    "updateInterval": 25
                    }
                },
                "nodes": {
                    "font": {
                    "size": 16,
                    "face": "arial"
                    }
                },
                "edges": {
                    "arrows": {
                    "to": {
                        "enabled": true,
                        "scaleFactor": 0.5
                    }
                    },
                    "smooth": false,
                    "color": "#999999"
                }
                }
                """)

                # 1. 先添加所有实体节点（不固定位置）
                all_entities = set()
                for r in rows:
                    for ce in r.get("co_entities_raw", [])[:8]:  # 限制一下数量防爆炸
                        all_entities.add(ce)

                for ent in all_entities:
                    net.add_node(
                        f"ent_{ent}",
                        label=ent,
                        color="#1f77b4",
                        size=20,
                        shape="dot",
                        font={"color": "white", "size": 14},
                        title=ent,
                        mass=1
                    )

                # 2. 添加事件节点：固定 x/y
                for idx, r in enumerate(rows):
                    x = idx * 230
                    ys = [0,60,-60]
                    y = ys[idx%3]
                
                    size = 30 + len(r.get("co_entities_raw", [])) * 3
                    label = r.get("event_summary", "")[:50] + "..." if len(r.get("event_summary", "")) > 50 else r.get("event_summary", "")

                    net.add_node(
                        f"evt_{idx}",
                        label=label,
                        title=r.get("event_summary", ""),
                        x=x,
                        y=y,
                        fixed={"x": True, "y": True},   # 固定事件节点位置！
                        # 关键：事件节点位置固定，但仍参与物理 => 作为“锚点”把相关实体吸附到周围
                        # 如果设为 physics=False，会导致实体节点难以围绕事件形成稳定簇
                        physics=True,
                        color="#ff7f0e",
                        size=size,
                        shape="dot",
                        font={"size": 18, "color": "white"},
                        shadow=True,
                        mass=5
                    )

                    # 添加边：实体 → 事件（箭头指向事件）
                    for ce in r.get("co_entities_raw", [])[:8]:
                        # length 越短，实体越贴近关联事件节点
                        net.add_edge(f"ent_{ce}", f"evt_{idx}", color="#aaaaaa", width=1.5, length=120)

                # 可选：加一个隐藏的“时间主线”让事件之间也有连线（更清晰）
                for i in range(len(rows)-1):
                    net.add_edge(f"evt_{i}", f"evt_{i+1}", color="#ff7f0e", width=3, dashes=True)

                # 保存并显示
                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                    net.save_graph(tmp.name)
                    html_string = Path(tmp.name).read_text(encoding="utf-8")

                st.components.v1.html(html_string, height=800, scrolling=True)

            except ImportError:
                st.warning("请先安装 pyvis：`pip install pyvis`")


    with TimelineDetails:
        st.subheader("时间线详情")
        if timeline_entity and timeline_entity != "(请选择)":
            if rows:
                df_tl = pd.DataFrame(rows)
                chart = alt.Chart(df_tl).mark_line(point=True).encode(
                    x="time_dt:T",
                    y=alt.value(0),
                    tooltip=["time_dt:T", "event_summary:N", "co_entities:N"]
                ).properties(height=120, width="container")
                st.altair_chart(chart, use_container_width=True)
                st.dataframe(df_tl[["time_dt", "event_summary", "co_entities"]], hide_index=True, use_container_width=True)
            
                if co_counter:
                    top_co = sorted(co_counter.items(), key=lambda x: x[1], reverse=True)[:10]
                    st.caption("Top 共现实体")
                    st.table({"entity": [x[0] for x in top_co], "count": [x[1] for x in top_co]})
            else:
                st.info("该实体没有可展示的带时间事件。")
        else:
            st.info("请选择一个实体查看时间线。")





