import asyncio
import time
import traceback
from typing import List, Dict, Any, Union
from pydantic import ValidationError
from .registry import FunctionRegistry
from .context import PipelineContext

class PipelineEngine:
    """
    流程执行引擎
    负责解析配置，调度原子函数，并管理上下文。
    """
    def __init__(self, context: PipelineContext = None):
        self.context = context or PipelineContext()

    async def run_task(self, task_config: Dict[str, Any]):
        """
        运行单个任务，支持重试和错误处理
        
        Task Config 结构示例:
        {
            "id": "fetch_news_step",
            "tool": "fetch_news_stream",
            "inputs": { ... },
            "output": "raw_news_data",
            "retry": 3,              # 可选：重试次数
            "continue_on_error": false # 可选：出错是否继续
        }
        """
        tool_name = task_config.get("tool")
        task_id = task_config.get("id", tool_name)
        retry_count = task_config.get("retry", 0)
        continue_on_error = task_config.get("continue_on_error", False)
        
        self.context.log(f"开始执行任务: {task_id} (工具: {tool_name})", source="Engine")
        
        func = FunctionRegistry.get_tool(tool_name)
        if not func:
            error_msg = f"找不到工具: {tool_name}"
            self.context.log(error_msg, level="ERROR", source="Engine")
            raise ValueError(error_msg)

        # 1. 解析并准备参数
        try:
            inputs = self._resolve_inputs(task_config.get("inputs", {}))
            
            # Pydantic 校验
            input_model = FunctionRegistry.get_input_model(tool_name)
            if input_model:
                try:
                    # 将字典转换为模型实例再转回字典（完成校验和类型转换）
                    validated_data = input_model(**inputs)
                    # 注意：如果函数签名接受的是具体参数而不是 **kwargs，
                    # 可能需要将 validated_data.dict() 解包。
                    # 这里保持 inputs 为字典，但在调用前确保了它符合模型。
                    # 如果需要更严格的类型转换，可以使用 validated_data.model_dump()
                    inputs = validated_data.model_dump()
                except ValidationError as ve:
                    raise ValueError(f"参数校验失败: {ve}")

        except Exception as e:
            self.context.log(f"参数解析/校验失败: {e}", level="ERROR", source="Engine")
            if continue_on_error:
                return None
            raise e

        # 2. 执行函数 (带重试逻辑)
        attempt = 0
        last_error = None
        
        while attempt <= retry_count:
            if attempt > 0:
                self.context.log(f"重试任务 {task_id} (第 {attempt}/{retry_count} 次)...", level="WARNING", source="Engine")
                await asyncio.sleep(1 * attempt) # 简单的指数退避
                
            start_time = time.time()
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(**inputs)
                else:
                    result = func(**inputs)
                
                duration = time.time() - start_time
                
                # 3. 处理输出
                output_key = task_config.get("output")
                if output_key:
                    self.context.set(output_key, result)
                    self.context.log(f"任务 {task_id} 完成，结果已存入 '{output_key}'", source="Engine")
                else:
                    self.context.log(f"任务 {task_id} 完成 (无输出存储)", source="Engine")

                self.context.record_execution(tool_name, "success", duration)
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                last_error = e
                error_msg = f"任务 {task_id} 执行出错: {str(e)}"
                self.context.log(error_msg, level="ERROR", source="Engine")
                self.context.record_execution(tool_name, "failed", duration, str(e))
                # 继续下一次重试循环
            
            attempt += 1

        # 重试耗尽
        final_msg = f"任务 {task_id} 失败，已重试 {retry_count} 次。错误: {last_error}"
        self.context.log(final_msg, level="CRITICAL", source="Engine")
        
        if continue_on_error:
            self.context.log(f"根据配置 continue_on_error=True，跳过此错误继续执行。", level="WARNING", source="Engine")
            return None
        else:
            raise last_error

    def _resolve_inputs(self, input_mapping: Dict[str, Any]) -> Dict[str, Any]:
        """解析输入参数中的变量引用"""
        inputs = {}
        for arg_name, value_mapping in input_mapping.items():
            if isinstance(value_mapping, str) and value_mapping.startswith("$"):
                # 从上下文获取变量，例如 "$user_query" -> context.get("user_query")
                key = value_mapping[1:]
                val = self.context.get(key)
                # 注意：这里如果 val 为 None，可能是有意为之，也可能是变量未定义
                # 暂时不强制报错，由 Pydantic 校验去处理 required 字段
                inputs[arg_name] = val
            else:
                # 直接字面量
                inputs[arg_name] = value_mapping
        return inputs

    async def run_pipeline(self, pipeline_config: List[Dict[str, Any]]):
        """
        执行完整流程
        
        pipeline_config: 任务列表
        """
        self.context.log("启动流程执行...", source="Engine")
        
        for task_config in pipeline_config:
            try:
                await self.run_task(task_config)
            except Exception as e:
                # 如果 run_task 抛出异常（意味着重试耗尽且 continue_on_error=False）
                # 则整个 Pipeline 中止
                self.context.log(f"流程执行被中断: {e}", level="CRITICAL", source="Engine")
                raise e
            
        self.context.log("流程执行结束", source="Engine")
        return self.context
