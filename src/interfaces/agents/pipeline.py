"""
入口层 - Agent 编排

将现有 agents 重构为调用 Application Services 的薄封装。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...app.services import (
    IngestionService, ReviewService, KnowledgeGraphService
)
from ...app.services_impl import (
    get_ingestion_service, get_review_service, get_kg_service
)
from ...infra import get_logger


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool = True
    message: str = ""
    data: Dict[str, Any] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self):
        self._logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> AgentResult:
        """执行 Agent 任务"""
        ...

    @abstractmethod
    async def run_async(self, context: Dict[str, Any]) -> AgentResult:
        """异步执行 Agent 任务"""
        ...


class Agent1(BaseAgent):
    """
    Agent1: 新闻抓取与实体抽取

    职责：抓取新闻 → 抽取实体/事件 → 存储 mentions
    """

    def __init__(self, ingestion_service: Optional[IngestionService] = None):
        super().__init__()
        self._ingestion = ingestion_service or get_ingestion_service()

    def run(self, context: Dict[str, Any]) -> AgentResult:
        """执行新闻入库"""
        self._logger.info("Agent1: Starting news ingestion")

        news_items = context.get("news_items", [])
        if not news_items:
            return AgentResult(
                success=False,
                error="No news items provided"
            )

        result = self._ingestion.ingest_news(news_items)

        return AgentResult(
            success=result.success,
            message=f"Processed {result.sources_processed} sources",
            data={
                "mentions_created": result.mentions_created,
                "sources_processed": result.sources_processed,
                "run_id": result.run_id
            },
            error=result.error
        )

    async def run_async(self, context: Dict[str, Any]) -> AgentResult:
        """异步执行"""
        news_items = context.get("news_items", [])
        result = await self._ingestion.ingest_news_async(news_items)

        return AgentResult(
            success=result.success,
            data={
                "mentions_created": result.mentions_created,
                "run_id": result.run_id
            }
        )


class Agent2(BaseAgent):
    """
    Agent2: 实体/事件审查与合并

    职责：生成合并候选 → LLM 裁决 → 执行合并
    """

    def __init__(self, review_service: Optional[ReviewService] = None):
        super().__init__()
        self._review = review_service or get_review_service()

    def run(self, context: Dict[str, Any]) -> AgentResult:
        """执行审查流程"""
        self._logger.info("Agent2: Starting review process")

        result = self._review.run_end_to_end()

        return AgentResult(
            success=result.success,
            message=f"Reviewed {result.tasks_reviewed} tasks, applied {result.merges_applied} merges",
            data={
                "candidates_generated": result.candidates_generated,
                "tasks_reviewed": result.tasks_reviewed,
                "merges_applied": result.merges_applied,
                "skipped": result.skipped
            }
        )

    async def run_async(self, context: Dict[str, Any]) -> AgentResult:
        """异步执行"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, context)


class Agent3(BaseAgent):
    """
    Agent3: 知识图谱构建与快照

    职责：刷新图谱 → 生成快照 → 导出
    """

    def __init__(self, kg_service: Optional[KnowledgeGraphService] = None):
        super().__init__()
        self._kg = kg_service or get_kg_service()

    def run(self, context: Dict[str, Any]) -> AgentResult:
        """执行图谱构建"""
        self._logger.info("Agent3: Starting knowledge graph construction")

        # 1. 刷新图谱
        refresh_result = self._kg.refresh()

        # 2. 生成快照
        snapshot_result = self._kg.generate_snapshots()

        return AgentResult(
            success=refresh_result.success and snapshot_result.success,
            message=f"Graph: {refresh_result.entities_count} entities, {refresh_result.events_count} events",
            data={
                "entities": refresh_result.entities_count,
                "events": refresh_result.events_count,
                "relations": refresh_result.relations_count,
                "snapshots": snapshot_result.graph_types
            }
        )

    async def run_async(self, context: Dict[str, Any]) -> AgentResult:
        """异步执行"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, context)


# =============================================================================
# Pipeline 编排
# =============================================================================


class AgentPipeline:
    """Agent 流水线编排"""

    def __init__(self):
        self._agents: List[BaseAgent] = []
        self._logger = get_logger(__name__)

    def add_agent(self, agent: BaseAgent) -> "AgentPipeline":
        """添加 Agent"""
        self._agents.append(agent)
        return self

    def run(self, initial_context: Optional[Dict[str, Any]] = None) -> List[AgentResult]:
        """执行流水线"""
        context = initial_context or {}
        results = []

        for i, agent in enumerate(self._agents):
            self._logger.info(f"Running agent {i + 1}/{len(self._agents)}: {agent.__class__.__name__}")

            result = agent.run(context)
            results.append(result)

            if not result.success:
                self._logger.error(f"Agent {agent.__class__.__name__} failed: {result.error}")
                break

            # 将结果合并到上下文
            if result.data:
                context.update(result.data)

        return results

    async def run_async(self, initial_context: Optional[Dict[str, Any]] = None) -> List[AgentResult]:
        """异步执行流水线"""
        context = initial_context or {}
        results = []

        for agent in self._agents:
            result = await agent.run_async(context)
            results.append(result)

            if not result.success:
                break

            if result.data:
                context.update(result.data)

        return results


def create_default_pipeline() -> AgentPipeline:
    """创建默认流水线：Agent1 → Agent2 → Agent3"""
    return (
        AgentPipeline()
        .add_agent(Agent1())
        .add_agent(Agent2())
        .add_agent(Agent3())
    )
