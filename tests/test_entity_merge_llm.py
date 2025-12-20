#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试LLM实体合并决策器
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.adapters.extraction.entity_merge_llm import (
    LLMEntityMergeDecider, 
    EntityMergeDecision,
    EntityAnalysis,
    MergeGroup,
    EntityType
)
from src.adapters.llm.pool import DefaultLLMPool


def test_entity_merge_decider():
    """测试实体合并决策器"""
    print("=== 测试LLM实体合并决策器 ===")
    
    # 初始化LLM池
    llm_pool = DefaultLLMPool()
    
    # 创建决策器
    decider = LLMEntityMergeDecider(llm_pool)
    
    # 测试案例1: 媒体名称合并
    print("\n--- 测试案例1: 媒体名称合并 ---")
    entities1 = ["New York Times", "《纽约时报》"]
    evidence1 = {
        "New York Times": [
            "New York Times <= New York Times报道了某事件 | New York Times, 某公司 | 摘要内容"
        ],
        "《纽约时报》": [
            "《纽约时报》 <= 《纽约时报》报道了某事件 | 《纽约时报》, 某公司 | 摘要内容"
        ]
    }
    
    decision1 = decider.decide_entity_merges(entities1, evidence1)
    print(f"实体列表: {entities1}")
    print(f"决策结果: {decision1}")
    
    # 输出详细分析
    print("实体分析:")
    for analysis in decision1.entity_analyses:
        print(f"  - {analysis.entity}: 类型={analysis.entity_type.value}, 置信度={analysis.confidence}, 理由={analysis.reasoning}")
    
    print("合并组:")
    for group in decision1.merge_groups:
        print(f"  - 主实体: {group.primary_entity}")
        print(f"    重复实体: {group.duplicate_entities}")
        print(f"    理由: {group.reason}")
        print(f"    置信度: {group.confidence}")
    
    # 测试案例2: 英文媒体名称合并
    print("\n--- 测试案例2: 英文媒体名称合并 ---")
    entities2 = ["The Times of London", "《泰晤士报》"]
    evidence2 = {
        "The Times of London": [
            "The Times of London <= The Times of London报道了某事件 | The Times of London, 某公司 | 摘要内容"
        ],
        "《泰晤士报》": [
            "《泰晤士报》 <= 《泰晤士报》报道了某事件 | 《泰晤士报》, 某公司 | 摘要内容"
        ]
    }
    
    decision2 = decider.decide_entity_merges(entities2, evidence2)
    print(f"实体列表: {entities2}")
    print(f"决策结果: {decision2}")
    
    # 输出详细分析
    print("实体分析:")
    for analysis in decision2.entity_analyses:
        print(f"  - {analysis.entity}: 类型={analysis.entity_type.value}, 置信度={analysis.confidence}, 理由={analysis.reasoning}")
    
    print("合并组:")
    for group in decision2.merge_groups:
        print(f"  - 主实体: {group.primary_entity}")
        print(f"    重复实体: {group.duplicate_entities}")
        print(f"    理由: {group.reason}")
        print(f"    置信度: {group.confidence}")
    
    # 测试案例3: 不应该合并的实体
    print("\n--- 测试案例3: 不应该合并的实体 ---")
    entities3 = ["Apple Inc.", "iPhone 15 Pro"]
    evidence3 = {
        "Apple Inc.": [
            "Apple Inc.发布新产品 <= Apple Inc.发布了新产品 | Apple Inc., 新产品 | 摘要内容"
        ],
        "iPhone 15 Pro": [
            "iPhone 15 Pro评测 <= 对iPhone 15 Pro的评测 | 评测机构, iPhone 15 Pro | 摘要内容"
        ]
    }
    
    decision3 = decider.decide_entity_merges(entities3, evidence3)
    print(f"实体列表: {entities3}")
    print(f"决策结果: {decision3}")
    
    # 输出详细分析
    print("实体分析:")
    for analysis in decision3.entity_analyses:
        print(f"  - {analysis.entity}: 类型={analysis.entity_type.value}, 置信度={analysis.confidence}, 理由={analysis.reasoning}")
    
    print("合并组:")
    for group in decision3.merge_groups:
        print(f"  - 主实体: {group.primary_entity}")
        print(f"    重复实体: {group.duplicate_entities}")
        print(f"    理由: {group.reason}")
        print(f"    置信度: {group.confidence}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_entity_merge_decider()