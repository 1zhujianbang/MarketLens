"""
Store 端口（Port）：
定义持久化存储的抽象接口，包括读写操作。

扩展现有的 KGReadStore，增加写操作接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from ..domain import (
    EntityCanonical,
    EntityMention,
    EventCanonical,
    EventEdge,
    EventMention,
    MergeDecision,
    Participant,
    RelationTriple,
    ReviewTask,
    ReviewTaskStatus,
    ReviewTaskType,
)


# =============================================================================
# Read Store（只读仓储 - 基于现有 KGReadStore 扩展）
# =============================================================================


class KGReadStore(Protocol):
    """
    图谱只读仓储端口（用于 Projection/Snapshots）。
    保持与现有接口兼容。
    """

    def fetch_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        ...

    def fetch_events(self) -> List[Dict[str, Any]]:
        """获取所有事件"""
        ...

    def fetch_participants_with_events(self) -> List[Dict[str, Any]]:
        """获取参与关系（带事件信息）"""
        ...

    def fetch_relations(self) -> List[Dict[str, Any]]:
        """获取关系三元组"""
        ...

    def fetch_event_edges(self) -> List[Dict[str, Any]]:
        """获取事件演化边"""
        ...


# =============================================================================
# Entity Store（实体仓储）
# =============================================================================


class EntityStore(ABC):
    """实体仓储端口"""

    @abstractmethod
    def get_entity_by_id(self, entity_id: str) -> Optional[EntityCanonical]:
        """根据 ID 获取实体"""
        ...

    @abstractmethod
    def get_entity_by_name(self, name: str) -> Optional[EntityCanonical]:
        """根据名称获取实体"""
        ...

    @abstractmethod
    def list_entities(
        self,
        limit: int = 1000,
        offset: int = 0,
        order_by: str = "first_seen",
    ) -> List[EntityCanonical]:
        """列出实体"""
        ...

    @abstractmethod
    def search_entities(
        self,
        query: str,
        limit: int = 100,
    ) -> List[EntityCanonical]:
        """搜索实体"""
        ...

    @abstractmethod
    def upsert_entity(self, entity: EntityCanonical) -> str:
        """创建或更新实体，返回 entity_id"""
        ...

    @abstractmethod
    def upsert_entities(self, entities: List[EntityCanonical]) -> int:
        """批量创建或更新实体，返回成功数量"""
        ...

    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool:
        """删除实体"""
        ...

    @abstractmethod
    def merge_entities(
        self,
        from_entity_id: str,
        to_entity_id: str,
        reason: str = "",
        decision_input_hash: str = "",
    ) -> Dict[str, Any]:
        """合并实体（from -> to）"""
        ...

    @abstractmethod
    def get_entity_aliases(self, entity_id: str) -> List[str]:
        """获取实体别名"""
        ...

    @abstractmethod
    def add_entity_alias(
        self,
        alias: str,
        entity_id: str,
        confidence: float = 1.0,
    ) -> bool:
        """添加实体别名"""
        ...


# =============================================================================
# Event Store（事件仓储）
# =============================================================================


class EventStore(ABC):
    """事件仓储端口"""

    @abstractmethod
    def get_event_by_id(self, event_id: str) -> Optional[EventCanonical]:
        """根据 ID 获取事件"""
        ...

    @abstractmethod
    def get_event_by_abstract(self, abstract: str) -> Optional[EventCanonical]:
        """根据摘要获取事件"""
        ...

    @abstractmethod
    def list_events(
        self,
        limit: int = 1000,
        offset: int = 0,
        order_by: str = "first_seen",
        since: Optional[datetime] = None,
    ) -> List[EventCanonical]:
        """列出事件"""
        ...

    @abstractmethod
    def search_events(
        self,
        query: str,
        limit: int = 100,
    ) -> List[EventCanonical]:
        """搜索事件"""
        ...

    @abstractmethod
    def upsert_event(self, event: EventCanonical) -> str:
        """创建或更新事件，返回 event_id"""
        ...

    @abstractmethod
    def upsert_events(self, events: List[EventCanonical]) -> int:
        """批量创建或更新事件，返回成功数量"""
        ...

    @abstractmethod
    def delete_event(self, event_id: str) -> bool:
        """删除事件"""
        ...

    @abstractmethod
    def merge_events(
        self,
        from_event_id: str,
        to_event_id: str,
        reason: str = "",
        decision_input_hash: str = "",
    ) -> Dict[str, Any]:
        """合并事件（from -> to）"""
        ...


# =============================================================================
# Relation Store（关系仓储）
# =============================================================================


class RelationStore(ABC):
    """关系仓储端口"""

    @abstractmethod
    def get_relations_by_entity(
        self,
        entity_id: str,
        direction: str = "both",  # "subject" | "object" | "both"
        limit: int = 100,
    ) -> List[RelationTriple]:
        """获取实体相关的关系"""
        ...

    @abstractmethod
    def get_relations_by_event(
        self,
        event_id: str,
        limit: int = 100,
    ) -> List[RelationTriple]:
        """获取事件相关的关系"""
        ...

    @abstractmethod
    def upsert_relation(self, relation: RelationTriple) -> int:
        """创建或更新关系，返回 ID"""
        ...

    @abstractmethod
    def upsert_relations(self, relations: List[RelationTriple]) -> int:
        """批量创建或更新关系，返回成功数量"""
        ...

    @abstractmethod
    def delete_relation(self, relation_id: int) -> bool:
        """删除关系"""
        ...


# =============================================================================
# Participant Store（参与关系仓储）
# =============================================================================


class ParticipantStore(ABC):
    """参与关系仓储端口"""

    @abstractmethod
    def get_participants_by_event(self, event_id: str) -> List[Participant]:
        """获取事件的参与者"""
        ...

    @abstractmethod
    def get_participants_by_entity(self, entity_id: str) -> List[Participant]:
        """获取实体参与的记录"""
        ...

    @abstractmethod
    def upsert_participant(self, participant: Participant) -> int:
        """创建或更新参与记录"""
        ...

    @abstractmethod
    def upsert_participants(self, participants: List[Participant]) -> int:
        """批量创建或更新参与记录"""
        ...


# =============================================================================
# Event Edge Store（事件边仓储）
# =============================================================================


class EventEdgeStore(ABC):
    """事件边仓储端口"""

    @abstractmethod
    def get_edges_by_event(
        self,
        event_id: str,
        direction: str = "both",  # "from" | "to" | "both"
    ) -> List[EventEdge]:
        """获取事件相关的边"""
        ...

    @abstractmethod
    def list_edges(
        self,
        limit: int = 1000,
        since: Optional[datetime] = None,
    ) -> List[EventEdge]:
        """列出所有边"""
        ...

    @abstractmethod
    def upsert_edge(self, edge: EventEdge) -> int:
        """创建或更新边"""
        ...

    @abstractmethod
    def upsert_edges(self, edges: List[EventEdge]) -> int:
        """批量创建或更新边"""
        ...


# =============================================================================
# Mention Store（提及仓储）
# =============================================================================


class MentionStore(ABC):
    """提及仓储端口"""

    @abstractmethod
    def get_entity_mention(self, mention_id: str) -> Optional[EntityMention]:
        """获取实体提及"""
        ...

    @abstractmethod
    def list_entity_mentions(
        self,
        resolved_entity_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[EntityMention]:
        """列出实体提及"""
        ...

    @abstractmethod
    def upsert_entity_mention(self, mention: EntityMention) -> str:
        """创建或更新实体提及"""
        ...

    @abstractmethod
    def get_event_mention(self, mention_id: str) -> Optional[EventMention]:
        """获取事件提及"""
        ...

    @abstractmethod
    def list_event_mentions(
        self,
        resolved_event_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[EventMention]:
        """列出事件提及"""
        ...

    @abstractmethod
    def upsert_event_mention(self, mention: EventMention) -> str:
        """创建或更新事件提及"""
        ...


# =============================================================================
# Review Store（审查仓储）
# =============================================================================


class ReviewStore(ABC):
    """审查任务与决策仓储端口"""

    @abstractmethod
    def enqueue_review_task(
        self,
        task_type: ReviewTaskType,
        payload: Dict[str, Any],
        priority: int = 50,
    ) -> int:
        """入队审查任务，返回 task_id"""
        ...

    @abstractmethod
    def claim_next_task(
        self,
        task_type: Optional[ReviewTaskType] = None,
    ) -> Optional[ReviewTask]:
        """领取下一个待处理任务"""
        ...

    @abstractmethod
    def complete_task(
        self,
        task_id: int,
        status: ReviewTaskStatus,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        model: str = "",
        prompt_version: str = "",
    ) -> bool:
        """完成任务"""
        ...

    @abstractmethod
    def requeue_stale_tasks(
        self,
        max_age_minutes: int = 10,
    ) -> int:
        """重新入队超时任务"""
        ...

    @abstractmethod
    def get_task_stats(self) -> Dict[str, int]:
        """获取任务统计"""
        ...

    @abstractmethod
    def upsert_merge_decision(
        self,
        decision: MergeDecision,
    ) -> int:
        """创建或更新合并决策"""
        ...

    @abstractmethod
    def get_merge_decision_by_hash(
        self,
        input_hash: str,
    ) -> Optional[MergeDecision]:
        """根据 input_hash 获取决策"""
        ...

    @abstractmethod
    def list_merge_decisions(
        self,
        decision_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[MergeDecision]:
        """列出合并决策"""
        ...


# =============================================================================
# Unified Store（统一仓储接口）
# =============================================================================


class UnifiedStore(
    EntityStore,
    EventStore,
    RelationStore,
    ParticipantStore,
    EventEdgeStore,
    MentionStore,
    ReviewStore,
    ABC,
):
    """
    统一仓储端口：
    组合所有子仓储接口，提供完整的持久化能力。
    """

    @abstractmethod
    def get_schema_version(self) -> str:
        """获取当前 schema 版本"""
        ...

    @abstractmethod
    def export_compat_json_files(self) -> Dict[str, str]:
        """导出兼容 JSON 文件"""
        ...

    @abstractmethod
    def export_entities_json(self) -> Dict[str, Any]:
        """导出实体 JSON"""
        ...

    @abstractmethod
    def export_abstract_map_json(self) -> Dict[str, Any]:
        """导出事件摘要映射 JSON"""
        ...

    @abstractmethod
    def begin_transaction(self) -> Any:
        """开始事务"""
        ...

    @abstractmethod
    def commit_transaction(self, tx: Any) -> None:
        """提交事务"""
        ...

    @abstractmethod
    def rollback_transaction(self, tx: Any) -> None:
        """回滚事务"""
        ...
