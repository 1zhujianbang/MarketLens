import streamlit as st
from datetime import datetime
import json
from pathlib import Path
import pandas as pd
from src.web.config import DATA_DIR, LOGS_DIR
from src.web import utils

def render():
    st.title("📊 Dashboard")
    
    # 状态概览
    col1, col2, col3, col4 = st.columns(4)
    
    news_count = 0
    entity_count = 0
    event_count = 0
    last_update = "N/A"
    
    try:
        # 新闻统计 (估算)
        raw_news_files = utils.get_raw_news_files()
        news_count = len(raw_news_files)
        
        # 实体统计
        entities = utils.load_entities()
        entity_count = len(entities)
                
        # 事件统计
        events = utils.load_events()
        event_count = len(events)
                
        # 最近更新
        if LOGS_DIR.exists():
             log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
             if log_files:
                 last_update = datetime.fromtimestamp(log_files[0].stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                 
    except Exception as e:
        st.error(f"Error loading stats: {e}")

    with col1:
        st.metric("Raw News Files", news_count, help="Number of raw news files collected")
    with col2:
        st.metric("Entities Tracked", entity_count, help="Total unique entities in Knowledge Graph")
    with col3:
        st.metric("Events Extracted", event_count, help="Total unique events extracted")
    with col4:
        st.metric("Last Activity", last_update)

    st.markdown("---")
    
    # 最近活动日志
    st.subheader("📋 System Activity")
    try:
        # 尝试读取最新的日志文件，如果没有 agent1.log 则找最新的
        log_target = LOGS_DIR / "agent1.log"
        
        # 如果 agent1.log 不存在，尝试找最新的 log
        if not log_target.exists() and LOGS_DIR.exists():
            log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if log_files:
                log_target = log_files[0]
        
        if log_target.exists():
            with open(log_target, "r", encoding="utf-8") as f:
                # 读取最后 20 行
                lines = f.readlines()[-20:]
                log_text = "".join(lines)
                st.caption(f"Showing logs from: {log_target.name}")
                st.code(log_text, language="text")
        else:
            st.info("No logs found.")
    except Exception as e:
        st.error(f"Error reading logs: {e}")

    # 快捷操作
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run Daily Scan (Quick Test)", use_container_width=True):
            st.switch_page("app.py") # 理想情况下应跳转或触发后台任务，这里暂时占位
            st.toast("Redirecting to Pipeline Builder...")
            # 实际逻辑需在 Pipeline Builder 中触发
