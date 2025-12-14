import streamlit as st
from src.web.framework.page import init_page, PageSpec

# MUST be the first Streamlit command on this page
init_page(PageSpec(title="新闻智能体系统 - News Intelligence Agent", icon="📰"))

st.title("📰 新闻智能体系统")
st.markdown("""
### 基于大语言模型和知识图谱的智能新闻处理与分析系统

本系统通过多智能体协作实现从"新闻→实体→事件→知识图谱"的自动化处理流程。

#### 🎯 核心功能
- **智能新闻处理**: 自动提取实体和事件，构建知识图谱
- **多源数据接入**: 支持GNews等多渠道新闻源
- **实时可视化**: 知识图谱和处理结果的Web界面展示
- **并发处理**: 基于AsyncExecutor的高效异步处理架构

#### 🚀 智能体流水线
```
新闻源 → Agent1(提取) → Agent2(扩展) → Agent3(图谱构建)
    ↓         ↓            ↓            ↓
多源API   实体/事件提取  相关新闻搜索   知识图谱压缩
```

请选择左侧的功能模块开始使用。
""")

