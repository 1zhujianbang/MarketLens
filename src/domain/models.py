"""
领域模型（Domain Models）：纯业务数据结构，不做 IO。

所有模型强制带 time 字段（DDD 时间一致性约束）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Value Objects（值对象）
# =============================================================================


@dataclass(frozen=True)
class SourceRef:
    """来源引用（不可变值对象）"""
    id: str = ""
    name: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "name": self.name, "url": self.url}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceRef":
        return cls(
            id=str(d.get("id") or ""),
            name=str(d.get("name") or ""),
            url=str(d.get("url") or ""),
        )


@dataclass(frozen=True)
class TimePrecision(Enum):
    """时间精度枚举"""
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"
    UNKNOWN = "unknown"


# =============================================================================
# Mention 模型（提及层：先落 mention，再 resolve 到 canonical）
# =============================================================================


@dataclass
class EntityMention:
    """
    实体提及（Mention-first 设计）：
    - 每次抽取产生的原始实体文本
    - 后续通过 resolve 关联到 canonical entity
    """
    mention_id: str
    name_text: str  # 原始提及文本
    reported_at: datetime
    source: SourceRef
    resolved_entity_id: Optional[str] = None  # 关联的 canonical entity_id
    confidence: float = 1.0
    created_at: Optional[datetime] = None

    def is_resolved(self) -> bool:
        return self.resolved_entity_id is not None and self.resolved_entity_id != ""


@dataclass
class EventMention:
    """
    事件提及（Mention-first 设计）：
    - 每次抽取产生的原始事件摘要
    - 后续通过 resolve 关联到 canonical event
    """
    mention_id: str
    abstract_text: str  # 原始事件摘要
    reported_at: datetime
    source: SourceRef
    resolved_event_id: Optional[str] = None  # 关联的 canonical event_id
    confidence: float = 1.0
    created_at: Optional[datetime] = None

    def is_resolved(self) -> bool:
        return self.resolved_event_id is not None and self.resolved_event_id != ""


# =============================================================================
# Canonical 模型（规范化实体/事件）
# =============================================================================


@dataclass
class EntityCanonical:
    """
    规范化实体（Canonical Entity）：
    - 知识图谱中的唯一实体节点
    - 可通过 aliases/redirects 收敛多个 mention
    """
    entity_id: str
    name: str  # 规范名称
    first_seen: datetime
    last_seen: datetime
    sources: List[SourceRef] = field(default_factory=list)
    original_forms: List[str] = field(default_factory=list)  # 别名/原始形式
    aliases: List[str] = field(default_factory=list)  # 已确认的别名

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "first_seen": self.first_seen.isoformat() if self.first_seen else "",
            "last_seen": self.last_seen.isoformat() if self.last_seen else "",
            "sources": [s.to_dict() for s in self.sources],
            "original_forms": self.original_forms,
            "aliases": self.aliases,
        }


@dataclass
class EventCanonical:
    """
    规范化事件（Canonical Event）：
    - 知识图谱中的唯一事件节点
    - 强制带 time 字段
    """
    event_id: str
    abstract: str  # 事件摘要（唯一键）
    event_summary: str
    event_types: List[str] = field(default_factory=list)
    event_start_time: Optional[datetime] = None
    event_start_time_text: str = ""
    event_start_time_precision: str = "unknown"
    reported_at: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    sources: List[SourceRef] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)  # 关联实体名列表
    entity_roles: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def time(self) -> Optional[datetime]:
        """获取事件时间（优先 event_start_time，其次 reported_at/first_seen）"""
        return self.event_start_time or self.reported_at or self.first_seen

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "abstract": self.abstract,
            "event_summary": self.event_summary,
            "event_types": self.event_types,
            "event_start_time": self.event_start_time.isoformat() if self.event_start_time else "",
            "event_start_time_text": self.event_start_time_text,
            "event_start_time_precision": self.event_start_time_precision,
            "reported_at": self.reported_at.isoformat() if self.reported_at else "",
            "first_seen": self.first_seen.isoformat() if self.first_seen else "",
            "last_seen": self.last_seen.isoformat() if self.last_seen else "",
            "sources": [s.to_dict() for s in self.sources],
            "entities": self.entities,
            "entity_roles": self.entity_roles,
        }


# =============================================================================
# 关系模型（强制带 time）
# =============================================================================


@dataclass
class RelationTriple:
    """
    实体-实体关系三元组（强制带 time）：
    - subject -> predicate -> object
    - 必须关联到事件上下文
    """
    id: Optional[int] = None
    event_id: str = ""
    subject_entity_id: str = ""
    predicate: str = ""
    object_entity_id: str = ""
    time: Optional[datetime] = None  # 强制非空
    reported_at: Optional[datetime] = None
    evidence: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """验证关系必须有 time"""
        return (
            self.time is not None
            and self.subject_entity_id != ""
            and self.object_entity_id != ""
            and self.predicate != ""
        )


class EventEdgeType(Enum):
    """事件-事件边类型"""
    FOLLOWS = "follows"  # 顺承
    RESPONDS_TO = "responds_to"  # 回应
    ESCALATES = "escalates"  # 升级
    CAUSES = "causes"  # 因果
    RELATED = "related"  # 一般关联


@dataclass
class EventEdge:
    """
    事件-事件演化边（强制带 time）：
    - from_event -> edge_type -> to_event
    - 用于构建事件演化图谱
    """
    id: Optional[int] = None
    from_event_id: str = ""
    to_event_id: str = ""
    edge_type: EventEdgeType = EventEdgeType.RELATED
    time: Optional[datetime] = None  # 强制非空
    reported_at: Optional[datetime] = None
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    decision_input_hash: str = ""

    def validate(self) -> bool:
        """验证边必须有 time"""
        return (
            self.time is not None
            and self.from_event_id != ""
            and self.to_event_id != ""
        )


# =============================================================================
# 参与关系（实体-事件）
# =============================================================================


@dataclass
class Participant:
    """
    实体参与事件记录（强制带 time）：
    - entity 在 event 中扮演的角色
    """
    id: Optional[int] = None
    event_id: str = ""
    entity_id: str = ""
    roles: List[str] = field(default_factory=list)
    time: Optional[datetime] = None  # 强制非空
    reported_at: Optional[datetime] = None

    def validate(self) -> bool:
        return (
            self.time is not None
            and self.event_id != ""
            and self.entity_id != ""
        )


# =============================================================================
# Review 模型（审查决策）
# =============================================================================


class ReviewTaskStatus(Enum):
    """审查任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ReviewTaskType(Enum):
    """审查任务类型"""
    ENTITY_MERGE_REVIEW = "entity_merge_review"
    EVENT_MERGE_OR_EVOLVE_REVIEW = "event_merge_or_evolve_review"


@dataclass
class ReviewTask:
    """审查任务"""
    task_id: int
    type: ReviewTaskType
    input_hash: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: ReviewTaskStatus = ReviewTaskStatus.PENDING
    priority: int = 50
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    model: str = ""
    prompt_version: str = ""


class MergeDecisionType(Enum):
    """合并决策类型"""
    ENTITY_MERGE = "entity_merge_review"
    EVENT_MERGE_OR_EVOLVE = "event_merge_or_evolve_review"


@dataclass
class MergeDecision:
    """合并决策记录"""
    decision_id: Optional[int] = None
    type: MergeDecisionType = MergeDecisionType.ENTITY_MERGE
    input_hash: str = ""
    output: Dict[str, Any] = field(default_factory=dict)
    model: str = ""
    prompt_version: str = ""
    created_at: Optional[datetime] = None

    # 解析后的决策字段
    @property
    def should_merge(self) -> bool:
        return bool(self.output.get("merge", False))

    @property
    def canonical_name(self) -> str:
        return str(self.output.get("canonical_name", ""))

    @property
    def confidence(self) -> float:
        return float(self.output.get("confidence", 0.0))

    @property
    def reasons(self) -> List[str]:
        return self.output.get("reasons", [])

    @property
    def evidence(self) -> List[str]:
        return self.output.get("evidence", [])
