import streamlit as st
import yaml
import asyncio
import json
from pathlib import Path
from datetime import datetime
from src.core.registry import FunctionRegistry
from src.core.engine import PipelineEngine
from src.core.context import PipelineContext
from src.data.api_client import DataAPIPool, get_apis_config
import src.functions.data_fetch
import src.functions.extraction
import src.functions.graph_ops
import src.functions.reporting

def render():
    st.title("⛓️ Pipeline Builder")
    
    # 初始化 Session State
    if "pipeline_steps" not in st.session_state:
        st.session_state.pipeline_steps = []
    
    # 模式选择
    mode = st.radio("Mode", ["🚀 Core Workflows", "🛠️ Custom Builder"], horizontal=True)
    
    st.markdown("---")
    
    if mode == "🚀 Core Workflows":
        render_core_workflows()
    else:
        render_custom_builder()

def render_core_workflows():
    st.header("Daily Market Scan")
    st.caption("Standard pipeline for fetching news, extracting events, and updating the Knowledge Graph.")
    
    # 获取动态数据源列表
    try:
        pool = DataAPIPool()
        available_sources = pool.list_available_sources()
    except Exception as e:
        st.warning(f"Could not load data sources: {e}")
        available_sources = []

    # 配置表单
    with st.form("daily_scan_config"):
        col1, col2 = st.columns(2)
        with col1:
            news_limit = st.slider("News Limit", 10, 500, 50)
            
            # 使用动态获取的 sources 填充
            default_source = [available_sources[0]] if available_sources else []
            sources = st.multiselect("Sources", available_sources, default=default_source)
        
        with col2:
            enable_report = st.checkbox("Generate Report", value=True)
            report_title = st.text_input("Report Title", value=f"Market Scan {datetime.now().strftime('%Y-%m-%d')}")
        
        submitted = st.form_submit_button("Run Workflow", type="primary")
        
    if submitted:
        if not sources:
            st.error("Please select at least one data source.")
            return

        # 动态构建配置
        pipeline_def = {
            "name": "Daily Market Scan (Interactive)",
            "steps": [
                {
                    "id": "fetch_news",
                    "tool": "fetch_news_stream",
                    "inputs": {"limit": news_limit, "sources": sources},
                    "output": "raw_news_data"
                },
                {
                    "id": "process_news",
                    "tool": "batch_process_news",
                    "inputs": {"news_list": "$raw_news_data"},
                    "output": "extracted_events"
                },
                {
                    "id": "update_kg",
                    "tool": "update_graph_data",
                    "inputs": {"events_list": "$extracted_events"},
                    "output": "update_status"
                }
            ]
        }
        
        if enable_report:
            pipeline_def["steps"].append({
                "id": "generate_report",
                "tool": "generate_markdown_report",
                "inputs": {"events_list": "$extracted_events", "title": report_title},
                "output": "final_report_md"
            })
            
        execute_pipeline(pipeline_def)

def render_custom_builder():
    st.header("Custom Pipeline Builder")
    st.caption("Build custom workflows by adding and configuring tools.")
    
    col_builder, col_preview = st.columns([1.5, 1])
    
    with col_builder:
        st.subheader("Pipeline Steps")
        
        # 1. 工具选择器
        tools = FunctionRegistry.get_all_tools()
        tool_names = list(tools.keys())
        
        c1, c2 = st.columns([3, 1])
        with c1:
            selected_tool = st.selectbox("Add Step", tool_names)
        with c2:
            if st.button("Add", use_container_width=True):
                # 添加默认步骤
                st.session_state.pipeline_steps.append({
                    "id": f"step_{len(st.session_state.pipeline_steps) + 1}",
                    "tool": selected_tool,
                    "inputs": {}
                })
                st.rerun()

        # 2. 步骤列表编辑
        if not st.session_state.pipeline_steps:
            st.info("No steps added. Select a tool above to start.")
        else:
            for i, step in enumerate(st.session_state.pipeline_steps):
                tool_name = step["tool"]
                tool_meta = tools.get(tool_name, {})
                
                with st.expander(f"Step {i+1}: {tool_name} ({step['id']})", expanded=True):
                    # 步骤基本信息
                    c_id, c_del = st.columns([4, 1])
                    new_id = c_id.text_input("Step ID", value=step["id"], key=f"id_{i}")
                    step["id"] = new_id
                    
                    if c_del.button("🗑️", key=f"del_{i}"):
                        st.session_state.pipeline_steps.pop(i)
                        st.rerun()
                    
                    st.caption(tool_meta.get("description", ""))
                    
                    # === Apifox 风格的参数编辑 ===
                    st.markdown("#### Parameters")
                    params = tool_meta.get("parameters", {})
                    current_inputs = step.get("inputs", {})
                    
                    if not params:
                        st.caption("No parameters required.")
                    
                    for p_name, p_info in params.items():
                        render_input_field(i, p_name, p_info, current_inputs, step)
                            
                    # 输出变量名
                    st.markdown("#### Output")
                    step["output"] = st.text_input("Store Result To ($var)", value=step.get("output", ""), key=f"out_{i}", placeholder="e.g., raw_data")

    with col_preview:
        st.subheader("Configuration Preview")
        
        # 构造 YAML 视图
        pipeline_def = {
            "name": "Custom Pipeline",
            "steps": st.session_state.pipeline_steps
        }
        yaml_str = yaml.dump(pipeline_def, sort_keys=False, allow_unicode=True)
        st.code(yaml_str, language="yaml")
        
        st.markdown("---")
        if st.button("🚀 Run Custom Pipeline", type="primary", use_container_width=True):
            execute_pipeline(pipeline_def)

def render_input_field(step_idx, p_name, p_info, current_inputs, step):
    """
    智能渲染输入组件，根据参数类型选择合适的 UI 控件
    """
    p_type = p_info.get('type', 'Any')
    p_required = p_info.get('required', False)
    default_val = p_info.get('default')
    
    # 标签 (带必填标记)
    label = f"{p_name}"
    if p_required:
        label += " *"
    
    help_text = f"Type: {p_type}"
    if default_val:
        help_text += f", Default: {default_val}"
    help_text += ". Use $var to reference context."

    key = f"in_{step_idx}_{p_name}"
    
    # 获取当前值，如果未设置则使用默认值
    current_val = current_inputs.get(p_name)
    
    # 1. Boolean 类型
    if "bool" in p_type.lower():
        # 如果当前值是字符串且是 $var 引用，则无法用 Checkbox，需要回退到 Text
        if isinstance(current_val, str) and current_val.startswith("$"):
             val = st.text_input(label + " (Context Ref)", value=current_val, key=key, help=help_text)
        else:
            # 解析 bool 值
            bool_val = False
            if current_val is not None:
                bool_val = str(current_val).lower() == "true"
            elif default_val:
                bool_val = str(default_val).lower() == "true"
                
            val = st.checkbox(label, value=bool_val, key=key, help=help_text)
            
        if val is not None:
            step["inputs"][p_name] = val

    # 2. Integer 类型
    elif "int" in p_type.lower():
        # 同样检查引用
        if isinstance(current_val, str) and current_val.startswith("$"):
            val = st.text_input(label + " (Context Ref)", value=current_val, key=key, help=help_text)
            step["inputs"][p_name] = val
        else:
            # 尝试解析 int
            int_val = 0
            if current_val is not None:
                try: int_val = int(current_val)
                except: pass
            elif default_val and default_val != "None":
                try: int_val = int(default_val)
                except: pass
                
            val = st.number_input(label, value=int_val, step=1, key=key, help=help_text)
            step["inputs"][p_name] = int(val)

    # 3. List 类型 (简单处理)
    elif "list" in p_type.lower():
        # 这里用 TextArea 模拟多行输入，或者 Text Input 用逗号分隔
        # 如果是已知源列表，可以用 multiselect，这里简化处理
        val_str = ""
        if isinstance(current_val, list):
            val_str = str(current_val) # 显示为 Python list 字符串
        elif current_val:
            val_str = str(current_val)
        elif default_val and default_val != "None":
            val_str = str(default_val)
            
        new_val_str = st.text_area(label + " (List/JSON)", value=val_str, height=68, key=key, help="Enter a JSON list or $var")
        
        # 尝试解析为 List
        if new_val_str.startswith("$"):
            step["inputs"][p_name] = new_val_str
        else:
            try:
                # 尝试安全解析 (AST literal eval 或 json)
                import ast
                if new_val_str.strip():
                    parsed = ast.literal_eval(new_val_str)
                    if isinstance(parsed, list):
                        step["inputs"][p_name] = parsed
                    else:
                         step["inputs"][p_name] = new_val_str # Fallback
                else:
                    if p_name in step["inputs"]: del step["inputs"][p_name]
            except:
                step["inputs"][p_name] = new_val_str # Keep as string if parsing fails

    # 4. 默认 String / Any
    else:
        val_str = ""
        if current_val is not None:
            val_str = str(current_val)
        elif default_val and default_val != "None":
            # 清理引号
            val_str = str(default_val).strip("'").strip('"')
            
        val = st.text_input(label, value=val_str, key=key, help=help_text)
        if val:
            step["inputs"][p_name] = val

def execute_pipeline(pipeline_def):
    """通用流水线执行器"""
    st.divider()
    st.subheader("Execution Status")
    
    log_container = st.empty()
    
    with st.spinner("Running pipeline..."):
        try:
            # 创建新的事件循环运行异步任务
            asyncio.run(run_pipeline_wrapper(pipeline_def, log_container))
            st.success("Pipeline Completed Successfully!")
        except Exception as e:
            st.error(f"Execution Failed: {e}")

async def run_pipeline_wrapper(pipeline_def, log_container):
    context = PipelineContext()
    engine = PipelineEngine(context)
    
    steps = pipeline_def.get("steps", [])
    
    # 进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_steps = len(steps)
    
    for i, step in enumerate(steps):
        step_id = step.get('id')
        status_text.text(f"Running step {i+1}/{total_steps}: {step_id}...")
        
        try:
            await engine.run_task(step)
            
            # 实时刷新日志
            logs = context.logs
            # 仅显示最后15条，避免太长
            recent_logs = logs[-15:]
            log_text = "\n".join([f"[{l['timestamp'].split('T')[1][:8]}] [{l['level']}] {l['message']}" for l in recent_logs])
            log_container.code(log_text, language="text")
            
            progress_bar.progress((i + 1) / total_steps)
            
        except Exception as e:
            st.error(f"Step '{step_id}' failed: {e}")
            raise e
            
    status_text.text("Done!")
    
    # 最终报告展示
    report = context.get("final_report_md")
    if report:
        with st.expander("📄 Generated Report", expanded=True):
            st.markdown(report)
