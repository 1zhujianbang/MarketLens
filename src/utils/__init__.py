"""
工具模块集合 - 委托层

已迁移模块：
- tool_function.py -> infra/paths.py
- llm_utils.py -> infra/async_utils.py
- data_utils.py -> domain/data_operations.py
- data_ops.py -> domain/data_ops.py
- news_fetch_utils.py -> adapters/news/fetch_utils.py

本模块保留以兼容旧代码。
"""

# 从 domain 重导出数据操作
from ..domain.data_ops import (
    merge_entity_data,
    merge_event_data,
    validate_entity_data,
    validate_event_data,
    cleanup_duplicate_entities,
    cleanup_duplicate_events,
    backup_data_file,
    restore_from_backup,
    write_jsonl_file,
    read_jsonl_file,
    write_json_file,
    read_json_file,
    sanitize_datetime_fields,
    create_temp_file_path,
    update_entities,
    update_abstract_map,
)

# 从 adapters/news 重导出新闻获取工具
from ..adapters.news.fetch_utils import (
    normalize_news_items,
    fetch_from_collector,
    fetch_from_multiple_sources,
)

__all__ = [
    # Data operations
    "merge_entity_data",
    "merge_event_data",
    "validate_entity_data",
    "validate_event_data",
    "cleanup_duplicate_entities",
    "cleanup_duplicate_events",
    "backup_data_file",
    "restore_from_backup",
    "write_jsonl_file",
    "read_jsonl_file",
    "write_json_file",
    "read_json_file",
    "sanitize_datetime_fields",
    "create_temp_file_path",
    "update_entities",
    "update_abstract_map",
    # News fetch utils
    "normalize_news_items",
    "fetch_from_collector",
    "fetch_from_multiple_sources",
]
