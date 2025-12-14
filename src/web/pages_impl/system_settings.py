from __future__ import annotations

import yaml
import streamlit as st

from src.core import get_config_manager
from src.web.config import PROJECT_ROOT
from src.web.framework.user_context import can_write, render_user_context_controls


def render() -> None:
    render_user_context_controls()
    st.title("⚙️ 系统设置")
    st.caption("编辑 Agent 并发/限速等核心参数（写入 config/agents/*.yaml）。默认按“性能/成本/质量”分组。")

    config_manager = get_config_manager()
    cfg = config_manager.load_multi_file_config()

    agent1 = cfg.get("agent1_config", {}) or {}
    agent2 = cfg.get("agent2_config", {}) or {}
    agent3 = cfg.get("agent3_config", {}) or {}

    tabs = st.tabs(["Agent1", "Agent2", "Agent3"])

    # reset helper (form widgets are keyed by label; we reset by rerun + clearing known keys)
    if st.button("🔄 重置为当前文件配置", use_container_width=True):
        st.rerun()

    with st.form("system_settings"):
        with tabs[0]:
            st.subheader("Agent1（抓取+抽取）")
            with st.expander("性能", expanded=True):
                a1_workers = st.number_input("max_workers", 1, 64, int(agent1.get("max_workers", 1)))
                a1_qps = st.number_input("rate_limit_per_sec", 0.1, 20.0, float(agent1.get("rate_limit_per_sec", 1.0)), 0.1)
            with st.expander("质量", expanded=False):
                a1_dedupe = st.number_input("dedupe_threshold", 1, 10, int(agent1.get("dedupe_threshold", 1)))

        with tabs[1]:
            st.subheader("Agent2（拓展搜索）")
            with st.expander("性能", expanded=True):
                a2_workers = st.number_input("A2 max_workers", 1, 64, int(agent2.get("max_workers", 1)))
                a2_qps = st.number_input("A2 rate_limit_per_sec", 0.1, 20.0, float(agent2.get("rate_limit_per_sec", 1.0)), 0.1)

        with tabs[2]:
            st.subheader("Agent3（知识图谱压缩）")
            with st.expander("性能", expanded=True):
                g3_e_workers = st.number_input("entity_max_workers", 1, 16, int(agent3.get("entity_max_workers", 1)))
                g3_ev_workers = st.number_input("event_max_workers", 1, 16, int(agent3.get("event_max_workers", 1)))
                g3_rate = st.number_input("rate_limit_per_sec", 0.1, 20.0, float(agent3.get("rate_limit_per_sec", 0.1)), 0.1)
            with st.expander("成本（批量/上限）", expanded=False):
                g3_ent_batch = st.number_input("entity_batch_size", 10, 500, int(agent3.get("entity_batch_size", 10)))
                g3_ev_batch = st.number_input("event_batch_size", 5, 200, int(agent3.get("event_batch_size", 5)))
                g3_ent_limit = st.number_input("entity_precluster_limit", 10, 2000, int(agent3.get("entity_precluster_limit", 10)))
                g3_ev_limit = st.number_input("event_precluster_limit", 10, 2000, int(agent3.get("event_precluster_limit", 10)))
                g3_bucket_max = st.number_input("event_bucket_max_size", 10, 1000, int(agent3.get("event_bucket_max_size", 10)))
            with st.expander("质量（相似度/摘要）", expanded=False):
                g3_ent_sim = st.number_input("entity_precluster_similarity", 0.1, 1.0, float(agent3.get("entity_precluster_similarity", 0.1)), 0.01)
                g3_ev_sim = st.number_input("event_precluster_similarity", 0.1, 1.0, float(agent3.get("event_precluster_similarity", 0.1)), 0.01)
                g3_bucket_days = st.number_input("event_bucket_days", 1, 90, int(agent3.get("event_bucket_days", 1)))
                g3_bucket_overlap = st.number_input("event_bucket_entity_overlap", 0, 10, int(agent3.get("event_bucket_entity_overlap", 0)))
                g3_max_summary = st.number_input("max_summary_chars", 50, 2000, int(agent3.get("max_summary_chars", 50)))
                g3_ev_per_entity = st.number_input("entity_evidence_per_entity", 0, 10, int(agent3.get("entity_evidence_per_entity", 0)))
                g3_ev_max_chars = st.number_input("entity_evidence_max_chars", 50, 2000, int(agent3.get("entity_evidence_max_chars", 50)))

        # 预览将写入的 YAML（保存前）
        preview_cfg = {
            "agent1_config": {"max_workers": int(a1_workers), "rate_limit_per_sec": float(a1_qps), "dedupe_threshold": int(a1_dedupe)},
            "agent2_config": {"max_workers": int(a2_workers), "rate_limit_per_sec": float(a2_qps)},
            "agent3_config": {
                "entity_batch_size": int(g3_ent_batch),
                "event_batch_size": int(g3_ev_batch),
                "event_bucket_days": int(g3_bucket_days),
                "event_bucket_entity_overlap": int(g3_bucket_overlap),
                "event_bucket_max_size": int(g3_bucket_max),
                "event_precluster_similarity": float(g3_ev_sim),
                "event_precluster_limit": int(g3_ev_limit),
                "entity_precluster_similarity": float(g3_ent_sim),
                "entity_precluster_limit": int(g3_ent_limit),
                "max_summary_chars": int(g3_max_summary),
                "entity_max_workers": int(g3_e_workers),
                "event_max_workers": int(g3_ev_workers),
                "rate_limit_per_sec": float(g3_rate),
                "entity_evidence_per_entity": int(g3_ev_per_entity),
                "entity_evidence_max_chars": int(g3_ev_max_chars),
            },
        }
        with st.expander("保存预览（将写入的 YAML）", expanded=False):
            st.code(yaml.safe_dump(preview_cfg, allow_unicode=True, sort_keys=False), language="yaml")

        submitted = st.form_submit_button("💾 保存配置", type="primary", use_container_width=True, disabled=(not can_write()))

        if submitted:
            if not can_write():
                st.error("当前角色为 viewer：禁止保存系统配置（权限占位）。")
                st.stop()
            try:
                cfg.update(preview_cfg)

                config_dir = PROJECT_ROOT / "config" / "agents"
                config_dir.mkdir(parents=True, exist_ok=True)

                agent1_file = config_dir / "agent1.yaml"
                agent2_file = config_dir / "agent2.yaml"
                agent3_file = config_dir / "agent3.yaml"

                with open(agent1_file, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg["agent1_config"], f, allow_unicode=True, sort_keys=False)
                with open(agent2_file, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg["agent2_config"], f, allow_unicode=True, sort_keys=False)
                with open(agent3_file, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg["agent3_config"], f, allow_unicode=True, sort_keys=False)

                # 清除配置缓存以强制重新加载
                config_manager._config_cache.clear()
                config_manager._cache_timestamps.clear()

                st.success("配置已保存到 config/agents/*.yaml 文件")
            except Exception as e:
                st.error(f"保存失败: {e}")


