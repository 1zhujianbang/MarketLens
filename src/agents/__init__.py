"""
src.agents 包 - 委托层

已迁移模块：
- Agent 编排 -> interfaces/agents/
- LLMAPIPool -> adapters/llm/pool.py
本模块保留以兼容旧代码。
"""

# LLM池 - 从 adapters 重导出
from ..adapters.llm import LLMAPIPool, DefaultLLMPool

# Agent 编排 - 从 interfaces 重导出
from ..interfaces.agents import (
    Agent1 as NewAgent1,
    Agent2 as NewAgent2,
    Agent3 as NewAgent3,
    AgentPipeline,
    create_default_pipeline,
)

__all__ = [
    "LLMAPIPool",
    "DefaultLLMPool",
    "NewAgent1",
    "NewAgent2",
    "NewAgent3",
    "AgentPipeline",
    "create_default_pipeline",
]
