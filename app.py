import streamlit as st
import sys
from pathlib import Path

# 添加项目根目录到 path
ROOT_DIR = Path(__file__).parent
sys.path.append(str(ROOT_DIR))

# 设置页面配置
st.set_page_config(
    page_title="Market Lens - 市场透镜",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Market Lens - 市场透镜")
st.markdown("""
### 欢迎使用智能市场感知与决策系统

请在左侧侧边栏选择功能模块：

- **Dashboard**: 系统概览与状态监控
- **Pipeline Builder**: 构建和运行数据处理流水线
- **Data Inspector**: 浏览和检查采集的数据
- **Knowledge Graph**: 市场知识图谱可视化
""")

st.sidebar.success("请在上方选择页面")

st.sidebar.info(
    """
    **Market Lens v0.2**
    
    智能市场感知与决策系统
    """
)
