#!/usr/bin/env python3
"""
新闻ID到事件ID映射使用示例
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app.business.news_event_mapper import store_news_event_mappings, get_events_by_news_id, get_news_by_event_id


def example_news_processing():
    """新闻处理示例"""
    print("📝 新闻处理与事件映射示例")
    
    # 模拟新闻数据
    news_data = {
        "id": "example_news_001",
        "source": "example_source",
        "title": "示例新闻标题",
        "content": "这是示例新闻的内容，包含一些重要的事件信息。",
        "timestamp": "2025-12-19T15:30:00Z"
    }
    
    # 模拟从新闻中提取的事件
    extracted_events = [
        {
            "abstract": "示例事件1",
            "event_summary": "这是第一个示例事件的摘要",
            "entities": ["公司A", "公司B"],
            "entities_original": ["Company A", "Company B"],
            "event_types": ["商业合作"],
        },
        {
            "abstract": "示例事件2",
            "event_summary": "这是第二个示例事件的摘要",
            "entities": ["政府机构C", "公司D"],
            "entities_original": ["Government Agency C", "Company D"],
            "event_types": ["政策发布"],
        }
    ]
    
    # 构造新闻全局ID
    global_news_id = f"{news_data['source']}:{news_data['id']}"
    print(f"📰 处理新闻: {global_news_id}")
    
    # 存储事件到数据库（这通常在 update_abstract_map 中完成）
    print("💾 存储提取的事件到数据库...")
    # 注意：在实际应用中，这一步由 update_abstract_map 函数完成
    # 我们在这里只是演示流程
    
    # 存储新闻ID到事件ID的映射关系
    print("🔗 建立新闻到事件的映射关系...")
    success = store_news_event_mappings(global_news_id, extracted_events)
    
    if success:
        print("✅ 映射关系建立成功")
        
        # 查询示例
        print("\n🔍 查询示例:")
        
        # 1. 根据新闻ID查询关联的事件
        print(f"1. 查询新闻 {global_news_id} 关联的事件:")
        event_ids = get_events_by_news_id(global_news_id)
        for i, event_id in enumerate(event_ids, 1):
            print(f"   事件{i} ID: {event_id}")
        
        # 2. 根据事件ID查询关联的新闻
        if event_ids:
            print(f"\n2. 查询事件 {event_ids[0]} 关联的新闻:")
            news_ids = get_news_by_event_id(event_ids[0])
            for i, news_id in enumerate(news_ids, 1):
                print(f"   新闻{i} ID: {news_id}")
        
        return True
    else:
        print("❌ 映射关系建立失败")
        return False


def main():
    """主函数"""
    print("🚀 新闻ID到事件ID映射使用示例")
    print("=" * 50)
    
    try:
        success = example_news_processing()
        if success:
            print("\n🎉 示例执行成功!")
            return 0
        else:
            print("\n💥 示例执行失败!")
            return 1
    except Exception as e:
        print(f"\n💥 示例执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())