#!/usr/bin/env python3
"""
新闻ID到事件ID映射处理模块
"""

import hashlib
from typing import List, Tuple, Dict, Any
from src.adapters.sqlite.store import get_store


def canonical_event_id(abstract: str) -> str:
    """
    计算事件的标准ID，与SQLiteStore中的实现保持一致
    
    Args:
        abstract: 事件摘要
        
    Returns:
        事件的标准ID
    """
    a = (abstract or "").strip()
    return hashlib.sha1(f"evt:{a}".encode("utf-8")).hexdigest()


def store_news_event_mappings(news_global_id: str, extracted_events: List[Dict[str, Any]]) -> bool:
    """
    存储新闻ID到事件ID的映射关系
    
    Args:
        news_global_id: 新闻的全局ID (格式: source:id)
        extracted_events: 提取的事件列表
        
    Returns:
        是否存储成功
    """
    try:
        # 获取 store 实例
        store = get_store()
        
        # 构造映射关系
        event_mappings = []
        for event in extracted_events:
            # 计算事件ID
            abstract = event.get("abstract", "")
            if not abstract:
                continue
                
            event_id = canonical_event_id(abstract)
            event_mappings.append((news_global_id, event_id))
        
        # 批量存储映射关系
        if event_mappings:
            count = store.add_news_event_mappings(event_mappings)
            print(f"✅ 成功存储 {count} 个新闻到事件的映射关系")
            return True
        else:
            print("ℹ️  没有有效的事件需要建立映射关系")
            return True
            
    except Exception as e:
        print(f"❌ 存储新闻事件映射关系失败: {e}")
        return False


def get_events_by_news_id(news_global_id: str) -> List[str]:
    """
    根据新闻ID获取关联的所有事件ID
    
    Args:
        news_global_id: 新闻的全局ID
        
    Returns:
        关联的事件ID列表
    """
    try:
        store = get_store()
        return store.get_events_by_news_id(news_global_id)
    except Exception as e:
        print(f"❌ 查询新闻关联事件失败: {e}")
        return []


def get_news_by_event_id(event_id: str) -> List[str]:
    """
    根据事件ID获取关联的所有新闻ID
    
    Args:
        event_id: 事件ID
        
    Returns:
        关联的新闻ID列表
    """
    try:
        store = get_store()
        return store.get_news_by_event_id(event_id)
    except Exception as e:
        print(f"❌ 查询事件关联新闻失败: {e}")
        return []