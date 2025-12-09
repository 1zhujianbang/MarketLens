import streamlit as st
import json
import networkx as nx
from pathlib import Path
import streamlit.components.v1 as components
import sys

# 添加项目根目录到 path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from src.web import utils

st.set_page_config(page_title="Knowledge Graph - Market Lens", page_icon="🕸️", layout="wide")

# --- 数据加载 ---
kg_file = Path(__file__).resolve().parent.parent / "data" / "knowledge_graph.json"
with st.spinner("Loading graph data..."):
    entities = utils.load_entities()
    events = utils.load_events()
    kg_data = {}
    if kg_file.exists():
        try:
            kg_data = json.loads(kg_file.read_text(encoding="utf-8"))
        except Exception:
            kg_data = {}

# --- 侧边栏控制 ---
with st.sidebar:
    st.header("Graph Controls")
    
    mode = st.radio("数据源", ["事件-实体映射 (EA)", "压缩图谱 (KG)"], index=0)
    all_entities = list(entities.keys()) if mode == "事件-实体映射 (EA)" else list((kg_data.get("entities") or {}).keys())
    placeholder_label = "(All / Top Nodes - EA)" if mode == "事件-实体映射 (EA)" else "(All / Top Nodes - KG)"
    search_query = st.selectbox(
        "Focus on Entity", 
        options=[placeholder_label] + sorted(all_entities),
        index=0,
        help="Select an entity to view its specific connections."
    )
    hop_depth = st.slider("Hop Depth (聚焦模式)", 1, 4, 1, help="从选定实体出发，最多拓展的边数（实体-事件-实体-...）。")
    
    st.divider()
    
    # 2. 显示设置
    max_nodes = st.slider("Max Nodes", 10, 3000, 500, help="Limit total nodes for better performance")
    physics_enabled = st.checkbox("Enable Physics", value=True)
    
    st.divider()
    if mode == "事件-实体映射 (EA)":
        st.caption(f"Total Entities: {len(entities)}")
        st.caption(f"Total Events: {len(events)}")
    else:
        st.caption(f"KG Entities: {len(kg_data.get('entities') or {})}")
        st.caption(f"KG Events: {len(kg_data.get('events') or {})}")

if mode == "事件-实体映射 (EA)":
    if not entities or not events:
        st.warning("Knowledge Graph is empty. Run the pipeline to populate data.")
        st.stop()
else:
    if not kg_data or not kg_data.get("entities") or not kg_data.get("events"):
        st.warning("Knowledge Graph (KG) is empty.")
        st.stop()

edge_list = []
event_ids = set()
if mode == "事件-实体映射 (EA)":
    event_ids = {f"EVT:{k}" for k in events.keys()}
    for evt_abstract, evt_data in events.items():
        evt_id = f"EVT:{evt_abstract}"  #以此区分
        evt_summary = evt_data.get('event_summary', evt_abstract)
        for ent in evt_data.get('entities', []):
            if ent in entities:
                edge_list.append((evt_id, ent, {"title": evt_summary}))
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
    # 简单起见，先统计实体出现频率
    # 也可以直接用 edge_list 构建临时图计算度
    temp_G = nx.Graph()
    temp_G.add_edges_from([(u, v) for u, v, _ in edge_list])
    
    # 计算度
    degrees = dict(temp_G.degree())
    # 排序
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
        
# --- PyVis 渲染 ---
try:
    from pyvis.network import Network
    import tempfile
    
    net = Network(height="700px", width="100%", bgcolor="#ffffff", font_color="black")
    net.from_nx(visual_G)
    
    if physics_enabled:
        net.force_atlas_2based()
    else:
        net.toggle_physics(False)
        
    # 保存并读取
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            html_string = f.read()
            
    components.html(html_string, height=710, scrolling=False)
    
except ImportError:
    st.error("PyVis not installed. Run `pip install pyvis` to view the graph.")
    st.info(f"Nodes: {visual_G.number_of_nodes()}, Edges: {visual_G.number_of_edges()}")

# --- 节点详情面板 ---
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
