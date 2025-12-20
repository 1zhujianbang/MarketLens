#!/usr/bin/env python3
"""
完整集成测试：新闻处理与事件映射
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.sqlite.store import get_store
from src.app.business.news_event_mapper import (
    store_news_event_mappings,
    get_events_by_news_id,
    get_news_by_event_id,
    canonical_event_id
)


def test_full_integration():
    """完整集成测试"""
    print("🧪 完整集成测试：新闻处理与事件映射")
    
    # 获取 store 实例
    store = get_store()
    
    # 模拟新闻数据
    news_data = {
        "id": "integration_test_001",
        "source": "test_source",
        "title": "集成测试新闻",
        "content": "这是用于集成测试的新闻内容，包含一些事件信息。",
        "timestamp": "2025-12-19T20:00:00Z"
    }
    
    # 模拟提取的事件
    extracted_events = [
        {
            "abstract": "集成测试事件A",
            "event_summary": "集成测试事件A的摘要",
            "entities": ["测试实体1", "测试实体2"],
            "entities_original": ["Test Entity 1", "Test Entity 2"],
            "event_types": ["测试类型A"],
        },
        {
            "abstract": "集成测试事件B",
            "event_summary": "集成测试事件B的摘要",
            "entities": ["测试实体3", "测试实体4"],
            "entities_original": ["Test Entity 3", "Test Entity 4"],
            "event_types": ["测试类型B"],
        }
    ]
    
    # 构造新闻全局ID
    global_news_id = f"{news_data['source']}:{news_data['id']}"
    print(f"📰 处理新闻: {global_news_id}")
    
    # 1. 模拟事件存储（在实际应用中由 update_abstract_map 完成）
    print("💾 存储事件到数据库...")
    try:
        store.upsert_events(extracted_events, source=news_data['source'], reported_at=news_data['timestamp'])
        print("✅ 事件存储成功")
    except Exception as e:
        print(f"❌ 事件存储失败: {e}")
        return False
    
    # 2. 存储新闻到事件的映射关系
    print("🔗 存储新闻到事件的映射关系...")
    try:
        success = store_news_event_mappings(global_news_id, extracted_events)
        if success:
            print("✅ 映射关系存储成功")
        else:
            print("❌ 映射关系存储失败")
            return False
    except Exception as e:
        print(f"❌ 映射关系存储异常: {e}")
        return False
    
    # 3. 验证映射关系
    print("🔍 验证映射关系...")
    
    # 3.1 根据新闻ID查询事件ID
    try:
        event_ids = get_events_by_news_id(global_news_id)
        print(f"  通过新闻ID查询到 {len(event_ids)} 个事件ID")
        if len(event_ids) != len(extracted_events):
            print(f"  ❌ 事件数量不匹配：期望 {len(extracted_events)}，实际 {len(event_ids)}")
            return False
            
        # 验证事件ID是否正确
        expected_event_ids = [canonical_event_id(ev["abstract"]) for ev in extracted_events]
        for expected_id in expected_event_ids:
            if expected_id not in event_ids:
                print(f"  ❌ 缺少事件ID: {expected_id}")
                return False
        print("  ✅ 事件ID验证通过")
    except Exception as e:
        print(f"  ❌ 新闻ID查询异常: {e}")
        return False
    
    # 3.2 根据事件ID查询新闻ID
    try:
        if event_ids:
            news_ids = get_news_by_event_id(event_ids[0])
            print(f"  通过事件ID查询到 {len(news_ids)} 个新闻ID")
            if global_news_id not in news_ids:
                print(f"  ❌ 缺少新闻ID: {global_news_id}")
                return False
            print("  ✅ 新闻ID验证通过")
    except Exception as e:
        print(f"  ❌ 事件ID查询异常: {e}")
        return False
    
    # 4. 测试重复插入
    print("🔄 测试重复插入...")
    try:
        success = store_news_event_mappings(global_news_id, extracted_events)
        if success:
            print("✅ 重复插入处理正确（无重复记录）")
        else:
            print("❌ 重复插入处理失败")
            return False
    except Exception as e:
        print(f"❌ 重复插入测试异常: {e}")
        return False
    
    print("🎉 所有测试通过!")
    return True


def main():
    """主函数"""
    print("🚀 开始完整集成测试")
    print("=" * 50)
    
    try:
        success = test_full_integration()
        if success:
            print("\n✅ 集成测试成功!")
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