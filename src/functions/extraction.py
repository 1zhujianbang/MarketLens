from typing import List, Dict, Any
from ..core.registry import register_tool
from ..agents.agent1 import llm_extract_events as _llm_extract
from ..agents.agent1 import NewsDeduplicator

@register_tool(
    name="extract_entities_events",
    description="使用 LLM 从新闻标题和内容中提取实体和事件",
    category="Information Extraction"
)
def extract_entities_events(title: str, content: str) -> List[Dict[str, Any]]:
    """
    从新闻中提取实体和事件
    
    Args:
        title: 新闻标题
        content: 新闻内容
        
    Returns:
        事件列表，每项包含 entities, event_summary 等
    """
    return _llm_extract(title, content)

@register_tool(
    name="deduplicate_news_batch",
    description="对新闻列表进行批量去重 (基于 SimHash)",
    category="Data Processing"
)
def deduplicate_news_batch(news_list: List[Dict[str, Any]], threshold: int = 3) -> List[Dict[str, Any]]:
    """
    批量去重
    
    Args:
        news_list: 新闻字典列表
        threshold: SimHash 汉明距离阈值
        
    Returns:
        去重后的新闻列表
    """
    if not news_list:
        return []
        
    deduper = NewsDeduplicator(threshold=threshold)
    unique_news = []
    
    for news in news_list:
        # 构造指纹文本
        text = (news.get("title", "") + " " + news.get("content", "")).strip()
        if not text: 
            continue
            
        # 检查重复
        if not deduper.is_duplicate(text):
            unique_news.append(news)
            
    return unique_news

@register_tool(
    name="batch_process_news",
    description="[工作流] 批量处理新闻：去重并提取事件",
    category="Workflow"
)
async def batch_process_news(news_list: List[Dict[str, Any]], limit: int = -1) -> List[Dict[str, Any]]:
    """
    批量处理新闻：
    1. 去重
    2. 提取实体和事件
    3. 附加元数据 (source, published_at)
    
    Args:
        news_list: 新闻列表
        limit: 限制处理的新闻数量，-1 表示不限制。用于测试/节省 Token。
    
    Returns:
        扁平化的事件列表
    """
    # 1. 去重
    unique_news = deduplicate_news_batch(news_list)
    
    all_events = []
    processed_count = 0
    
    # 2. 提取 (串行，因为 llm_extract 是同步且可能限流)
    # 理想情况下应并发控制，但 agent1 内部已经是简单的同步调用
    for news in unique_news:
        # 检查限制
        if limit > 0 and processed_count >= limit:
            print(f"Reached processing limit of {limit}, stopping extraction.")
            break
            
        title = news.get("title", "")
        content = news.get("content", "")
        source = news.get("source", "unknown")
        # 尝试获取时间
        timestamp = news.get("datetime") or news.get("formatted_time")
        
        try:
            print(f"Extracting events from: {title[:30]}...")
            extracted = _llm_extract(title, content)
            
            # 如果提取到了事件，才算作一次有效的“处理”
            # 或者无论是否提取到都算？通常为了节省Token，调用了就算。
            processed_count += 1
            
            for ev in extracted:
                ev["source"] = source
                ev["published_at"] = timestamp
                # 关联原新闻ID
                ev["news_id"] = news.get("id")
                all_events.append(ev)
        except Exception as e:
            print(f"Extraction failed for news {title[:20]}: {e}")
            
    return all_events
