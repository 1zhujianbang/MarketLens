#!/usr/bin/env python3
"""
测试 processed_ids 数据库功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.sqlite.store import get_store


def test_processed_ids_db():
    """测试 processed_ids 数据库功能"""
    print("🧪 测试 processed_ids 数据库功能")
    
    # 获取 store 实例
    store = get_store()
    
    # 获取初始已处理ID数量
    initial_ids = store.get_processed_ids()
    print(f"初始已处理ID数量: {len(initial_ids)}")
    
    # 添加一些测试ID
    test_ids = [
        ("test_source1:12345", "test_source1", "12345"),
        ("test_source2:67890", "test_source2", "67890"),
        ("test_source1:12346", "test_source1", "12346"),
    ]
    
    print(f"添加 {len(test_ids)} 个测试ID...")
    count = store.add_processed_ids(test_ids)
    print(f"成功添加 {count} 个ID")
    
    # 再次获取已处理ID
    updated_ids = store.get_processed_ids()
    print(f"更新后已处理ID数量: {len(updated_ids)}")
    
    # 检查是否包含我们添加的ID
    for global_id, _, _ in test_ids:
        if global_id in updated_ids:
            print(f"✅ ID {global_id} 存在于数据库中")
        else:
            print(f"❌ ID {global_id} 不存在于数据库中")
    
    # 测试重复添加
    print("测试重复添加...")
    count = store.add_processed_ids(test_ids)
    print(f"重复添加返回数量: {count} (应该是0，因为ID已存在)")
    
    # 获取最终已处理ID数量
    final_ids = store.get_processed_ids()
    print(f"最终已处理ID数量: {len(final_ids)}")
    
    print("✅ 测试完成")


if __name__ == "__main__":
    test_processed_ids_db()