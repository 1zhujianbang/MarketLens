"""
LLM 适配器包。

提供对各种 LLM 提供商的适配实现。
"""

from .providers import (
    OpenAIAdapter,
    KimiAdapter,
    AliyunAdapter,
    DefaultLLMClientPool,
    create_llm_client,
)
from .pool import DefaultLLMPool, get_llm_pool

# 兼容别名：LLMAPIPool 指向新的 DefaultLLMPool 实现
LLMAPIPool = DefaultLLMPool

__all__ = [
    "OpenAIAdapter",
    "KimiAdapter",
    "AliyunAdapter",
    "DefaultLLMClientPool",
    "DefaultLLMPool",
    "LLMAPIPool",
    "create_llm_client",
    "get_llm_pool",
]
