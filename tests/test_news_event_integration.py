#!/usr/bin/env python3
"""
测试新闻处理与事件映射集成
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.sqlite.store import get_store


def simulate_news_processing():
    """模拟新闻处理流程"""
    print("🔄 模拟新闻处理流程")
    
    # 获取 store 实例
    store = get_store()
    
    # 模拟新闻数据
    news_data = {
        "id": "test_news_001",
        "source": "test_source",
        "title": "测试新闻标题",
        "content": "这是测试新闻的内容，包含一些重要的事件信息。",
        "timestamp": "2025-12-19T10:00:00Z"
    }
    
    # 模拟提取的事件数据
    extracted_events = [
        {
            "abstract": "测试事件1",
            "event_summary": "这是一个测试事件的摘要",
            "entities": ["实体A", "实体B"],
            "entities_original": ["Entity A", "Entity B"],
            "event_types": ["测试类型"],
        },
        {
            "abstract": "测试事件2",
            "event_summary": "这是另一个测试事件的摘要",
            "entities": ["实体C", "实体D"],
            "entities_original": ["Entity C", "Entity D"],
            "event_types": ["测试类型2"],
        }
    ]
    
    # 构造新闻全局ID
    global_news_id = f"{news_data['source']}:{news_data['id']}"
    print(f"📰 处理新闻: {global_news_id}")
    
    # 模拟事件存储过程
    print("💾 存储提取的事件...")
    try:
        store.upsert_events(extracted_events, source=news_data['source'], reported_at=news_data['timestamp'])
        print("✅ 事件存储成功")
    except Exception as e:
        print(f"❌ 事件存储失败: {e}")
        return False
    
    # 获取存储的事件ID（通过事件摘要计算）
    event_mappings = []
    for event in extracted_events:
        # 计算事件ID（与SQLiteStore中的canonical_event_id一致）
        abstract = event["abstract"]
        event_id = __import__('hashlib').sha1(f"evt:{abstract}".encode("utf-8")).hexdigest()
        event_mappings.append((global_news_id, event_id))
        print(f"  - 事件: {abstract} -> ID: {event_id}")
    
    # 存储新闻ID到事件ID的映射
    print("🔗 存储新闻到事件的映射关系...")
    try:
        count = store.add_news_event_mappings(event_mappings)
        print(f"✅ 成功存储 {count} 个映射关系")
    except Exception as e:
        print(f"❌ 映射关系存储失败: {e}")
        return False
    
    # 验证映射关系
    print("🔍 验证映射关系...")
    try:
        # 根据新闻ID查询事件ID
        event_ids = store.get_events_by_news_id(global_news_id)
        print(f"  通过新闻ID {global_news_id} 查询到 {len(event_ids)} 个事件ID: {event_ids}")
        
        # 根据事件ID查询新闻ID
        if event_ids:
            news_ids = store.get_news_by_event_id(event_ids[0])
            print(f"  通过事件ID {event_ids[0]} 查询到 {len(news_ids)} 个新闻ID: {news_ids}")
        
        return True
    except Exception as e:
        print(f"❌ 映射关系验证失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 开始测试新闻处理与事件映射集成")
    
    try:
        success = simulate_news_processing()
        if success:
            print("\n✅ 集成测试通过!")
            return 0
        else:
            print("\n❌ 集成测试失败!")
            return 1
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())