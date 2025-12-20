"""
Review Tools: 审查工具（薄封装调用 ReviewService）

这是 Interfaces 层的示例：
- 工具只做薄封装，核心逻辑在 Application/Domain 层
- 保持向后兼容 @register_tool 的使用方式
"""
from __future__ import annotations

from typing import Any, Dict

from ...infra.registry import register_tool


# =============================================================================
# 实体审查工具
# =============================================================================


@register_tool(
    name="enqueue_entity_merge_candidates_v2",
    description="[V2] 生成实体合并候选并入队（调用 ReviewService）",
    category="Review",
)
def enqueue_entity_merge_candidates_v2(
    min_similarity: float = 0.92,
    max_pairs: int = 200,
) -> Dict[str, Any]:
    """
    生成实体合并候选。
    
    这是 Interfaces 层的薄封装，实际逻辑委托给现有的 review_ops。
    未来可以替换为调用 ReviewService。
    """
    # 暂时委托给现有实现
    from ...app.business.review_ops import enqueue_entity_merge_candidates
    return enqueue_entity_merge_candidates(
        min_similarity=min_similarity,
        max_pairs=max_pairs,
    )


@register_tool(
    name="run_entity_review_worker_v2",
    description="[V2] 运行实体审查 worker（调用 ReviewService）",
    category="Review",
)
def run_entity_review_worker_v2(
    max_tasks: int = 20,
    rate_limit_per_sec: float = 0.5,
) -> Dict[str, Any]:
    """运行实体审查 worker。"""
    from ...app.business.review_ops import run_review_worker
    return run_review_worker(
        task_type="entity_merge_review",
        max_tasks=max_tasks,
        rate_limit_per_sec=rate_limit_per_sec,
    )


@register_tool(
    name="apply_entity_merges_v2",
    description="[V2] 应用实体合并决策（调用 ReviewService）",
    category="Review",
)
def apply_entity_merges_v2(
    max_actions: int = 50,
) -> Dict[str, Any]:
    """应用实体合并决策。"""
    from ...app.business.review_ops import apply_entity_merge_decisions
    return apply_entity_merge_decisions(max_actions=max_actions)


# =============================================================================
# 事件审查工具
# =============================================================================


@register_tool(
    name="enqueue_event_merge_candidates_v2",
    description="[V2] 生成事件合并/演化候选并入队",
    category="Review",
)
def enqueue_event_merge_candidates_v2(
    max_pairs: int = 200,
    shared_entity_min: int = 2,
    days_window: int = 14,
) -> Dict[str, Any]:
    """生成事件合并/演化候选。"""
    from ...app.business.review_ops import enqueue_event_merge_or_evolve_candidates
    return enqueue_event_merge_or_evolve_candidates(
        max_pairs=max_pairs,
        shared_entity_min=shared_entity_min,
        days_window=days_window,
    )


@register_tool(
    name="run_event_review_worker_v2",
    description="[V2] 运行事件审查 worker",
    category="Review",
)
def run_event_review_worker_v2(
    max_tasks: int = 20,
    rate_limit_per_sec: float = 0.5,
) -> Dict[str, Any]:
    """运行事件审查 worker。"""
    from ...app.business.review_ops import run_review_worker
    return run_review_worker(
        task_type="event_merge_or_evolve_review",
        max_tasks=max_tasks,
        rate_limit_per_sec=rate_limit_per_sec,
    )


@register_tool(
    name="apply_event_decisions_v2",
    description="[V2] 应用事件审查决策（merge/evolve）",
    category="Review",
)
def apply_event_decisions_v2(
    max_actions: int = 50,
) -> Dict[str, Any]:
    """应用事件审查决策。"""
    from ...app.business.review_ops import apply_event_merge_or_evolve_decisions
    return apply_event_merge_or_evolve_decisions(max_actions=max_actions)


# =============================================================================
# 端到端工具
# =============================================================================


@register_tool(
    name="review_entities_end_to_end_v2",
    description="[V2] 端到端实体审查：生成候选→LLM审查→应用合并",
    category="Review",
)
def review_entities_end_to_end_v2(
    min_similarity: float = 0.92,
    max_pairs: int = 200,
    max_review_tasks: int = 30,
    rate_limit_per_sec: float = 0.5,
    max_apply: int = 30,
) -> Dict[str, Any]:
    """端到端实体审查。"""
    from ...app.business.review_ops import review_entity_merges_end_to_end
    return review_entity_merges_end_to_end(
        min_similarity=min_similarity,
        max_pairs=max_pairs,
        max_review_tasks=max_review_tasks,
        rate_limit_per_sec=rate_limit_per_sec,
        max_apply=max_apply,
    )


@register_tool(
    name="get_review_stats_v2",
    description="[V2] 获取审查队列统计",
    category="Review",
)
def get_review_stats_v2() -> Dict[str, Any]:
    """获取审查队列统计。"""
    from ...app.business.review_ops import review_queue_stats
    return review_queue_stats()
