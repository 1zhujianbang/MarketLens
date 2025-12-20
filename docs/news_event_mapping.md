# 新闻ID到事件ID映射功能说明

## 概述

本功能用于建立新闻ID与事件ID之间的映射关系，方便追踪哪些新闻产生了哪些事件，以及哪些事件来源于哪些新闻。

## 数据库表结构

### news_event_mapping 表

```sql
CREATE TABLE IF NOT EXISTS news_event_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_global_id TEXT NOT NULL,     -- 新闻全局ID (格式: source:id)
    event_id TEXT NOT NULL,           -- 事件ID (SHA1哈希值)
    created_at TEXT NOT NULL,         -- 创建时间
    UNIQUE(news_global_id, event_id)  -- 确保映射关系唯一
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_news_event_mapping_news ON news_event_mapping(news_global_id);
CREATE INDEX IF NOT EXISTS idx_news_event_mapping_event ON news_event_mapping(event_id);
CREATE INDEX IF NOT EXISTS idx_news_event_mapping_created_at ON news_event_mapping(created_at);
```

## 核心功能

### 1. 添加映射关系

```python
from src.app.business.news_event_mapper import store_news_event_mappings

# 存储新闻ID到事件ID的映射
news_global_id = "source_name:news_id"
extracted_events = [...]  # 从新闻中提取的事件列表
success = store_news_event_mappings(news_global_id, extracted_events)
```

### 2. 查询映射关系

```python
from src.app.business.news_event_mapper import get_events_by_news_id, get_news_by_event_id

# 根据新闻ID查询关联的事件ID
event_ids = get_events_by_news_id("source_name:news_id")

# 根据事件ID查询关联的新闻ID
news_ids = get_news_by_event_id("event_sha1_hash")
```

## 在新闻处理流程中的集成

### 1. 在 `process_news_pipeline` 函数中集成

在 `src/app/business/extraction.py` 文件的 `process_news_pipeline` 函数中，在调用 `update_abstract_map` 后添加映射关系存储：

```python
# 在提取事件后添加映射关系存储
from src.app.business.news_event_mapper import store_news_event_mappings

if all_entities and len(all_entities) == len(all_entities_original):
    update_entities(all_entities, all_entities_original, source, published_at)
    update_abstract_map(extracted, source, published_at)
    
    # 添加新闻到事件的映射关系
    store_news_event_mappings(global_id, extracted)
    
    total_processed += 1
    # ... rest of existing code ...
```

### 2. 在 `batch_process_news` 函数中集成

在 `src/app/business/extraction.py` 文件的 `batch_process_news` 函数中，在处理完每个新闻后添加映射关系存储：

```python
# 在提取事件后添加映射关系存储
from src.app.business.news_event_mapper import store_news_event_mappings

# ... in process_one function ...
for ev in extracted:
    ev["source"] = source
    ev["published_at"] = timestamp
    ev["news_id"] = news.get("id")
    events_out.append(ev)

# 如果有处理ID，则存储映射关系
if processed_id and extracted:
    store_news_event_mappings(processed_id, extracted)

# ... rest of existing code ...
```

## 使用示例

```python
# 示例：处理新闻并建立映射关系
news_data = {
    "id": "news_001",
    "source": "example_source",
    "title": "示例新闻",
    "content": "新闻内容...",
    "timestamp": "2025-12-19T10:00:00Z"
}

extracted_events = [
    {
        "abstract": "示例事件1",
        "event_summary": "事件摘要",
        "entities": ["实体A", "实体B"],
        # ... other fields
    }
]

# 构造新闻全局ID
global_news_id = f"{news_data['source']}:{news_data['id']}"

# 存储映射关系
from src.app.business.news_event_mapper import store_news_event_mappings
store_news_event_mappings(global_news_id, extracted_events)

# 查询映射关系
from src.app.business.news_event_mapper import get_events_by_news_id
event_ids = get_events_by_news_id(global_news_id)
print(f"新闻 {global_news_id} 产生的事件: {event_ids}")
```

## 注意事项

1. **事件ID计算**：事件ID通过 `canonical_event_id` 函数计算，与SQLiteStore中的一致
2. **批量操作**：推荐使用批量操作提高性能
3. **错误处理**：所有操作都有适当的异常处理
4. **唯一性约束**：数据库层面确保映射关系的唯一性