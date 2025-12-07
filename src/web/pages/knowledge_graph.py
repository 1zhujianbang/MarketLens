import streamlit as st
import json
import networkx as nx
from pathlib import Path
import streamlit.components.v1 as components
from src.web import utils

# 注意：pyvis 可能需要单独安装，如果没有安装，这里提供简单的 NetworkX 绘图或降级处理
# 建议用户安装 pyvis: pip install pyvis

def render():
    st.title("🕸️ Knowledge Graph Visualization")
    
    entities = utils.load_entities()
    events = utils.load_events()
    
    if not entities or not events:
        st.error("Knowledge Graph data missing or empty.")
        return

    # 构建图
    G = nx.Graph()
        
    # 限制节点数量以保证性能
    max_nodes = st.slider("Max Nodes to Visualize", 10, 500, 100)
    
    # 简单的构建逻辑：Event -> Entity
    added_nodes = 0
    
    for evt_abstract, evt_data in events.items():
        if added_nodes > max_nodes:
            break
            
        # 添加事件节点
        # 截断长标题
        label = evt_abstract[:20] + "..." if len(evt_abstract) > 20 else evt_abstract
        G.add_node(evt_abstract, label=label, title=evt_data.get('event_summary'), group='Event', color='#ff7f0e')
        added_nodes += 1
        
        # 添加实体节点及边
        for ent in evt_data.get('entities', []):
            if ent not in G:
                G.add_node(ent, label=ent, group='Entity', color='#1f77b4')
                added_nodes += 1
            G.add_edge(evt_abstract, ent)
            
    st.info(f"Visualizing {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    # 尝试使用 PyVis
    try:
        from pyvis.network import Network
        import tempfile
        
        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black")
        net.from_nx(G)
        
        # 物理模拟配置
        net.force_atlas_2based()
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            net.save_graph(tmp.name)
            with open(tmp.name, "r", encoding="utf-8") as f:
                html_string = f.read()
                
        components.html(html_string, height=600, scrolling=True)
        
    except ImportError:
        st.warning("PyVis not installed. Please install it for interactive visualization: `pip install pyvis`")
        st.write("Fallback: NetworkX static plot (not implemented in this demo).")
