#!/usr/bin/env python3
"""
数据存储库初始化/重置脚本

将所有数据存储恢复到空白默认状态：
- 清空 data/ 目录下的运行数据
- 重置配置文件为空白状态
- 保留目录结构

使用方法:
    python scripts/reset_data.py [--force]
    
参数:
    --force: 跳过确认提示，直接执行重置
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"


def get_utc_now_iso() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ============================================================================
# 默认空白状态定义
# ============================================================================

DEFAULT_ENTITY_MERGE_RULES = {
    "merge_rules": {},
    "last_updated": None  # 将在重置时填充
}

# 知识图谱相关的空白默认值
# （已移除JSON相关默认值，使用SQLite存储）

# 需要清空内容但保留目录的路径（相对于 DATA_DIR）
DIRS_TO_CLEAR = [
    "projects/default/cache/pyvis",
    "projects/default/runs",
    "projects/default/evidence",
    "snapshots",
    "logs",
    "tmp/raw_news",
    "tmp/deduped_news",
]

# 需要删除的文件（相对于 DATA_DIR）
FILES_TO_DELETE = [
    "store.sqlite",
    "store.sqlite-wal",
    "store.sqlite-shm",
]

# 需要清空的文本文件（相对于 DATA_DIR）
TEXT_FILES_TO_CLEAR = [
    "stop_words.txt",
]

# 需要重置的配置文件（相对于 CONFIG_DIR）
# （已移除JSON相关配置，使用SQLite存储）
CONFIG_FILES_TO_RESET = {}


def clear_text_file(file_path: Path, verbose: bool = True) -> bool:
    """清空文本文件内容"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('')
        if verbose:
            print(f"  清空文件: {file_path.name}")
        return True
    except Exception as e:
        print(f"  警告: 无法清空 {file_path}: {e}")
        return False


# （已移除JSON文件重置功能，使用SQLite存储）


def clear_directory(dir_path: Path, verbose: bool = True) -> int:
    """
    清空目录内容但保留目录本身
    
    Returns:
        删除的项目数量
    """
    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
        return 0
    
    count = 0
    for item in dir_path.iterdir():
        try:
            if item.is_file():
                item.unlink()
                count += 1
                if verbose:
                    print(f"  删除文件: {item.name}")
            elif item.is_dir():
                shutil.rmtree(item)
                count += 1
                if verbose:
                    print(f"  删除目录: {item.name}/")
        except Exception as e:
            print(f"  警告: 无法删除 {item}: {e}")
    
    return count


def delete_file(file_path: Path, verbose: bool = True) -> bool:
    """删除单个文件"""
    if not file_path.exists():
        return False
    
    try:
        file_path.unlink()
        if verbose:
            print(f"  删除文件: {file_path.name}")
        return True
    except Exception as e:
        print(f"  警告: 无法删除 {file_path}: {e}")
        return False


def reset_config_file(file_path: Path, default_content: dict, verbose: bool = True) -> bool:
    """重置配置文件为默认内容（已简化，不再处理JSON）"""
    try:
        # 更新时间戳
        content = default_content.copy()
        if "last_updated" in content:
            content["last_updated"] = get_utc_now_iso()
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件（简化处理）
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("")  # 空文件即可
        
        if verbose:
            print(f"  重置配置: {file_path.name}")
        return True
    except Exception as e:
        print(f"  警告: 无法重置 {file_path}: {e}")
        return False


def ensure_directory_structure():
    """确保基本目录结构存在"""
    required_dirs = [
        DATA_DIR / "projects" / "default" / "cache" / "pyvis",
        DATA_DIR / "projects" / "default" / "runs",
        DATA_DIR / "projects" / "default" / "evidence",
        DATA_DIR / "snapshots",
        DATA_DIR / "logs",
        DATA_DIR / "tmp" / "raw_news",
        DATA_DIR / "tmp" / "deduped_news",
        DATA_DIR / "config" / "templates",
    ]
    
    for dir_path in required_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)


def get_data_stats() -> dict:
    """获取当前数据状态统计"""
    stats = {
        "sqlite_size": 0,
        "cache_files": 0,
        "run_files": 0,
        "snapshot_files": 0,
        "log_files": 0,
        "merge_rules_count": 0,
        "processed_ids_count": 0,
        "entities_count": 0,
        "kg_nodes_count": 0,
    }
    
    # SQLite 数据库大小
    sqlite_path = DATA_DIR / "store.sqlite"
    if sqlite_path.exists():
        stats["sqlite_size"] = sqlite_path.stat().st_size
    
    # 缓存文件数
    cache_dir = DATA_DIR / "projects" / "default" / "cache" / "pyvis"
    if cache_dir.exists():
        stats["cache_files"] = len(list(cache_dir.iterdir()))
    
    # 运行记录数
    runs_dir = DATA_DIR / "projects" / "default" / "runs"
    if runs_dir.exists():
        stats["run_files"] = len(list(runs_dir.iterdir()))
    
    # 快照数
    snapshots_dir = DATA_DIR / "snapshots"
    if snapshots_dir.exists():
        stats["snapshot_files"] = len(list(snapshots_dir.iterdir()))
    
    # 日志文件数
    logs_dir = DATA_DIR / "logs"
    if logs_dir.exists():
        stats["log_files"] = len(list(logs_dir.iterdir()))
    
    # 合并规则数（已移除JSON处理，使用SQLite存储）
    stats["merge_rules_count"] = 0
    
    # 已处理ID数（从数据库获取）
    try:
        from ..src.adapters.sqlite.store import get_store
        processed_ids = get_store().get_processed_ids()
        stats["processed_ids_count"] = len(processed_ids)
    except:
        pass
    
    # 实体数量和知识图谱节点数量（从数据库获取）
    try:
        from ..src.adapters.sqlite.store import get_store
        store = get_store()
        # 获取实体数量
        entities = store.get_entities(limit=1)  # 只获取一个实体来测试连接
        if entities:
            # 如果能获取到实体，尝试获取实际数量
            try:
                conn = store._connect()
                result = conn.execute("SELECT COUNT(*) as count FROM entities").fetchone()
                stats["entities_count"] = result["count"] if result else 0
                conn.close()
            except:
                stats["entities_count"] = 0
        else:
            stats["entities_count"] = 0
            
        # 获取知识图谱节点数量
        try:
            conn = store._connect()
            result = conn.execute("SELECT COUNT(*) as count FROM entities").fetchone()
            stats["kg_nodes_count"] = result["count"] if result else 0
            conn.close()
        except:
            stats["kg_nodes_count"] = 0
    except:
        stats["entities_count"] = 0
        stats["kg_nodes_count"] = 0
    
    return stats


def print_stats(stats: dict, title: str = "当前数据状态"):
    """打印数据统计"""
    print(f"\n{title}:")
    print(f"  - SQLite 数据库: {stats['sqlite_size'] / 1024:.1f} KB")
    print(f"  - 缓存文件: {stats['cache_files']} 个")
    print(f"  - 运行记录: {stats['run_files']} 个")
    print(f"  - 快照文件: {stats['snapshot_files']} 个")
    print(f"  - 日志文件: {stats['log_files']} 个")
    print(f"  - 实体合并规则: {stats['merge_rules_count']} 条")
    print(f"  - 实体数量: {stats['entities_count']} 个")
    print(f"  - 知识图谱节点: {stats['kg_nodes_count']} 个")
    print(f"  - 已处理新闻ID: {stats['processed_ids_count']} 条")


def reset_all(verbose: bool = True) -> dict:
    """
    执行完整重置
    
    Returns:
        重置统计信息
    """
    results = {
        "dirs_cleared": 0,
        "files_deleted": 0,
        "text_files_cleared": 0,
        "configs_reset": 0,
    }
    
    print("\n" + "=" * 50)
    print("开始重置数据存储库...")
    print("=" * 50)
    
    # 1. 清空目录
    print("\n[1/4] 清空数据目录...")
    for rel_path in DIRS_TO_CLEAR:
        dir_path = DATA_DIR / rel_path
        if verbose:
            print(f"\n  目录: {rel_path}/")
        count = clear_directory(dir_path, verbose=verbose)
        if count > 0:
            results["dirs_cleared"] += 1
    
    # 2. 删除数据库文件
    print("\n[2/4] 删除数据库文件...")
    for rel_path in FILES_TO_DELETE:
        file_path = DATA_DIR / rel_path
        if delete_file(file_path, verbose=verbose):
            results["files_deleted"] += 1
    
    # 3. 清空文本文件
    print("\n[3/4] 清空文本数据文件...")
    for rel_path in TEXT_FILES_TO_CLEAR:
        file_path = DATA_DIR / rel_path
        if clear_text_file(file_path, verbose=verbose):
            results["text_files_cleared"] += 1
    
    # 4. 重置配置文件
    print("\n[4/4] 重置配置文件...")
    for filename, default_content in CONFIG_FILES_TO_RESET.items():
        file_path = CONFIG_DIR / filename
        if reset_config_file(file_path, default_content, verbose=verbose):
            results["configs_reset"] += 1
    
    # 确保目录结构完整
    ensure_directory_structure()
    
    print("\n" + "=" * 50)
    print("重置完成!")
    print("=" * 50)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="重置数据存储库到空白默认状态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/reset_data.py          # 交互式重置
    python scripts/reset_data.py --force  # 跳过确认直接重置
    python scripts/reset_data.py --stats  # 仅显示当前状态
        """
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="跳过确认提示，直接执行重置"
    )
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="仅显示当前数据状态，不执行重置"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，减少输出"
    )
    
    args = parser.parse_args()
    
    # 显示当前状态
    before_stats = get_data_stats()
    
    if args.stats:
        print_stats(before_stats)
        return 0
    
    print_stats(before_stats, "重置前状态")
    
    # 确认操作
    if not args.force:
        print("\n⚠️  警告: 此操作将删除所有数据，无法恢复!")
        response = input("确定要继续吗? [y/N]: ").strip().lower()
        if response not in ('y', 'yes'):
            print("已取消操作。")
            return 1
    
    # 执行重置
    results = reset_all(verbose=not args.quiet)
    
    # 显示重置后状态
    after_stats = get_data_stats()
    print_stats(after_stats, "重置后状态")
    
    print(f"\n统计: 清空 {results['dirs_cleared']} 个目录, "
          f"删除 {results['files_deleted']} 个数据库文件, "
          f"清空 {results['text_files_cleared']} 个文本文件, "
          f"重置 {results['configs_reset']} 个配置")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
