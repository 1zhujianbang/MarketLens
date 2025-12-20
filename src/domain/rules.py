"""
业务规则接口（Domain Rules）：
纯函数式规则，不做 IO，只描述"如何判断/如何合并/如何演化"。

这些接口由 Application 层调用，实际实现可以是规则引擎或 LLM。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    EntityCanonical,
    EntityMention,
    EventCanonical,
    EventEdge,
    EventEdgeType,
    EventMention,
    MergeDecision,
    RelationTriple,
)


# =============================================================================
# 候选生成规则（Candidate Generation）
# =============================================================================


class CandidateReason(Enum):
    """候选生成原因"""
    ORIGINAL_FORMS_MATCH = "original_forms_match"  # 原始形式匹配
    NAME_SIMILARITY = "name_similarity"  # 名称相似
    SHARED_ENTITIES = "shared_entities"  # 共享实体
    TEMPORAL_PROXIMITY = "temporal_proximity"  # 时间接近
    SIMHASH_MATCH = "simhash_match"  # SimHash 相似
    VECTOR_SIMILARITY = "vector_similarity"  # 向量相似


@dataclass
class EntityMergeCandidatePair:
    """实体合并候选对"""
    entity_a: str  # entity_id 或 name
    entity_b: str
    similarity: float
    reason: CandidateReason
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class EventMergeCandidatePair:
    """事件合并/演化候选对"""
    event_a_id: str
    event_a_abstract: str
    event_b_id: str
    event_b_abstract: str
    shared_entities: int
    temporal_distance_hours: Optional[float] = None
    reason: CandidateReason = CandidateReason.SHARED_ENTITIES
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CandidateGenerator(ABC):
    """
    候选生成器接口：
    生成实体/事件合并候选对，供 Adjudicator 裁决。
    """

    @abstractmethod
    def generate_entity_merge_candidates(
        self,
        entities: List[EntityCanonical],
        min_similarity: float = 0.92,
        max_pairs: int = 200,
    ) -> List[EntityMergeCandidatePair]:
        """生成实体合并候选对"""
        ...

    @abstractmethod
    def generate_event_merge_candidates(
        self,
        events: List[EventCanonical],
        shared_entity_min: int = 2,
        days_window: int = 14,
        max_pairs: int = 200,
    ) -> List[EventMergeCandidatePair]:
        """生成事件合并/演化候选对"""
        ...


# =============================================================================
# 裁决规则（Adjudication）
# =============================================================================


class MergeVerdict(Enum):
    """合并裁决结果"""
    MERGE = "merge"
    SEPARATE = "separate"
    EVOLVE = "evolve"  # 仅用于事件


@dataclass
class EntityMergeVerdict:
    """实体合并裁决"""
    verdict: MergeVerdict
    canonical_name: str = ""
    confidence: float = 0.0
    reasons: List[str] = None
    evidence: List[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.evidence is None:
            self.evidence = []

    @property
    def should_merge(self) -> bool:
        return self.verdict == MergeVerdict.MERGE


@dataclass
class EventMergeVerdict:
    """事件合并/演化裁决"""
    verdict: MergeVerdict
    canonical_abstract: str = ""  # merge 时的规范摘要
    edge_type: Optional[EventEdgeType] = None  # evolve 时的边类型
    confidence: float = 0.0
    reasons: List[str] = None
    evidence: List[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.evidence is None:
            self.evidence = []

    @property
    def should_merge(self) -> bool:
        return self.verdict == MergeVerdict.MERGE

    @property
    def should_create_edge(self) -> bool:
        return self.verdict == MergeVerdict.EVOLVE


class Adjudicator(ABC):
    """
    裁决器接口：
    对候选对进行最终裁决（可以是规则引擎、向量相似度、或 LLM）。
    """

    @abstractmethod
    def adjudicate_entity_merge(
        self,
        entity_a: EntityCanonical,
        entity_b: EntityCanonical,
        context: Optional[Dict[str, Any]] = None,
    ) -> EntityMergeVerdict:
        """裁决两个实体是否应合并"""
        ...

    @abstractmethod
    def adjudicate_event_merge_or_evolve(
        self,
        event_a: EventCanonical,
        event_b: EventCanonical,
        context: Optional[Dict[str, Any]] = None,
    ) -> EventMergeVerdict:
        """裁决两个事件是 merge/evolve/separate"""
        ...


# =============================================================================
# 应用规则（Application Rules - Applier）
# =============================================================================


@dataclass
class MergeAction:
    """合并动作描述"""
    from_id: str
    to_id: str
    reason: str
    decision_input_hash: str = ""
    executed_at: Optional[datetime] = None
    success: bool = False
    error: Optional[str] = None


@dataclass
class EdgeCreationAction:
    """边创建动作描述"""
    from_event_id: str
    to_event_id: str
    edge_type: EventEdgeType
    time: datetime
    confidence: float
    evidence: List[str]
    decision_input_hash: str = ""
    executed_at: Optional[datetime] = None
    success: bool = False
    error: Optional[str] = None


class Applier(ABC):
    """
    应用器接口：
    执行合并/边创建动作，保证幂等性。
    """

    @abstractmethod
    def apply_entity_merge(
        self,
        from_entity_id: str,
        to_entity_id: str,
        reason: str,
        decision_input_hash: str = "",
    ) -> MergeAction:
        """执行实体合并（幂等）"""
        ...

    @abstractmethod
    def apply_event_merge(
        self,
        from_event_id: str,
        to_event_id: str,
        reason: str,
        decision_input_hash: str = "",
    ) -> MergeAction:
        """执行事件合并（幂等）"""
        ...

    @abstractmethod
    def apply_event_edge(
        self,
        from_event_id: str,
        to_event_id: str,
        edge_type: EventEdgeType,
        time: datetime,
        confidence: float,
        evidence: List[str],
        decision_input_hash: str = "",
    ) -> EdgeCreationAction:
        """创建事件演化边（幂等）"""
        ...


# =============================================================================
# Resolution 规则（Mention -> Canonical）
# =============================================================================


@dataclass
class ResolutionResult:
    """解析结果"""
    mention_id: str
    resolved_id: Optional[str] = None  # canonical id
    confidence: float = 1.0
    is_new: bool = False  # 是否为新建的 canonical
    reason: str = ""


class MentionResolver(ABC):
    """
    Mention 解析器接口：
    将 mention 解析到 canonical entity/event。
    """

    @abstractmethod
    def resolve_entity_mention(
        self,
        mention: EntityMention,
        existing_entities: List[EntityCanonical],
    ) -> ResolutionResult:
        """解析实体 mention"""
        ...

    @abstractmethod
    def resolve_event_mention(
        self,
        mention: EventMention,
        existing_events: List[EventCanonical],
    ) -> ResolutionResult:
        """解析事件 mention"""
        ...


# =============================================================================
# 纯函数式规则（无状态）
# =============================================================================


def normalize_entity_name(name: str) -> str:
    """规范化实体名称（用于比较/索引）"""
    s = (name or "").strip().lower()
    # 去掉常见分隔符
    for ch in [" ", "\t", "\n", "\r", "·", "•", "-", "_", ".", ",", "，", "。",
               "（", "）", "(", ")", "[", "]", "{", "}", "\"", "'"]:
        s = s.replace(ch, "")
    return s


def compute_name_similarity(a: str, b: str) -> float:
    """计算名称相似度（SequenceMatcher）"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, normalize_entity_name(a), normalize_entity_name(b)).ratio()


def select_canonical_name(name_a: str, name_b: str, preferred: Optional[str] = None) -> str:
    """
    选择规范名称：
    1. 如果 preferred 等于其中一个，选 preferred
    2. 否则选更长/更完整的
    """
    if preferred:
        if preferred == name_a:
            return name_a
        if preferred == name_b:
            return name_b
    return name_a if len(name_a) >= len(name_b) else name_b


def select_canonical_event(
    event_a: EventCanonical,
    event_b: EventCanonical,
    preferred_abstract: Optional[str] = None,
) -> Tuple[EventCanonical, EventCanonical]:
    """
    选择规范事件（to, from）：
    返回 (canonical_event, duplicate_event)
    """
    if preferred_abstract:
        if preferred_abstract == event_a.abstract:
            return event_a, event_b
        if preferred_abstract == event_b.abstract:
            return event_b, event_a
    # 默认选更早创建的
    if event_a.first_seen and event_b.first_seen:
        if event_a.first_seen <= event_b.first_seen:
            return event_a, event_b
        else:
            return event_b, event_a
    # 或选摘要更长的
    if len(event_a.abstract) >= len(event_b.abstract):
        return event_a, event_b
    return event_b, event_a


def merge_entity_sources(
    sources_a: List[Any],
    sources_b: List[Any],
) -> List[Any]:
    """合并实体来源（去重）"""
    seen = set()
    result = []
    for src_list in [sources_a, sources_b]:
        for src in src_list:
            if isinstance(src, dict):
                key = (src.get("id", ""), src.get("url", ""))
            else:
                key = str(src)
            if key not in seen:
                seen.add(key)
                result.append(src)
    return result


def merge_original_forms(
    forms_a: List[str],
    forms_b: List[str],
) -> List[str]:
    """合并原始形式（去重）"""
    seen = set()
    result = []
    for f in forms_a + forms_b:
        if isinstance(f, str) and f.strip():
            key = normalize_entity_name(f)
            if key not in seen:
                seen.add(key)
                result.append(f.strip())
    return result


def validate_time_constraint(time_val: Optional[datetime]) -> bool:
    """验证时间约束（time 必须非空）"""
    return time_val is not None
