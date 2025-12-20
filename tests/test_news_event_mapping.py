#!/usr/bin/env python3
"""
测试新闻ID到事件ID映射功能
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.sqlite.store import get_store


def test_news_event_mapping():
    """测试新闻事件映射功能"""
    print("🧪 测试新闻ID到事件ID映射功能")
    
    # 获取 store 实例
    store = get_store()
    
    # 测试数据
    test_mappings = [
        ("news_source:news001", "event_id_1"),
        ("news_source:news001", "event_id_2"),  # 同一个新闻可以关联多个事件
        ("news_source:news002", "event_id_1"),  # 同一个事件可以关联多个新闻
        ("news_source:news003", "event_id_3"),
    ]
    
    print(f"添加 {len(test_mappings)} 个映射关系...")
    count = store.add_news_event_mappings(test_mappings)
    print(f"成功添加 {count} 个新映射关系")
    
    # 查询测试
    print("\n🔍 查询测试:")
    
    # 根据新闻ID查询事件ID
    news_id = "news_source:news001"
    event_ids = store.get_events_by_news_id(news_id)
    print(f"新闻 {news_id} 关联的事件ID: {event_ids}")
    
    # 根据事件ID查询新闻ID
    event_id = "event_id_1"
    news_ids = store.get_news_by_event_id(event_id)
    print(f"事件 {event_id} 关联的新闻ID: {news_ids}")
    
    # 测试重复插入
    print("\n🔄 测试重复插入:")
    duplicate_count = store.add_news_event_mappings(test_mappings[:2])
    print(f"重复插入 {len(test_mappings[:2])} 个映射关系，实际新增: {duplicate_count}")
    
    return True


def main():
    """主函数"""
    print("🚀 开始测试新闻事件映射功能")
    
    try:
        success = test_news_event_mapping()
        if success:
            print("\n✅ 所有测试通过!")
            return 0
        else:
            print("\n❌ 测试失败!")
            return 1
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())