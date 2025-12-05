# src/data/api_client.py （建议单独文件）
import os
import json
from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv
from .news_collector import BlockbeatsNewsCollector, GNewsCollector, Language

class DataAPIPool:
    _instance = None
    _collectors = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        # 加载配置
        PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
        dotenv_path = PROJECT_ROOT / "config" / ".env.local"
        load_dotenv(dotenv_path)

        self.configs = []
        self._load_configs()
        # 调试：打印已加载的数据源配置
        print(f"[数据获取][DataAPIPool] 已加载数据源配置: {[c.get('name') for c in self.configs]}")

    def _load_configs(self):
        try:
            apis_config = os.getenv("DATA_APIS")
            if not apis_config:
                raise ValueError("DATA_APIS 未设置")
            print(f"[数据获取][DataAPIPool] 原始 DATA_APIS 环境变量: {apis_config}")
            apis = json.loads(apis_config)
            for cfg in apis:
                if cfg.get("enabled", True):
                    self.configs.append(cfg)
        except Exception as e:
            print(f"[数据获取] ❌ 解析 DATA_APIS 失败: {e}")
            raise

    def get_collector(self, name: str) -> Optional[Any]:
        """根据 name 返回对应的新闻收集器实例（单例）"""
        if name in self._collectors:
            print(f"[数据获取][DataAPIPool] 复用已创建的 collector: {name}")
            return self._collectors[name]

        # 查找配置
        config = None
        for cfg in self.configs:
            if name in cfg["name"]:
                config = cfg
                break

        if not config:
            raise ValueError(f"[数据获取][DataAPIPool] 未找到名为 '{name}' 的数据源配置")

        # 创建对应 collector
        print(f"[数据获取][DataAPIPool] 准备创建 collector: {name}, config={config}")
        if "Blockbeats" in name:
            collector = BlockbeatsNewsCollector(
                language=Language.CN,  # 可从配置读取
                timeout=config.get("timeout", 30),
            )
        elif "GNews" in name:
            api_key = config.get("api_key") or os.getenv("GNEWS_API_KEY", "")
            if not api_key:
                raise ValueError("GNews 数据源需要配置 api_key 或环境变量 GNEWS_API_KEY")

            language = config.get("language", "zh")
            country = config.get("country")

            collector = GNewsCollector(
                api_key=api_key,
                language=language,
                country=country,
                timeout=config.get("timeout", 30),
            )
        else:
            raise NotImplementedError(f"不支持的数据源类型: {name}")

        self._collectors[name] = collector
        return collector

    def list_available_sources(self) -> list:
        return [cfg["name"] for cfg in self.configs]