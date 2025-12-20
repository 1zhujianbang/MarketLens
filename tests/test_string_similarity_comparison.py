#!/usr/bin/env python3
"""
测试字符串相似度算法对比
对比旧算法（SequenceMatcher）和新算法（混合策略）
"""

import sys
from pathlib import Path
from difflib import SequenceMatcher

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def old_similarity(a: str, b: str) -> float:
    """旧算法：简单的 SequenceMatcher"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def new_similarity(a: str, b: str) -> float:
    """新算法：混合策略 + 语义匹配（从 graph_ops.py 复制）"""
    import re
    
    # 快速路径：完全相同
    if a == b:
        return 1.0
    
    # 归一化：去除空格、标点、转小写
    def normalize(s: str) -> str:
        s = re.sub(r'[^\w]', '', s, flags=re.UNICODE)
        return s.lower()
    
    a_norm = normalize(a)
    b_norm = normalize(b)
    
    # 归一化后相同
    if a_norm and b_norm and a_norm == b_norm:
        return 0.98
    
    # 尝试导入Jaro-Winkler
    try:
        from jellyfish import jaro_winkler_similarity
        jw_score = jaro_winkler_similarity(a.lower(), b.lower())
    except ImportError:
        jw_score = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    # 中英文混合实体：尝试语义匹配
    def is_chinese(text: str) -> bool:
        return any('\u4e00' <= ch <= '\u9fff' for ch in text)
    
    a_is_chinese = is_chinese(a)
    b_is_chinese = is_chinese(b)
    
    if a_is_chinese != b_is_chinese:
        # 一个中文一个英文：尝试语义匹配
        try:
            # 导入语义匹配器
            sys.path.insert(0, str(project_root / 'src'))
            from infra.semantic_matcher import get_semantic_matcher
            semantic_matcher = get_semantic_matcher()
            if semantic_matcher.is_available():
                semantic_score = semantic_matcher.similarity(a, b)
                if semantic_score is not None:
                    # 语义相似度70%权重 + 字符串相似度30%权重
                    return semantic_score * 0.7 + jw_score * 0.3
        except Exception:
            pass
        
        # 如果语义匹配不可用，降权70%
        return jw_score * 0.3
    
    return jw_score


def test_entity_pairs():
    """测试常见实体对"""
    test_cases = [
        # (实体A, 实体B, 期望结果, 描述)
        
        # ===== 应该合并的案例（高相似度）=====
        ("Apple Inc.", "Apple Inc", True, "标点差异"),
        ("Goldman Sachs", "Goldman Sach", True, "拼写变体"),
        ("New York Times", "The New York Times", True, "冠词差异"),
        ("IBM Corporation", "IBM Corp.", True, "缩写"),
        ("Microsoft Corporation", "Microsoft Corp", True, "缩写"),
        ("中国工商银行", "中国工商银行股份有限公司", True, "中文全称vs简称"),
        
        # ===== 不应该合并的案例（低相似度）=====
        ("民众党", "布朗大学", False, "完全不相关（日志中的错误案例）"),
        ("民众党", "京都府八幡市", False, "政党 vs 地名"),
        ("民众党", "葡萄牙", False, "政党 vs 国家"),
        ("民众党", "麻省理工学院", False, "政党 vs 大学"),
        ("Apple", "Orange", False, "不同公司"),
        ("Google", "Microsoft", False, "不同公司"),
        
        # ===== 中英文混合（应该低相似度）=====
        ("苹果公司", "Apple Inc.", False, "中英翻译（字符串算法无法识别）"),
        ("纽约时报", "New York Times", False, "中英翻译"),
        ("高盛集团", "Goldman Sachs", False, "中英翻译"),
    ]
    
    print("=" * 80)
    print("字符串相似度算法对比测试")
    print("=" * 80)
    print(f"{'实体A':<25} {'实体B':<25} {'旧算法':<8} {'新算法':<8} {'期望':<8} {'结果'}")
    print("-" * 80)
    
    passed = 0
    failed = 0
    threshold = 0.93  # 预聚类阈值
    
    for a, b, should_match, desc in test_cases:
        old_score = old_similarity(a, b)
        new_score = new_similarity(a, b)
        
        # 判断是否会被预聚类分组
        old_would_match = old_score >= threshold
        new_would_match = new_score >= threshold
        
        # 检查新算法是否符合期望
        if new_would_match == should_match:
            result = "✅"
            passed += 1
        else:
            result = "❌"
            failed += 1
        
        print(f"{a:<25} {b:<25} {old_score:>6.2f}   {new_score:>6.2f}   {'Y' if should_match else 'N':<8} {result}  {desc}")
    
    print("-" * 80)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 80)
    
    # 关键改进分析
    print("\n📊 关键改进分析：")
    print("\n1. **日志中的错误案例**（不应合并的）：")
    problematic_pairs = [
        ("民众党", "布朗大学"),
        ("民众党", "京都府八幡市"),
        ("民众党", "葡萄牙"),
        ("民众党", "麻省理工学院"),
    ]
    
    for a, b in problematic_pairs:
        old = old_similarity(a, b)
        new = new_similarity(a, b)
        print(f"   {a} vs {b}:")
        print(f"      旧算法: {old:.3f} ({'会触发' if old >= threshold else '不会触发'}预聚类)")
        print(f"      新算法: {new:.3f} ({'会触发' if new >= threshold else '不会触发'}预聚类)")
    
    print("\n2. **应该合并的案例**（缩写/变体）：")
    valid_pairs = [
        ("Apple Inc.", "Apple Inc"),
        ("Goldman Sachs", "Goldman Sach"),
        ("IBM Corporation", "IBM Corp."),
    ]
    
    for a, b in valid_pairs:
        old = old_similarity(a, b)
        new = new_similarity(a, b)
        print(f"   {a} vs {b}:")
        print(f"      旧算法: {old:.3f} ({'会触发' if old >= threshold else '不会触发'}预聚类)")
        print(f"      新算法: {new:.3f} ({'会触发' if new >= threshold else '不会触发'}预聚类)")
    
    return passed, failed


if __name__ == "__main__":
    print("🚀 开始测试字符串相似度算法改进\n")
    
    # 检查是否安装了 jellyfish
    try:
        import jellyfish
        print("✅ 已安装 jellyfish，使用 Jaro-Winkler 算法\n")
    except ImportError:
        print("⚠️ 未安装 jellyfish，降级到 SequenceMatcher\n")
        print("   安装命令: pip install jellyfish\n")
    
    passed, failed = test_entity_pairs()
    
    if failed == 0:
        print("\n✅ 所有测试通过！新算法显著改进了实体相似度判断。")
    else:
        print(f"\n⚠️ {failed} 个测试失败，需要进一步调整阈值或算法。")
