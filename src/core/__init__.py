"""
src.core 包（轻量入口 + 懒加载）

目标：
- 避免 import-time 拉起 LLM/agents/utils 等重型依赖，消灭循环导入
- 仍保持对旧代码 `from src.core import X` 的兼容（通过 __getattr__ 懒加载）
"""

from __future__ import annotations

from typing import Any

# 轻量且不产生循环导入的基础导出
from ..infra.registry import FunctionRegistry, register_tool
from ..infra.config import ConfigManager
from ..infra.key_manager import KeyManager, get_key_manager, store_api_key, get_api_key
from ..infra.logging import LoggerManager

# ============================================================================
# 新架构兼容层：从 infra 层重导出
# ============================================================================
# 这些导入提供向后兼容性，新代码应直接从 src.infra 导入
try:
    from ..infra import (
        # Exceptions
        NewsAgentException,
        ConfigError,
        ValidationError,
        NetworkError,
        APIError,
        ProcessingError,
        FileOperationError,
        ConcurrencyError,
        handle_errors,
        handle_async_errors,
        ErrorHandler,
        # Clock & IdFactory
        Clock,
        SystemClock,
        get_clock,
        utc_now,
        utc_now_iso,
        IdFactory,
        # Cache
        MemoryCache,
        SmartCache,
        get_global_cache,
        # Serialization
        Serializer,
        extract_json_from_llm_response,
        safe_json_loads,
        # Retry
        RetryConfig,
        retry_with_backoff,
    )
except ImportError:
    # infra 层可能尚未完全初始化
    pass

# 注意：不要在 import-time 引入 src.utils.tool_function（它会 import src.core.singleton，而导入子模块前会先执行本 __init__，容易形成循环）。
# tools 将通过 __getattr__ 懒加载提供。

# 全局实例工厂函数 (避免循环导入)
def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    return ConfigManager()

def get_logger_manager() -> LoggerManager:
    """获取日志管理器实例"""
    return LoggerManager()

_LAZY_EXPORTS = {
    # Pipeline 执行 - 新架构路径 (app/pipeline)
    "PipelineContext": ("src.app.pipeline.context", "PipelineContext"),
    "PipelineEngine": ("src.app.pipeline.engine", "PipelineEngine"),
    "TaskExecutor": ("src.app.pipeline.engine", "PipelineEngine"),  # 别名
    # 并发/限速（依赖 llm_utils，可能进一步引入 api_client，因此懒加载）
    "AsyncExecutor": ("src.infra.async_utils", "AsyncExecutor"),
    "RateLimiter": ("src.infra.async_utils", "RateLimiter"),
    # LLM Pool - 新架构路径 (adapters/llm)
    "LLMAPIPool": ("src.adapters.llm.pool", "DefaultLLMPool"),
    "DefaultLLMPool": ("src.adapters.llm.pool", "DefaultLLMPool"),
    "get_llm_pool": ("src.adapters.llm.pool", "get_llm_pool"),
    # Data pipeline - 新架构路径 (domain)
    "DataNormalizer": ("src.domain.data_pipeline", "DataNormalizer"),
    "DataPipeline": ("src.domain.data_pipeline", "DataPipeline"),
    "StandardEventPipeline": ("src.domain.data_pipeline", "StandardEventPipeline"),
    "BatchDataProcessor": ("src.domain.data_pipeline", "BatchDataProcessor"),
    # News APIs - 新架构路径 (adapters/news)
    "NewsAPIManager": ("src.adapters.news.api_manager", "NewsAPIManager"),
    "GNewsAdapter": ("src.adapters.news.api_manager", "GNewsAdapter"),
    # 向后兼容旧名称
    "GNewsCollector": ("src.adapters.news.api_manager", "GNewsAdapter"),
}


def __getattr__(name: str) -> Any:  # PEP 562
    if name == "tools":
        from ..infra.paths import tools as ToolsClass

        v = ToolsClass()
        globals()["tools"] = v
        return v
    if name in _LAZY_EXPORTS:
        mod_name, attr = _LAZY_EXPORTS[name]
        import importlib

        m = importlib.import_module(mod_name)
        v = getattr(m, attr)
        globals()[name] = v  # cache
        return v
    raise AttributeError(name)


__all__ = [
    "FunctionRegistry",
    "register_tool",
    "ConfigManager",
    "KeyManager",
    "get_key_manager",
    "store_api_key",
    "get_api_key",
    "LoggerManager",
    "tools",
    "get_config_manager",
    "get_logger_manager",
    *_LAZY_EXPORTS.keys(),
]

