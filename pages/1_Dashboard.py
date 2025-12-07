import streamlit as st
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import time

# 添加项目根目录到 path (用于导入 src 模块)
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from src.web.config import DATA_DIR, LOGS_DIR
from src.web import utils

st.set_page_config(page_title="Dashboard - Market Lens", page_icon="📊", layout="wide")

# CSS 样式优化
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .st-emotion-cache-16idsys p {
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard")
st.markdown("Overview of your system status, data collection, and knowledge graph growth.")

# --- 数据加载 ---
with st.spinner("Loading metrics..."):
    # 1. 基础统计
    raw_news_files = utils.get_raw_news_files()
    news_count = len(raw_news_files)
    
    entities = utils.load_entities()
    entity_count = len(entities)
    
    events = utils.load_events()
    event_count = len(events)
    
    # 2. 计算最近更新时间
    last_update = "N/A"
    if LOGS_DIR.exists():
        log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            last_update = datetime.fromtimestamp(log_files[0].stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    # 3. 准备图表数据
    # 实体 Top 10
    top_entities_df = pd.DataFrame()
    if entities:
        # 假设实体结构: {"Name": {"count": 5, "last_seen": ...}}
        # 如果没有 count 字段，默认设为 1
        data = []
        for name, info in entities.items():
            count = info.get("count", 1) if isinstance(info, dict) else 1
            source = info.get("sources", ["unknown"])[0] if isinstance(info, dict) and info.get("sources") else "unknown"
            data.append({"Entity": name, "Mentions": count, "Source": source})
        
        df_all = pd.DataFrame(data)
        if not df_all.empty:
            top_entities_df = df_all.sort_values("Mentions", ascending=False).head(10)

# --- 核心指标卡片 ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📰 Raw News Files", news_count, delta="Total Collected", help="Number of raw news files in storage")
with col2:
    st.metric("🧠 Entities Tracked", entity_count, delta="Knowledge Nodes", help="Total unique entities in Knowledge Graph")
with col3:
    st.metric("🔗 Events Extracted", event_count, delta="Relationships", help="Total unique events extracted")
with col4:
    st.metric("🕒 Last Activity", last_update, help="Time of last system log update")

st.markdown("---")

# --- 图表区域 ---
col_chart1, col_chart2 = st.columns([2, 1])

with col_chart1:
    st.subheader("🏆 Top Mentioned Entities")
    if not top_entities_df.empty:
        st.bar_chart(top_entities_df.set_index("Entity")["Mentions"], color="#4e79a7")
    else:
        st.info("No entity data available for visualization.")

with col_chart2:
    st.subheader("📡 Data Sources")
    if entities and not top_entities_df.empty:
        # 简单的源分布
        source_counts = df_all["Source"].value_counts().head(5)
        st.write("Distribution of entities by primary source:")
        st.dataframe(source_counts, use_container_width=True)
    else:
        st.info("No source data available.")

st.markdown("---")

# --- 系统活动日志 & 快捷入口 ---
c_log, c_action = st.columns([2, 1])

with c_log:
    st.subheader("📋 Recent System Logs")
    
    log_content = []
    try:
        log_target = LOGS_DIR / "agent1.log"
        if not log_target.exists() and LOGS_DIR.exists():
             # Fallback to latest
             log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
             if log_files: log_target = log_files[0]
             
        if log_target.exists():
            with open(log_target, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 反转显示，最新的在最上面
                for line in reversed(lines[-50:]):
                    if "ERROR" in line:
                        icon = "🔴"
                    elif "WARNING" in line:
                        icon = "qh"
                    elif "SUCCESS" in line or "✅" in line:
                        icon = "🟢"
                    else:
                        icon = "ℹ️"
                    log_content.append(f"{icon} {line.strip()}")
    except Exception as e:
        log_content = [f"Error reading logs: {e}"]

    # 使用 scrollable container
    with st.container(height=300):
        if log_content:
            for line in log_content:
                st.text(line)
        else:
            st.text("No logs found.")

with c_action:
    st.subheader("🚀 Quick Actions")
    with st.container(border=True):
        st.markdown("**Pipeline Operations**")
        if st.button("Go to Pipeline Builder", use_container_width=True):
            st.switch_page("pages/2_Pipeline_Builder.py")
            
        st.markdown("**Data Management**")
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            if st.button("Inspect Data", use_container_width=True):
                st.switch_page("pages/3_Data_Inspector.py")
        with c_a2:
            if st.button("View Graph", use_container_width=True):
                st.switch_page("pages/4_Knowledge_Graph.py")
                
        st.divider()
        st.caption("System Status: 🟢 Online")
