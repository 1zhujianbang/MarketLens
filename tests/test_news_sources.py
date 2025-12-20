#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试新闻源扩展脚本

该脚本用于验证新闻源是否已成功扩展到10个以上。
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_news_sources():
    """测试新闻源扩展"""
    print("=== 测试新闻源扩展 ===")
    
    # 测试NewsAPIManager
    print("\n--- 测试NewsAPIManager ---")
    try:
        from src.adapters.news.api_manager import NewsAPIManager
        manager = NewsAPIManager()
        sources = manager.list_sources()
        print(f"NewsAPIManager注册的源数量: {len(sources)}")
        print("注册的源列表:")
        for i, source in enumerate(sources, 1):
            print(f"  {i}. {source}")
        
        if len(sources) >= 10:
            print("✅ NewsAPIManager成功扩展到10个以上新闻源")
        else:
            print("❌ NewsAPIManager未达到10个以上新闻源")
    except Exception as e:
        print(f"❌ NewsAPIManager测试失败: {e}")
    
    # 测试前端默认配置
    print("\n--- 测试前端默认配置 ---")
    try:
        from src.web.utils import get_default_api_sources_df
        df = get_default_api_sources_df()
        print(f"前端默认配置的源数量: {len(df)}")
        print("前端默认配置的源列表:")
        for i, (_, row) in enumerate(df.iterrows(), 1):
            print(f"  {i}. {row['name']} ({row['language']}/{row['country']})")
        
        if len(df) >= 10:
            print("✅ 前端默认配置成功扩展到10个以上新闻源")
        else:
            print("❌ 前端默认配置未达到10个以上新闻源")
    except Exception as e:
        print(f"❌ 前端默认配置测试失败: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_news_sources()