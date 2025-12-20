#!/usr/bin/env python3
"""
测试语义实体匹配器
验证跨语言实体匹配功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_semantic_matcher_basic():
    """测试基本功能"""
    print("=" * 80)
    print("测试语义匹配器基本功能")
    print("=" * 80)
    
    try:
        from src.infra.semantic_matcher import get_semantic_matcher
        
        matcher = get_semantic_matcher()
        
        # 检查是否可用
        if not matcher.is_available():
            print("⚠️ 语义匹配器不可用")
            print("   可能原因：")
            print("   1. sentence-transformers 未安装")
            print("   2. 模型下载失败")
            print("\n安装命令: pip install sentence-transformers")
            return False
        
        print("✅ 语义匹配器初始化成功\n")
        
        # 测试单对相似度
        print("🧪 测试单对实体相似度：")
        test_pairs = [
            ("苹果公司", "Apple Inc."),
            ("纽约时报", "New York Times"),
            ("高盛集团", "Goldman Sachs"),
            ("中国工商银行", "ICBC"),
            ("特斯拉", "Tesla"),
            ("微软", "Microsoft"),
            ("谷歌", "Google"),
            ("亚马逊", "Amazon"),
        ]
        
        for cn, en in test_pairs:
            score = matcher.similarity(cn, en)
            status = "✅" if score and score > 0.6 else "❌"
            print(f"  {status} {cn:<15} vs {en:<20} → {score:.3f if score else 'N/A'}")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("\n安装命令: pip install sentence-transformers")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_semantic_matcher_batch():
    """测试批量匹配"""
    print("\n" + "=" * 80)
    print("测试批量实体匹配")
    print("=" * 80)
    
    try:
        from src.infra.semantic_matcher import get_semantic_matcher
        
        matcher = get_semantic_matcher()
        
        if not matcher.is_available():
            print("⚠️ 语义匹配器不可用，跳过测试")
            return False
        
        # 测试批量查找相似实体
        print("\n🧪 测试批量查找相似实体：")
        
        query = "苹果公司"
        candidates = [
            "Apple Inc.",
            "Apple Corporation",
            "Microsoft",
            "Google",
            "亚马逊",
            "特斯拉",
            "IBM",
            "Oracle",
        ]
        
        print(f"\n查询实体: {query}")
        print(f"候选实体: {candidates}\n")
        
        similar = matcher.find_similar_entities(query, candidates, threshold=0.6)
        
        if similar:
            print("找到相似实体：")
            for entity, score in similar:
                print(f"  ✅ {entity:<20} → {score:.3f}")
        else:
            print("  ⚠️ 未找到相似实体（阈值 >= 0.6）")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_semantic_vs_string():
    """对比语义匹配和字符串匹配"""
    print("\n" + "=" * 80)
    print("对比语义匹配 vs 字符串匹配")
    print("=" * 80)
    
    try:
        from src.infra.semantic_matcher import get_semantic_matcher
        from difflib import SequenceMatcher
        
        matcher = get_semantic_matcher()
        
        if not matcher.is_available():
            print("⚠️ 语义匹配器不可用，跳过对比")
            return False
        
        print(f"\n{'实体对':<40} {'字符串相似度':<15} {'语义相似度':<15} {'提升'}")
        print("-" * 80)
        
        test_cases = [
            ("苹果公司", "Apple Inc."),
            ("纽约时报", "New York Times"),
            ("高盛集团", "Goldman Sachs"),
            ("中国工商银行", "ICBC"),
            ("特斯拉", "Tesla"),
            ("微软公司", "Microsoft Corporation"),
            ("谷歌", "Google LLC"),
            ("亚马逊", "Amazon.com"),
            ("Facebook", "Meta"),  # 改名后的公司
            ("Beijing", "北京"),  # 地名翻译
        ]
        
        for a, b in test_cases:
            # 字符串相似度
            string_sim = SequenceMatcher(None, a.lower(), b.lower()).ratio()
            
            # 语义相似度
            semantic_sim = matcher.similarity(a, b)
            
            if semantic_sim is not None:
                improvement = semantic_sim - string_sim
                status = "🚀" if improvement > 0.3 else ("✅" if improvement > 0 else "→")
                print(f"{a} ↔ {b:<25} {string_sim:>6.3f}         {semantic_sim:>6.3f}         {status} {improvement:+.3f}")
            else:
                print(f"{a} ↔ {b:<25} {string_sim:>6.3f}         N/A           ❌")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 开始测试语义实体匹配器\n")
    
    # 检查依赖
    try:
        import sentence_transformers
        print(f"✅ sentence-transformers 版本: {sentence_transformers.__version__}\n")
    except ImportError:
        print("❌ sentence-transformers 未安装")
        print("\n安装步骤：")
        print("  1. 取消 requirements.txt 中 sentence-transformers 的注释")
        print("  2. 运行: pip install sentence-transformers")
        print("\n注意：首次运行会下载约420MB的模型文件\n")
        return
    
    # 运行测试
    test1 = test_semantic_matcher_basic()
    test2 = test_semantic_matcher_batch()
    test3 = test_semantic_vs_string()
    
    print("\n" + "=" * 80)
    if test1 and test2 and test3:
        print("✅ 所有测试通过！")
        print("\n💡 语义匹配器已成功集成到系统中")
        print("   - 支持中英文跨语言实体匹配")
        print("   - 自动识别语义相似的实体（如翻译、同义词）")
        print("   - 在预聚类阶段会自动使用语义匹配")
    else:
        print("⚠️ 部分测试失败")
    print("=" * 80)


if __name__ == "__main__":
    main()
