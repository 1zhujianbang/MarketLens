import streamlit as st

def load_openai_style():
    """注入模仿 OpenAI Platform 的 CSS 样式"""
    st.markdown("""
        <style>
        /* 全局字体与背景 */
        .stApp {
            font-family: 'Söhne', 'ui-sans-serif', 'system-ui', -apple-system, 'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif;
            background-color: #ffffff;
            color: #0d0d0d;
        }
        
        /* 侧边栏样式 */
        section[data-testid="stSidebar"] {
            background-color: #f9f9f9;
            border-right: 1px solid #e5e5e5;
        }
        
        section[data-testid="stSidebar"] .block-container {
            padding-top: 2rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        /* 隐藏 Streamlit 默认头部装饰 */
        header[data-testid="stHeader"] {
            background-color: transparent;
        }
        
        /* 导航 Radio 按钮改造 */
        .stRadio > label {
            display: none; /* 隐藏标题 */
        }
        
        div[role="radiogroup"] > label {
            background-color: transparent !important;
            border: none;
            padding: 0.5rem 0.75rem;
            margin-bottom: 0.2rem;
            border-radius: 6px;
            color: #6e6e80;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        div[role="radiogroup"] > label:hover {
            background-color: #ececf1 !important;
            color: #0d0d0d;
        }
        
        /* 选中状态 */
        div[role="radiogroup"] > label[data-checked="true"] {
            background-color: #ececf1 !important;
            color: #0d0d0d;
            font-weight: 600;
        }

        /* 标题样式 */
        h1, h2, h3 {
            font-family: 'Söhne', sans-serif;
            letter-spacing: -0.01em;
            color: #202123;
        }
        
        /* 按钮样式 - Primary (模仿 OpenAI 黑色/绿色按钮) */
        .stButton > button {
            border-radius: 6px;
            border: 1px solid #e5e5e5;
            background-color: #ffffff;
            color: #0d0d0d;
            font-weight: 500;
            padding: 0.5rem 1rem;
            transition: all 0.1s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        .stButton > button:hover {
            border-color: #d1d1d1;
            background-color: #f7f7f8;
            color: #0d0d0d;
        }
        
        .stButton > button:active {
            background-color: #f0f0f1;
        }

        /* 特定 Primary 按钮覆盖 (如果有特定的 type='primary') */
        .stButton > button[kind="primary"] {
            background-color: #10a37f;
            color: white;
            border: none;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #1a7f64;
        }

        /* 卡片/容器样式 */
        div[data-testid="stMetric"], div[data-testid="stExpander"] {
            background-color: #ffffff;
            border: 1px solid #e5e5e5;
            border-radius: 6px;
            padding: 1rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        
        /* 调整 Metric 样式 */
        div[data-testid="stMetricLabel"] {
            font-size: 0.875rem;
            color: #6e6e80;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.5rem;
            font-weight: 600;
            color: #202123;
        }

        /* 输入框样式 */
        .stTextInput > div > div > input, .stTextArea > div > div > textarea {
            border-radius: 6px;
            border-color: #e5e5e5;
            color: #0d0d0d;
        }
        .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
            border-color: #10a37f;
            box-shadow: 0 0 0 1px #10a37f;
        }

        </style>
    """, unsafe_allow_html=True)

def render_sidebar_header():
    """渲染侧边栏顶部 Logo 区域"""
    st.sidebar.markdown("""
        <div style="padding-bottom: 1.5rem; padding-left: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <div style="width: 32px; height: 32px; background-color: #202123; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-weight: bold; font-size: 18px;">M</span>
                </div>
                <div>
                    <div style="font-weight: 600; font-size: 1rem; color: #202123;">Market Lens</div>
                    <div style="font-size: 0.75rem; color: #6e6e80;">v0.2.0</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

