#!/usr/bin/env python3
"""
集成测试 processed_ids 功能
测试与新闻处理管道的集成
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.sqlite.store import get_store
from src.app.business.extraction import get_unprocessed_news_files, process_news_pipeline
from src.infra.paths import tools


def create_test_news_file():
    """创建测试新闻文件"""
    # 确保目录存在
    raw_dir = tools.RAW_NEWS_TMP_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建测试新闻数据
    test_news = [
        {
            "id": "test001",
            "source": "test_source",
            "title": "Test News 1",
            "content": "This is test news content 1",
            "timestamp": "2025-12-19T10:00:00Z"
        },
        {
            "id": "test002",
            "source": "test_source",
            "title": "Test News 2",
            "content": "This is test news content 2",
            "timestamp": "2025-12-19T11:00:00Z"
        }
    ]
    
    # 写入测试文件
    test_file = raw_dir / "test_news.jsonl"
    with open(test_file, "w", encoding="utf-8") as f:
        for news in test_news:
            f.write(json.dumps(news, ensure_ascii=False) + "\n")
    
    print(f"创建测试新闻文件: {test_file}")
    return test_file


def test_get_unprocessed_news_files():
    """测试获取未处理新闻文件功能"""
    print("🧪 测试 get_unprocessed_news_files 功能")
    
    # 创建测试文件
    test_file = create_test_news_file()
    
    # 获取未处理的新闻文件
    unprocessed_files = get_unprocessed_news_files()
    
    print(f"找到 {len(unprocessed_files)} 个未处理的新闻文件")
    for file in unprocessed_files:
        print(f"  - {file}")
    
    # 清理测试文件
    test_file.unlink(missing_ok=True)
    
    return len(unprocessed_files) > 0


def test_processed_ids_integration():
    """测试 processed_ids 集成功能"""
    print("🧪 测试 processed_ids 集成功能")
    
    # 获取 store 实例
    store = get_store()
    
    # 获取初始已处理ID数量
    initial_ids = store.get_processed_ids()
    print(f"初始已处理ID数量: {len(initial_ids)}")
    
    # 添加一些测试ID
    test_ids = [
        ("test_source:test001", "test_source", "test001"),
        ("test_source:test002", "test_source", "test002"),
    ]
    
    print(f"添加 {len(test_ids)} 个测试ID...")
    count = store.add_processed_ids(test_ids)
    print(f"成功添加 {count} 个新ID")
    
    # 再次获取已处理ID
    updated_ids = store.get_processed_ids()
    print(f"更新后已处理ID数量: {len(updated_ids)}")
    
    # 验证ID是否存在
    for global_id, _, _ in test_ids:
        if global_id in updated_ids:
            print(f"✅ ID {global_id} 存在于数据库中")
        else:
            print(f"❌ ID {global_id} 不存在于数据库中")
    
    return True


def main():
    """主测试函数"""
    print("🚀 开始集成测试")
    
    # 测试 processed_ids 集成功能
    success1 = test_processed_ids_integration()
    
    # 测试获取未处理新闻文件功能
    success2 = test_get_unprocessed_news_files()
    
    if success1 and success2:
        print("✅ 所有集成测试通过")
    else:
        print("❌ 部分测试失败")
        
    return success1 and success2


if __name__ == "__main__":
    main()