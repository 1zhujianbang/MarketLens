#!/usr/bin/env python3
"""
手动下载语义相似度模型

用于解决 Hugging Face 网络连接问题

使用镜像源（在 PowerShell 启动时设置）：
``` powershell
# 添加到 PowerShell 配置文件
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def download_with_mirror():
    """使用镜像源下载模型"""
    print("=" * 80)
    print("语义模型下载工具")
    print("=" * 80)
    print()
    
    model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
    
    print(f"\n📦 准备下载模型: {model_name}")
    print(f"   大小: 约420MB")
    print()
    
    # 提供镜像选项
    print("请选择下载源：")
    print("  1. 官方源（huggingface.co）- 国外网络")
    print("  2. 镜像源（hf-mirror.com）- 国内推荐 ⭐")
    print("  3. 退出")
    print()
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    if choice == "3":
        print("已取消")
        return False
    
    # ⚠️ 关键修复：必须在导入 sentence_transformers 之前设置环境变量
    if choice == "2":
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        print("\n✅ 已切换到镜像源: https://hf-mirror.com")
    else:
        # 清除镜像设置（如果有）
        os.environ.pop('HF_ENDPOINT', None)
        print("\n使用官方源: https://huggingface.co")
    
    # 现在才导入 sentence_transformers
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("❌ sentence-transformers 未安装")
        print("   安装命令: pip install sentence-transformers")
        return False
    
    print(f"\n开始下载... 请耐心等待")
    print("-" * 80)
    
    try:
        # 下载模型
        model = SentenceTransformer(model_name)
        
        print("-" * 80)
        print(f"✅ 模型下载成功！")
        print(f"   缓存位置: {model._model_card_vars.get('model_path', 'Unknown')}")
        print()
        
        # 测试模型
        print("🧪 测试模型...")
        test_result = model.encode(["测试文本", "test text"])
        print(f"✅ 模型测试成功！嵌入维度: {test_result.shape}")
        print()
        
        return True
        
    except Exception as e:
        print("-" * 80)
        print(f"❌ 下载失败: {e}")
        print()
        print("可能的解决方案：")
        print("  1. 检查网络连接")
        print("  2. 使用代理: set HTTP_PROXY=http://your-proxy:port")
        print("  3. 重试选择镜像源（选项2）")
        print("  4. 手动下载（见下方说明）")
        print()
        return False


def show_manual_download_guide():
    """显示手动下载指南"""
    print("=" * 80)
    print("手动下载指南")
    print("=" * 80)
    print()
    print("如果自动下载失败，可以手动下载模型：")
    print()
    print("方法1：使用镜像站下载")
    print("-" * 80)
    print("1. 访问镜像站: https://hf-mirror.com/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print("2. 点击 'Files and versions' 标签")
    print("3. 下载所有文件到本地目录")
    print("4. 放置到缓存目录:")
    print("   Windows: %USERPROFILE%\\.cache\\huggingface\\hub\\")
    print("            models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2\\")
    print()
    
    print("方法2：使用 Git LFS")
    print("-" * 80)
    print("1. 安装 Git LFS: https://git-lfs.github.com/")
    print("2. 克隆模型仓库:")
    print("   git clone https://hf-mirror.com/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    print("3. 移动到缓存目录（同上）")
    print()
    
    print("方法3：禁用语义匹配")
    print("-" * 80)
    print("如果不需要跨语言匹配功能，可以暂时禁用：")
    print("  pip uninstall sentence-transformers")
    print("  系统会自动降级到字符串匹配（不影响其他功能）")
    print()


def check_model_exists():
    """检查模型是否已存在"""
    try:
        from sentence_transformers import SentenceTransformer
        from pathlib import Path
        
        # 检查缓存目录
        cache_home = Path.home() / '.cache' / 'huggingface' / 'hub'
        model_dir = cache_home / 'models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2'
        
        if model_dir.exists():
            print(f"✅ 发现已缓存的模型: {model_dir}")
            print()
            
            # 尝试加载
            try:
                model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                print("✅ 模型加载成功！")
                
                # 测试
                test_result = model.encode(["测试", "test"])
                print(f"✅ 模型测试成功！嵌入维度: {test_result.shape}")
                return True
            except Exception as e:
                print(f"⚠️ 模型加载失败: {e}")
                return False
        else:
            print(f"ℹ️ 未找到缓存模型")
            print(f"   预期位置: {model_dir}")
            return False
            
    except Exception as e:
        print(f"检查失败: {e}")
        return False


def main():
    """主函数"""
    print()
    print("🚀 语义模型下载工具")
    print()
    
    # 先检查是否已存在
    print("检查模型缓存...")
    print("-" * 80)
    if check_model_exists():
        print()
        print("=" * 80)
        print("✅ 模型已就绪，无需下载！")
        print("=" * 80)
        return
    
    print()
    
    # 尝试下载
    success = download_with_mirror()
    
    if not success:
        print()
        show_manual_download_guide()
    else:
        print()
        print("=" * 80)
        print("✅ 模型下载完成！可以开始使用语义匹配功能了")
        print("=" * 80)
        print()
        print("测试命令: python tests/test_semantic_matcher.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
