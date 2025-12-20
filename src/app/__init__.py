"""
应用服务层（Application Layer）。

原则：
- 这里承载"用例/服务"编排：入库、审查、投影、导出等。
- 这里不直接做 UI，不直接暴露 @register_tool；tool 应该是薄封装，调用 app 服务。

服务接口：
- IngestionService: 新闻入库（抓取→抽取→落 mention/canonical）
- ReviewService: 审查流程（候选生成→LLM裁决→执行→审计）
- KnowledgeGraphService: 图谱服务（refresh/export/snapshot）
"""
#
# 重要：保持本模块"零副作用"，避免在 import app.* 时引入 utils/llm/core 的重型依赖，
# 从而导致循环导入（例如 core -> app -> utils.llm_utils -> agents.api_client -> core）。
#
# 请直接从子模块导入需要的服务，例如：
# - from src.app.services import IngestionService, ReviewService, KnowledgeGraphService
# - from src.app.snapshot_service import SnapshotService
# - from src.app.pipeline.engine import PipelineEngine

# 服务接口（启用导入）
from .services import (
    ServiceResult,
    BaseService,
    IngestionConfig,
    IngestionResult,
    IngestionService,
    ReviewConfig,
    ReviewResult,
    ReviewService,
    SnapshotConfig,
    KGRefreshResult,
    SnapshotResult,
    KnowledgeGraphService,
)

# 服务实现
from .services_impl import (
    IngestionServiceImpl,
    ReviewServiceImpl,
    KnowledgeGraphServiceImpl,
    get_ingestion_service,
    get_review_service,
    get_kg_service,
)

__all__ = [
    # 接口
    "ServiceResult",
    "BaseService",
    "IngestionConfig",
    "IngestionResult",
    "IngestionService",
    "ReviewConfig",
    "ReviewResult",
    "ReviewService",
    "SnapshotConfig",
    "KGRefreshResult",
    "SnapshotResult",
    "KnowledgeGraphService",
    # 实现
    "IngestionServiceImpl",
    "ReviewServiceImpl",
    "KnowledgeGraphServiceImpl",
    "get_ingestion_service",
    "get_review_service",
    "get_kg_service",
]

