"""
基础设施层 - 路径与工具函数

提供项目路径配置、日志记录和基础工具函数。
从 utils/tool_function.py 迁移。
"""

import os
import sys
import re
import threading
import hashlib
from typing import Set
from datetime import datetime
from pathlib import Path

from .singleton import SingletonBase


class ProjectPaths(SingletonBase):
    """项目路径与工具函数管理器"""
    
    # ======================
    # 路径与配置（类变量，可通过类直接访问）
    # ======================
    
    # 基础路径（类变量）
    ROOT_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = ROOT_DIR / "data"
    CONFIG_DIR = ROOT_DIR / "config"
    DATA_TMP_DIR = DATA_DIR / "tmp"
    RAW_NEWS_TMP_DIR = DATA_TMP_DIR / "raw_news"
    DEDUPED_NEWS_TMP_DIR = DATA_TMP_DIR / "deduped_news"
    LOG_FILE = DATA_DIR / "logs" / "agent1.log"
    
    # 数据文件（类变量）
    # 兼容旧版JSON文件路径（用于导出兼容）
    ENTITIES_FILE = DATA_DIR / "entities.json"
    EVENTS_FILE = DATA_DIR / "events.json"
    ABSTRACT_MAP_FILE = DATA_DIR / "abstract_to_event_map.json"
    KNOWLEDGE_GRAPH_FILE = DATA_DIR / "knowledge_graph.json"
    KG_VISUAL_FILE = DATA_DIR / "kg_visual.json"
    KG_VISUAL_TIMELINE_FILE = DATA_DIR / "kg_visual_timeline.json"
    # processed_ids.txt 已废弃，数据已迁移到 SQLite 的 processed_ids 表
    # PROCESSED_IDS_FILE = DATA_DIR / "processed_ids.txt"  # 已废弃
    STOP_WORDS_FILE = DATA_DIR / "stop_words.txt"
    # SQLite 主存储（最终方案：SQLite 为主，JSON 为兼容导出/快照）
    SQLITE_DB_FILE = DATA_DIR / "store.sqlite"
    # 五种图谱快照输出目录
    SNAPSHOTS_DIR = DATA_DIR / "snapshots"
    
    # 临时文件路径（用于图谱更新过程中的暂存文件）
    ENTITIES_TMP_FILE = DATA_TMP_DIR / "entities_tmp.json"
    ABSTRACT_TMP_FILE = DATA_TMP_DIR / "abstract_tmp.json"
    
    # 配置常量（类变量）- 延迟初始化
    _dedupe_threshold = None

    @classmethod
    def get_dedupe_threshold(cls):
        """动态获取去重阈值配置"""
        if cls._dedupe_threshold is None:
            try:
                # 延迟导入以避免循环依赖
                from .config import ConfigManager
                config_manager = ConfigManager()
                cls._dedupe_threshold = config_manager.get_config_value("dedupe_threshold", 3, "agent1_config")
            except Exception:
                # 降级到环境变量或默认值
                cls._dedupe_threshold = int(os.getenv("AGENT1_DEDUPE_THRESHOLD", "3"))
        return cls._dedupe_threshold
    
    def _init_singleton(self) -> None:
        """单例初始化"""
        # 确保目录存在（仅使用 tmp 路径存放新闻）
        for d in [self.DATA_DIR, self.DATA_TMP_DIR, self.RAW_NEWS_TMP_DIR, 
                  self.DEDUPED_NEWS_TMP_DIR, self.DATA_DIR / "logs"]:
            d.mkdir(parents=True, exist_ok=True)

        # 实例变量
        stop_words = set()
        if self.STOP_WORDS_FILE.exists():
            with open(self.STOP_WORDS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        stop_words.add(word)
        self.STOP_WORDS = stop_words
        # 初始化刷新锁
        self._refresh_lock = threading.Lock()

    # ======================
    # 工具函数
    # ======================

    def log(self, msg: str):
        """记录日志"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] {msg}"
        # Windows 控制台常见为 GBK/CP936，遇到 emoji 等字符可能触发 UnicodeEncodeError
        try:
            print(line)
        except UnicodeEncodeError:
            try:
                enc = getattr(sys.stdout, "encoding", None) or "utf-8"
                safe_line = line.encode(enc, errors="replace").decode(enc, errors="replace")
                print(safe_line)
            except Exception:
                # 极端情况下直接降级为去除不可编码字符
                print(line.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore"))
        with open(self.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def load_stop_words(self) -> Set[str]:
        """加载停用词"""
        stop_words = set()
        if self.STOP_WORDS_FILE.exists():
            with open(self.STOP_WORDS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        stop_words.add(word)
        return stop_words

    def is_valid_entity(self, entity: str) -> bool:
        """检查实体是否有效（暂时弃用）"""
        word = entity.strip()
        if word in self.STOP_WORDS:
            return False
        return True

    def simhash(self, text: str, bits=64) -> int:
        """计算文本的 SimHash"""
        text = re.sub(r'\s+', ' ', text.lower())
        tokens = text.split()
        v = [0] * bits
        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            for i in range(bits):
                bit = (h >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1
        hash_val = 0
        for i in range(bits):
            if v[i] > 0:
                hash_val |= (1 << i)
        return hash_val

    def hamming_distance(self, h1: int, h2: int) -> int:
        """计算汉明距离"""
        return bin(h1 ^ h2).count("1")


# =============================================================================
# 兼容别名
# =============================================================================

# 保持向后兼容：tools 是 ProjectPaths 的别名
tools = ProjectPaths


# =============================================================================
# 便捷函数
# =============================================================================

def get_tools() -> ProjectPaths:
    """获取工具实例"""
    return ProjectPaths()


def get_data_dir() -> Path:
    """获取数据目录"""
    return ProjectPaths.DATA_DIR


def get_config_dir() -> Path:
    """获取配置目录"""
    return ProjectPaths.CONFIG_DIR
