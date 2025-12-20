"""
src.functions 包 - 委托层

已迁移模块：
- 所有业务逻辑 -> app/business/

本模块保留以兼容旧代码。
"""
import sys

# 子模块别名 - 支持 `import src.functions.data_fetch` 等导入方式
from ..app.business import data_fetch
from ..app.business import extraction
from ..app.business import graph_ops
from ..app.business import reporting
from ..app.business import review_ops
from ..app.business import migration

# 注册子模块别名到 sys.modules
sys.modules['src.functions.data_fetch'] = data_fetch
sys.modules['src.functions.extraction'] = extraction
sys.modules['src.functions.graph_ops'] = graph_ops
sys.modules['src.functions.reporting'] = reporting
sys.modules['src.functions.review_ops'] = review_ops
sys.modules['src.functions.migration'] = migration

# 从 app/business 重导出
from ..app.business import *  # noqa: F401, F403
from ..app.business.extraction import (
    NewsDeduplicator,
    llm_extract_events,
    persist_expanded_news_to_tmp,
)
from ..app.business.review_ops import (
    enqueue_entity_merge_candidates,
    enqueue_event_merge_or_evolve_candidates,
    run_review_worker,
    apply_entity_merge_decisions,
    apply_event_merge_or_evolve_decisions,
    review_entity_merges_end_to_end,
    review_queue_stats,
)
from ..app.business.graph_ops import (
    update_graph_data,
    refresh_knowledge_graph,
    generate_kg_visual_snapshots,
)
from ..app.business.data_fetch import (
    fetch_news_stream,
)
from ..app.business.migration import (
    migrate_json_to_sqlite,
    backfill_mentions,
)
from ..app.business.reporting import (
    generate_markdown_report,
)

