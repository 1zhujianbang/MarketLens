"""
Application Services 实现。

提供 IngestionService、ReviewService、KnowledgeGraphService 的具体实现。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .services import (
    IngestionService, IngestionConfig, IngestionResult,
    ReviewService, ReviewConfig, ReviewResult,
    KnowledgeGraphService, SnapshotConfig, KGRefreshResult, SnapshotResult,
)
from ..domain import (
    EntityCanonical, EntityMention, EventCanonical, EventMention, EventEdge
)
from ..ports.extraction import EntityExtractor, EventExtractor
from ..ports.store import UnifiedStore
from ..infra import get_logger, IdFactory, utc_now


class IngestionServiceImpl(IngestionService):
    """入库服务实现"""

    def __init__(
        self,
        store: UnifiedStore,
        entity_extractor: Optional[EntityExtractor] = None,
        event_extractor: Optional[EventExtractor] = None,
    ):
        self._store = store
        self._entity_extractor = entity_extractor
        self._event_extractor = event_extractor
        self._logger = get_logger(__name__)

    def ingest_news(
        self,
        news_items: List[Dict[str, Any]],
        config: Optional[IngestionConfig] = None,
    ) -> IngestionResult:
        """入库新闻"""
        config = config or IngestionConfig()
        result = IngestionResult(
            success=True,
            run_id=IdFactory.run_id(),
            started_at=utc_now()
        )

        for item in news_items:
            try:
                # 1. 处理新闻项
                source_id = item.get("id", "")
                text = item.get("content", "") or item.get("title", "")

                if not text:
                    continue

                # 2. 抽取实体
                entities = self.extract_entities(text, source_id)
                for entity in entities:
                    # TODO: 实际写入存储
                    result.mentions_created += 1

                # 3. 抽取事件
                events = self.extract_events(text, source_id)
                for event in events:
                    result.mentions_created += 1

                result.sources_processed += 1

            except Exception as e:
                self._logger.error(f"Failed to ingest news item: {e}")

        result.finished_at = utc_now()
        return result

    async def ingest_news_async(
        self,
        news_items: List[Dict[str, Any]],
        config: Optional[IngestionConfig] = None,
    ) -> IngestionResult:
        """异步入库新闻"""
        # 简单实现：调用同步方法
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.ingest_news, news_items, config
        )

    def extract_entities(
        self,
        text: str,
        source_id: str = "",
    ) -> List[EntityMention]:
        """从文本中抽取实体"""
        if not self._entity_extractor:
            return []

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            self._entity_extractor.extract(text)
        )

        if not result.success:
            return []

        mentions = []
        for entity in result.entities:
            mention = EntityMention(
                mention_id=IdFactory.mention_id(entity.name, source_id, utc_now().isoformat()),
                name_text=entity.name,
                reported_at=utc_now(),
                source=None,  # TODO: 创建 SourceRef
                confidence=entity.confidence,
                created_at=utc_now()
            )
            mentions.append(mention)

        return mentions

    def extract_events(
        self,
        text: str,
        source_id: str = "",
    ) -> List[EventMention]:
        """从文本中抽取事件"""
        if not self._event_extractor:
            return []

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            self._event_extractor.extract(text)
        )

        if not result.success:
            return []

        mentions = []
        for event in result.events:
            mention = EventMention(
                mention_id=IdFactory.mention_id(event.abstract, source_id, utc_now().isoformat()),
                abstract_text=event.abstract,
                reported_at=utc_now(),
                source=None,
                event_type=event.event_type,
                confidence=event.confidence,
                created_at=utc_now()
            )
            mentions.append(mention)

        return mentions


class ReviewServiceImpl(ReviewService):
    """审查服务实现"""

    def __init__(self, store: UnifiedStore):
        self._store = store
        self._logger = get_logger(__name__)

    def generate_entity_merge_candidates(
        self,
        min_similarity: float = 0.92,
        max_pairs: int = 200,
    ) -> int:
        """生成实体合并候选"""
        # TODO: 实现候选生成逻辑
        self._logger.info(f"Generating entity merge candidates (similarity >= {min_similarity})")
        return 0

    def generate_event_merge_candidates(
        self,
        shared_entity_min: int = 2,
        days_window: int = 14,
        max_pairs: int = 200,
    ) -> int:
        """生成事件合并候选"""
        self._logger.info(f"Generating event merge candidates (shared >= {shared_entity_min})")
        return 0

    def run_review_worker(
        self,
        task_type: str,
        max_tasks: int = 20,
        rate_limit_per_sec: float = 0.5,
    ) -> Dict[str, int]:
        """运行审查 worker"""
        self._logger.info(f"Running review worker for {task_type}")
        return {"done": 0, "failed": 0}

    def apply_entity_merges(
        self,
        max_actions: int = 50,
    ) -> Dict[str, int]:
        """应用实体合并"""
        return {"applied": 0, "skipped": 0}

    def apply_event_decisions(
        self,
        max_actions: int = 50,
    ) -> Dict[str, int]:
        """应用事件决策"""
        return {"merged": 0, "edges_added": 0, "skipped": 0}

    def run_end_to_end(
        self,
        config: Optional[ReviewConfig] = None,
    ) -> ReviewResult:
        """端到端审查流程"""
        config = config or ReviewConfig()
        result = ReviewResult(success=True, started_at=utc_now())

        # 1. 生成候选
        result.candidates_generated = self.generate_entity_merge_candidates(
            min_similarity=config.min_similarity,
            max_pairs=config.max_pairs
        )

        # 2. 运行审查
        worker_result = self.run_review_worker("entity_merge", config.max_review_tasks)
        result.tasks_reviewed = worker_result.get("done", 0)
        result.tasks_failed = worker_result.get("failed", 0)

        # 3. 应用合并
        apply_result = self.apply_entity_merges(config.max_apply)
        result.merges_applied = apply_result.get("applied", 0)
        result.skipped = apply_result.get("skipped", 0)

        result.finished_at = utc_now()
        return result

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        return {
            "pending_entity_merges": 0,
            "pending_event_decisions": 0,
            "completed_today": 0
        }


class KnowledgeGraphServiceImpl(KnowledgeGraphService):
    """知识图谱服务实现"""

    def __init__(self, store: UnifiedStore):
        self._store = store
        self._logger = get_logger(__name__)

    def refresh(self) -> KGRefreshResult:
        """刷新知识图谱"""
        result = KGRefreshResult(success=True, started_at=utc_now())

        stats = self.get_stats()
        result.entities_count = stats.get("entities", 0)
        result.events_count = stats.get("events", 0)
        result.relations_count = stats.get("relations", 0)
        result.edges_count = stats.get("edges", 0)

        result.finished_at = utc_now()
        return result

    def export_compat_json(self) -> Dict[str, str]:
        """导出兼容 JSON"""
        return {}

    def generate_snapshots(
        self,
        config: Optional[SnapshotConfig] = None,
    ) -> SnapshotResult:
        """生成快照"""
        config = config or SnapshotConfig()
        result = SnapshotResult(
            success=True,
            started_at=utc_now(),
            graph_types=["entity", "event", "relation", "evolution", "timeline"]
        )

        result.finished_at = utc_now()
        return result

    def get_stats(self) -> Dict[str, int]:
        """获取统计"""
        return {
            "entities": 0,
            "events": 0,
            "relations": 0,
            "edges": 0
        }

    def query_entity(
        self,
        entity_name: str,
    ) -> Optional[EntityCanonical]:
        """查询实体"""
        return None

    def query_event(
        self,
        abstract: str,
    ) -> Optional[EventCanonical]:
        """查询事件"""
        return None

    def query_entity_timeline(
        self,
        entity_name: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询实体时间线"""
        return []

    def query_event_edges(
        self,
        event_id: str,
    ) -> List[EventEdge]:
        """查询事件演化边"""
        return []


# =============================================================================
# 服务工厂
# =============================================================================

_services_registry: Dict[str, Any] = {}


def get_ingestion_service() -> IngestionService:
    """获取入库服务"""
    if "ingestion" not in _services_registry:
        from src.adapters.sqlite.store import get_store
        store = get_store()
        _services_registry["ingestion"] = IngestionServiceImpl(store)
    return _services_registry["ingestion"]


def get_review_service() -> ReviewService:
    """获取审查服务"""
    if "review" not in _services_registry:
        from src.adapters.sqlite.store import get_store
        store = get_store()
        _services_registry["review"] = ReviewServiceImpl(store)
    return _services_registry["review"]


def get_kg_service() -> KnowledgeGraphService:
    """获取图谱服务"""
    if "kg" not in _services_registry:
        from src.adapters.sqlite.store import get_store
        store = get_store()
        _services_registry["kg"] = KnowledgeGraphServiceImpl(store)
    return _services_registry["kg"]
