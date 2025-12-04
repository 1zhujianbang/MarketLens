import os
import sys
import json
import re
import time
from typing import Set
from datetime import datetime, timezone
import hashlib
from pathlib import Path

class tools:
    def __init__(self):

        # ======================
        # 路径与配置
        # ======================

        self.ROOT_DIR = Path(__file__).parent.parent.parent
        self.DATA_DIR = self.ROOT_DIR / "data"
        self.CONFIG_DIR = self.ROOT_DIR / "config"
        self.RAW_NEWS_DIR = self.DATA_DIR / "raw_news"
        self.DEDUPED_NEWS_DIR = self.DATA_DIR / "deduped_news"
        self.LOG_FILE = self.DATA_DIR / "logs" / "agent1.log"

        # 确保目录存在
        for d in [self.DATA_DIR, self.RAW_NEWS_DIR, self.DEDUPED_NEWS_DIR, self.DATA_DIR / "logs"]:
            d.mkdir(parents=True, exist_ok=True)

        # 数据文件
        self.ENTITIES_FILE = self.DATA_DIR / "entities.json"
        self.ABSTRACT_MAP_FILE = self.DATA_DIR / "abstract_to_event_map.json"
        self.PROCESSED_IDS_FILE = self.DATA_DIR / "processed_ids.txt"
        self.STOP_WORDS_FILE = self.DATA_DIR / "stop_words.txt"

        # 加载环境变量
        self.DEDUPE_THRESHOLD = int(os.getenv("AGENT1_DEDUPE_THRESHOLD", "3"))
        stop_words = set()
        if self.STOP_WORDS_FILE.exists():
            with open(self.STOP_WORDS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        stop_words.add(word)
        self.STOP_WORDS = stop_words

    # ======================
    # 工具函数
    # ======================

    def log(self, msg: str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] {msg}"
        print(line)
        with open(self.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def load_stop_words(self) -> Set[str]:
        stop_words = set()
        if self.STOP_WORDS_FILE.exists():
            with open(self.STOP_WORDS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        stop_words.add(word)
        return stop_words

    

    def is_valid_entity(self, entity: str) -> bool:
        word = entity.strip()
        if not word or len(word) < 2:
            return False
        if word in self.STOP_WORDS:
            return False
        if word.isdigit() or re.match(r'^[0-9+\-\.%$€¥]+$', word):
            return False
        if not any(c.isalnum() for c in word):
            return False
        # 排除常见无效模式
        if re.search(
            r'(上涨|下跌|暴涨|暴跌|利好|利空|市场|投资者|用户|社区|'
            r'协议|链|代币|币种|项目|平台|技术|系统|机制|概念|'
            r'行情|趋势|信号|策略|模型|算法|框架|生态)$',
            word
        ):
            return False
        return True

    def simhash(self, text: str, bits=64) -> int:
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
        return bin(h1 ^ h2).count("1")
