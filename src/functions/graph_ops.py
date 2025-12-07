from typing import List, Dict, Any, Optional
from ..core.registry import register_tool
from ..utils.entity_updater import update_entities, update_abstract_map
from ..agents.agent3 import refresh_graph as _refresh_graph

@register_tool(
    name="update_graph_data",
    description="将提取的事件数据写入知识图谱文件 (Entities & Events)",
    category="Knowledge Graph"
)
def update_graph_data(events_list: List[Dict[str, Any]], default_source: str = "auto_pipeline") -> Dict[str, Any]:
    """
    更新知识图谱数据文件。
    
    Args:
        events_list: 事件列表，每项应包含 entities, abstract 等，以及可选的 source, published_at
        default_source: 默认来源标识
        
    Returns:
        更新状态
    """
    count = 0
    for event in events_list:
        entities = event.get("entities", [])
        entities_original = event.get("entities_original", [])
        # 如果没有原始形式，回退到实体名
        if not entities_original:
            entities_original = entities
            
        source = event.get("source", default_source)
        published_at = event.get("published_at")
        
        # 更新实体库
        update_entities(entities, entities_original, source, published_at)
        count += 1
        
    # 更新事件映射 (abstract_map)
    # update_abstract_map 期望的是 events_list，但其中的 item 需要有 source 和 published_at
    # 如果 event 字典里已经有这些字段，update_abstract_map 内部怎么处理？
    # 查看 entity_updater.py:
    #   def update_abstract_map(extracted_list, source, published_at):
    # 它接受一个 source 和 published_at 参数，统一应用于所有 item。
    # 这对于批量处理不同来源的事件不太友好。
    # 我们可以稍微 hack 一下：循环调用 update_abstract_map，或者修改 update_abstract_map。
    # 为了不修改原有 util，我们按 source 分组调用。
    
    # 简单的按个调用 (效率稍低但安全)
    for event in events_list:
        src = event.get("source", default_source)
        ts = event.get("published_at")
        update_abstract_map([event], src, ts)
    
    return {"status": "success", "updated_count": count}

@register_tool(
    name="refresh_knowledge_graph",
    description="重建并压缩知识图谱 (触发 Agent3 逻辑)",
    category="Knowledge Graph"
)
def refresh_knowledge_graph() -> Dict[str, str]:
    """
    刷新知识图谱：构建、压缩、更新
    """
    try:
        _refresh_graph()
        return {"status": "refreshed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

