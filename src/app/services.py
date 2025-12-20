"""
Application Services（应用服务层）。

用例固化：
- IngestionService: 新闻入库（抓取→抽取→落 mention/canonical）
- ReviewService: 审查流程（候选生成→LLM裁决→执行→审计）
- KnowledgeGraphService: 图谱服务（refresh/export/snapshot）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..domain import (
    EntityCanonical,
    EntityMention,
    EventCanonical,
    EventEdge,
    EventMention,
    MergeDecision,
    ReviewTask,
)
from ..infra import utc_now, utc_now_iso, IdFactory


# =============================================================================
# Service 基类
# =============================================================================


@dataclass
class ServiceResult:
    """服务执行结果"""
    success: bool = True
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class BaseService(ABC):
    """服务基类"""

    def _success(self, message: str = "", **data) -> ServiceResult:
        return ServiceResult(success=True, message=message, data=data)

    def _error(self, error: str, **data) -> ServiceResult:
        return ServiceResult(success=False, error=error, data=data)


# =============================================================================
# IngestionService（入库服务）
# =============================================================================


@dataclass
class IngestionConfig:
    """入库配置"""
    max_workers: int = 3
    rate_limit_per_sec: float = 1.0
    batch_size: int = 50
    skip_duplicate: bool = True


@dataclass
class IngestionResult(ServiceResult):
    """入库结果"""
    entities_created: int = 0
    entities_updated: int = 0
    events_created: int = 0
    events_updated: int = 0
    mentions_created: int = 0
    sources_processed: int = 0
    run_id: str = ""


class IngestionService(ABC):
    """
    入库服务接口：
    输入：news items
    输出：写 SQLite（mentions + 结构化元组），并记录 run_id
    """

    @abstractmethod
    def ingest_news(
        self,
        news_items: List[Dict[str, Any]],
        config: Optional[IngestionConfig] = None,
    ) -> IngestionResult:
        """
        入库新闻。
        
        Args:
            news_items: 新闻列表
            config: 入库配置
            
        Returns:
            入库结果
        """
        ...

    @abstractmethod
    async def ingest_news_async(
        self,
        news_items: List[Dict[str, Any]],
        config: Optional[IngestionConfig] = None,
    ) -> IngestionResult:
        """异步入库新闻"""
        ...

    @abstractmethod
    def extract_entities(
        self,
        text: str,
        source_id: str = "",
    ) -> List[EntityMention]:
        """从文本中抽取实体 mentions"""
        ...

    @abstractmethod
    def extract_events(
        self,
        text: str,
        source_id: str = "",
    ) -> List[EventMention]:
        """从文本中抽取事件 mentions"""
        ...


# =============================================================================
# ReviewService（审查服务）
# =============================================================================


@dataclass
class ReviewConfig:
    """审查配置"""
    min_similarity: float = 0.92
    max_pairs: int = 200
    max_review_tasks: int = 30
    rate_limit_per_sec: float = 0.5
    max_apply: int = 30
    shared_entity_min: int = 2
    days_window: int = 14


@dataclass
class ReviewResult(ServiceResult):
    """审查结果"""
    candidates_generated: int = 0
    tasks_reviewed: int = 0
    tasks_failed: int = 0
    merges_applied: int = 0
    edges_created: int = 0
    skipped: int = 0


class ReviewService(ABC):
    """
    审查服务接口：
    候选生成 → LLM裁决 → 执行 → 审计
    """

    @abstractmethod
    def generate_entity_merge_candidates(
        self,
        min_similarity: float = 0.92,
        max_pairs: int = 200,
    ) -> int:
        """生成实体合并候选，返回候选数量"""
        ...

    @abstractmethod
    def generate_event_merge_candidates(
        self,
        shared_entity_min: int = 2,
        days_window: int = 14,
        max_pairs: int = 200,
    ) -> int:
        """生成事件合并/演化候选，返回候选数量"""
        ...

    @abstractmethod
    def run_review_worker(
        self,
        task_type: str,
        max_tasks: int = 20,
        rate_limit_per_sec: float = 0.5,
    ) -> Dict[str, int]:
        """
        运行审查 worker。
        
        Returns:
            {"done": n, "failed": m}
        """
        ...

    @abstractmethod
    def apply_entity_merges(
        self,
        max_actions: int = 50,
    ) -> Dict[str, int]:
        """
        应用实体合并决策。
        
        Returns:
            {"applied": n, "skipped": m}
        """
        ...

    @abstractmethod
    def apply_event_decisions(
        self,
        max_actions: int = 50,
    ) -> Dict[str, int]:
        """
        应用事件决策（merge/evolve）。
        
        Returns:
            {"merged": n, "edges_added": m, "skipped": k}
        """
        ...

    @abstractmethod
    def run_end_to_end(
        self,
        config: Optional[ReviewConfig] = None,
    ) -> ReviewResult:
        """端到端审查流程"""
        ...

    @abstractmethod
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取审查队列统计"""
        ...


# =============================================================================
# KnowledgeGraphService（图谱服务）
# =============================================================================


@dataclass
class SnapshotConfig:
    """快照配置"""
    top_entities: int = 500
    top_events: int = 500
    max_edges: int = 5000
    days_window: int = 0
    gap_days: int = 30


@dataclass
class KGRefreshResult(ServiceResult):
    """图谱刷新结果"""
    entities_count: int = 0
    events_count: int = 0
    relations_count: int = 0
    edges_count: int = 0


@dataclass
class SnapshotResult(ServiceResult):
    """快照生成结果"""
    paths: Dict[str, str] = field(default_factory=dict)
    graph_types: List[str] = field(default_factory=list)


class KnowledgeGraphService(ABC):
    """
    图谱服务接口：
    refresh / export / snapshot
    """

    @abstractmethod
    def refresh(self) -> KGRefreshResult:
        """刷新知识图谱"""
        ...

    @abstractmethod
    def export_compat_json(self) -> Dict[str, str]:
        """
        导出兼容 JSON 文件。
        
        Returns:
            文件路径映射
        """
        ...

    @abstractmethod
    def generate_snapshots(
        self,
        config: Optional[SnapshotConfig] = None,
    ) -> SnapshotResult:
        """
        生成五图谱快照。
        
        Args:
            config: 快照配置
            
        Returns:
            快照生成结果
        """
        ...

    @abstractmethod
    def get_stats(self) -> Dict[str, int]:
        """
        获取图谱统计。
        
        Returns:
            {"entities": n, "events": m, "relations": k, "edges": j}
        """
        ...

    @abstractmethod
    def query_entity(
        self,
        entity_name: str,
    ) -> Optional[EntityCanonical]:
        """查询实体"""
        ...

    @abstractmethod
    def query_event(
        self,
        abstract: str,
    ) -> Optional[EventCanonical]:
        """查询事件"""
        ...

    @abstractmethod
    def query_entity_timeline(
        self,
        entity_name: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询实体时间线"""
        ...

    @abstractmethod
    def query_event_edges(
        self,
        event_id: str,
    ) -> List[EventEdge]:
        """查询事件演化边"""
        ...
