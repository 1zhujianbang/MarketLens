from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from src.web import utils
from src.web.config import DATA_DIR, LOGS_DIR
from src.web.framework.user_context import render_user_context_controls


def render() -> None:
    render_user_context_controls()
    kg_file = DATA_DIR / "knowledge_graph.json"

    @st.cache_data(ttl=60)
    def load_kg_counts():
        """从 knowledge_graph.json 统计实体出现次数（基于 edges 的 from 字段）。"""
        counts = {}
        if kg_file.exists():
            try:
                with open(kg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                edges = data.get("edges", [])
                for edge in edges:
                    src = edge.get("from")
                    if src:
                        counts[src] = counts.get(src, 0) + 1
                # 如果 edges 为空，尝试从 entities 节点补充一次计数
                if not counts and isinstance(data.get("entities"), dict):
                    for name in data["entities"].keys():
                        counts[name] = 1
            except Exception:
                pass
        return counts

    with st.spinner("Loading metrics..."):
        raw_news_files = utils.get_raw_news_files()
        news_count = len(raw_news_files)

        entities = utils.load_entities()
        entity_count = len(entities)
        kg_counts = load_kg_counts()

        events = utils.load_events()
        event_count = len(events)

        # 研究向：最近24h新增（展示/审查默认时间窗）
        def _parse_iso(dt_str: str):
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            except Exception:
                return None

        def _within_last_24h(dt_str: str) -> bool:
            dt = _parse_iso(dt_str)
            if not dt:
                return False
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt >= (datetime.now(timezone.utc) - timedelta(hours=24))

        recent_events_24h = 0
        for _, info in (events or {}).items():
            if isinstance(info, dict):
                ts = info.get("published_at") or info.get("first_seen") or ""
                if _within_last_24h(str(ts)):
                    recent_events_24h += 1

        recent_entities_24h = 0
        for _, info in (entities or {}).items():
            if isinstance(info, dict):
                ts = info.get("first_seen") or ""
                if _within_last_24h(str(ts)):
                    recent_entities_24h += 1

        last_update = "N/A"
        if LOGS_DIR.exists():
            log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if log_files:
                last_update = datetime.fromtimestamp(log_files[0].stat().st_mtime).strftime("%Y-%m-%d %H:%M")

        top_entities_df = pd.DataFrame()
        df_all = pd.DataFrame()
        if entities:
            data = []
            for name, info in entities.items():
                name = str(name)
                if isinstance(info, dict):
                    count = info.get("count", kg_counts.get(name, 1))
                    src_raw = info.get("sources", [])
                else:
                    count = kg_counts.get(name, 1)
                    src_raw = []

                try:
                    count = int(count)
                except Exception:
                    count = 0

                source = "unknown"
                if src_raw:
                    first = src_raw[0]
                    if isinstance(first, dict):
                        source = first.get("name") or first.get("id") or first.get("url") or "unknown"
                    else:
                        source = str(first)

                data.append({"Entity": name, "Mentions": count, "Source": source})

            df_all = pd.DataFrame(data)
            if not df_all.empty:
                df_all["Mentions"] = pd.to_numeric(df_all["Mentions"], errors="coerce").fillna(0).astype(int)
                df_all["Entity"] = df_all["Entity"].astype(str)
                if df_all["Mentions"].sum() > 0:
                    top_entities_df = df_all.sort_values("Mentions", ascending=False).head(10)

    st.markdown("### 📊 核心指标")
    metric_cols = st.columns(4)

    with metric_cols[0]:
        st.metric(
            "📰 新闻文件",
            f"{news_count}",
            delta=f"+{len([f for f in raw_news_files if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days < 1])} 今日",
            help="存储的原始新闻文件总数",
        )
    with metric_cols[1]:
        st.metric(
            "🧠 实体数量",
            f"{entity_count}",
            delta=f"{len([e for e in entities.values() if isinstance(e, dict) and (datetime.now().date() - datetime.fromisoformat(e.get('first_seen', '2024-01-01')).date()).days < 7])} 新增",
            help="知识图谱中的唯一实体节点",
        )
    with metric_cols[2]:
        st.metric(
            "🔗 事件数量",
            f"{event_count}",
            delta=f"{len([e for e in events.values() if isinstance(e, dict) and (datetime.now().date() - datetime.fromisoformat(e.get('first_seen', '2024-01-01')).date()).days < 7])} 新增",
            help="提取的事件关系总数",
        )
    with metric_cols[3]:
        st.metric("🆕 最近24h新增", f"事件 {recent_events_24h} / 实体 {recent_entities_24h}", help="展示/审查默认时间窗：最近24h（按发布时间/发现时间）")

    st.markdown("---")
    st.markdown("### 🔍 数据洞察")

    chart_col1, chart_col2 = st.columns([3, 2])
    with chart_col1:
        with st.container(border=True):
            st.subheader("🏆 热门实体排名")
            if not top_entities_df.empty:
                st.bar_chart(top_entities_df.set_index("Entity")["Mentions"], color="#667eea", use_container_width=True)
                st.markdown("**🏅 排名详情:**")
                for i, (_, row) in enumerate(top_entities_df.head(3).iterrows()):
                    medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "🏅"
                    st.markdown(f"{medal} **{row['Entity']}** - {row['Mentions']} 次提及")
            else:
                st.info("暂无实体数据可供可视化")

    with chart_col2:
        with st.container(border=True):
            st.subheader("📡 数据来源分布")
            if (not df_all.empty) and (not top_entities_df.empty):
                source_counts = df_all["Source"].value_counts().head(6)
                pie_data = pd.DataFrame({"Source": source_counts.index, "Count": source_counts.values})
                st.bar_chart(pie_data.set_index("Source")["Count"], color="#667eea", use_container_width=True)
                st.markdown("**📊 详细统计:**")
                for source, count in source_counts.items():
                    percentage = (count / len(df_all)) * 100
                    st.markdown(f"• **{source}**: {count} 条 ({percentage:.1f}%)")
            else:
                st.info("暂无数据来源信息")

    st.markdown("---")
    c_log, c_action = st.columns([2, 1])

    with c_log:
        st.subheader("📋 系统活动日志")
        log_content = []
        try:
            log_target = LOGS_DIR / "agent1.log"
            if (not log_target.exists()) and LOGS_DIR.exists():
                log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
                if log_files:
                    log_target = log_files[0]

            if log_target.exists():
                with open(log_target, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                for line in reversed(lines[-20:]):
                    if "ERROR" in line:
                        icon, level = "🔴", "ERROR"
                    elif "WARNING" in line:
                        icon, level = "🟡", "WARNING"
                    elif "SUCCESS" in line or "✅" in line:
                        icon, level = "🟢", "SUCCESS"
                    else:
                        icon, level = "🔵", "INFO"

                    timestamp = line.split("[")[1].split("]")[0] if "[" in line else ""
                    message = line.split("]", 2)[-1].strip() if "]" in line else line.strip()
                    log_content.append(f"{icon} **{level}** {timestamp} {message}")
        except Exception as e:
            log_content = [f"❌ 读取日志失败: {e}"]

        if log_content:
            st.text_area("Recent Logs", value="\n".join(log_content), height=300, label_visibility="collapsed")
        else:
            st.info("暂无系统日志")

    with c_action:
        st.subheader("🚀 快捷操作")
        with st.container(border=True):
            st.markdown("**🔧 工作流管理**")

            if st.button("🔧 构建Pipeline", use_container_width=True, key="dashboard_pipeline_button"):
                st.switch_page("pages/2_Pipeline_Builder.py")
            if st.button("🕵️ 检查数据", use_container_width=True, key="dashboard_data_button"):
                st.switch_page("pages/3_Data_Inspector.py")
            if st.button("🕸️ 查看图谱", use_container_width=True, key="dashboard_graph_button"):
                st.switch_page("pages/4_Knowledge_Graph.py")
            if st.button("⚙️ 系统设置", use_container_width=True, key="dashboard_settings_button"):
                st.switch_page("pages/5_System_Settings.py")

            st.divider()
            st.success("系统运行正常")
            st.caption("建议流程：先跑“增量更新”→ Data Inspector 审查最近24h新增 → KG 生成/刷新 PyVis 查看宏观结构。")


