"""
新闻API管理器

统一管理新闻数据源的API配置、密钥池和收集器实例。
"""

import os
import json
import aiohttp
import asyncio
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any, List, Dict
from dotenv import load_dotenv
from .singleton import SingletonBase
from ..utils.tool_function import tools

# 设置Windows异步兼容性
os.environ["AIODNS_NO_winloop"] = "1"
if os.name == "nt":  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_apis_config(config_path: Path = None) -> List[dict]:
    """
    获取默认API配置（硬编码作为默认值）
    """
    return [
        {"name": "GNews-cn", "language": "zh", "country": "cn", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-us", "language": "en", "country": "us", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-fr", "language": "fr", "country": "fr", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-gb", "language": "en", "country": "gb", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-hk", "language": "zh", "country": "hk", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-ru", "language": "ru", "country": "ru", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-ua", "language": "uk", "country": "ua", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-tw", "language": "zh", "country": "tw", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-sg", "language": "en", "country": "sg", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-jp", "language": "ja", "country": "jp", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-br", "language": "pt", "country": "br", "timeout": 30, "enabled": True, "type": "gnews"},
        {"name": "GNews-ar", "language": "es", "country": "ar", "timeout": 30, "enabled": True, "type": "gnews"}
    ]


class NewsAPIManager(SingletonBase):
    """
    新闻API管理器 - 单例模式
    负责管理API配置、密钥池和收集器实例
    """
    _collectors = {}

    def _init_singleton(self) -> None:
        """单例初始化"""
        # 加载环境变量（主要用于获取API密钥）
        PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
        dotenv_path = PROJECT_ROOT / "config" / ".env.local"
        load_dotenv(dotenv_path)

        self.configs: List[Dict[str, Any]] = []
        self.api_key_pool: List[str] = []  # API密钥池
        self._load_configs()
        # 调试：打印已加载的数据源配置
        print(f"[数据获取][NewsAPIManager] 已加载数据源配置: {[c.get('name') for c in self.configs]}")

    def _load_configs(self):
        """
        加载API配置和API池
        """
        try:
            # 获取默认配置
            print(f"[数据获取][NewsAPIManager] 加载默认 API 配置")
            apis = get_apis_config()

            # 加载API密钥池
            gnews_apis_pool = os.getenv("GNEWS_APIS_POOL")
            self.api_key_pool = []
            if gnews_apis_pool:
                print(f"[数据获取][NewsAPIManager] 加载GNEWS_APIS_POOL环境变量")
                # 移除环境变量值可能存在的首尾单引号
                gnews_apis_pool_clean = gnews_apis_pool.strip("'")
                try:
                    self.api_key_pool = json.loads(gnews_apis_pool_clean)
                    print(f"[数据获取][NewsAPIManager] 已加载API池，包含 {len(self.api_key_pool)} 个API密钥")
                except json.JSONDecodeError:
                    print(f"[数据获取][NewsAPIManager] Error: GNEWS_APIS_POOL 格式错误，应为 JSON 数组")
            else:
                print(f"[数据获取][NewsAPIManager] 警告: 未设置 GNEWS_APIS_POOL")

            # 为每个启用的配置分配API密钥
            api_key_index = 0
            for cfg in apis:
                if cfg.get("enabled", True):
                    # 如果是GNews类型且没有api_key，则从API池分配
                    # 根据 type 或 name 判断
                    is_gnews = cfg.get("type") == "gnews" or "GNews" in cfg.get("name", "")

                    if is_gnews and "api_key" not in cfg and self.api_key_pool:
                        cfg["api_key"] = self.api_key_pool[api_key_index % len(self.api_key_pool)]
                        api_key_index += 1
                        # print(f"[数据获取][NewsAPIManager] 为 {cfg['name']} 分配API密钥")

                    self.configs.append(cfg)
        except Exception as e:
            print(f"[数据获取] ❌ 解析 API 配置失败: {e}")
            raise

    def get_collector(self, name: str) -> Optional[Any]:
        """根据 name 返回对应的新闻收集器实例（单例）"""
        if name in self._collectors:
            # print(f"[数据获取][NewsAPIManager] 复用已创建的 collector: {name}")
            return self._collectors[name]

        # 查找配置
        config = None
        for cfg in self.configs:
            if name == cfg["name"]:
                config = cfg
                break

        if not config:
            raise ValueError(f"[数据获取][NewsAPIManager] 未找到名为 '{name}' 的数据源配置")

        # 创建对应 collector
        # print(f"[数据获取][NewsAPIManager] 准备创建 collector: {name}")

        source_type = config.get("type", "").lower()
        if not source_type:
            if "gnews" in name.lower(): source_type = "gnews"

        if source_type == "gnews":
            api_key = config.get("api_key") or os.getenv("GNEWS_API_KEY", "")
            if not api_key:
                raise ValueError("GNews 数据源需要配置 api_key 或环境变量 GNEWS_API_KEY")

            language = config.get("language", "zh")
            country = config.get("country")

            collector = GNewsCollector(
                api_key=api_key,
                language=language,
                country=country,
                timeout=config.get("timeout", 30)
            )
        else:
            raise NotImplementedError(f"不支持的数据源类型: {source_type} ({name})")

        self._collectors[name] = collector
        return collector

    def list_available_sources(self) -> List[str]:
        """
        获取所有可用的数据源名称列表

        Returns:
            数据源名称列表
        """
        available_sources = []
        for cfg in self.configs:
            if cfg.get("enabled", True):
                available_sources.append(cfg["name"])
        return available_sources


class GNewsCollector:
    """
    GNews 新闻数据收集器

    文档: https://gnews.io/api/v4/{endpoint}?{parameters}&apikey=YOUR_API_KEY
    """

    BASE_URL = "https://gnews.io/api/v4/"

    def __init__(
        self,
        api_key: str,
        language: str = "zh",
        country: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        初始化 GNews 收集器

        Args:
            api_key: GNews API Key
            language: 语言代码, 如 'zh', 'en'
            country: 国家代码, 如 'cn', 'us'；可选
            timeout: 超时时间（秒）
        """
        self.api_key = api_key
        self.language = language
        self.country = country
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def __aenter__(self):
        if not self.session:
            self._connector = aiohttp.TCPConnector(limit=10)
            self.session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None
        if self._connector:
            await self._connector.close()
            self._connector = None

    async def _ensure_session(self):
        if not self.session:
            self._connector = aiohttp.TCPConnector(limit=10)
            self.session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )

    async def _make_request(self, endpoint: str, params: Dict) -> Dict[str, Any]:
        await self._ensure_session()

        url = f"{self.BASE_URL}{endpoint}"
        # 创建参数副本，避免修改原始参数
        request_params = dict(params or {})

        # 使用当前收集器的API key
        request_params["apikey"] = self.api_key

        try:
            # 调试：打印本次请求的关键信息（不打印完整 key）
            safe_params = {k: (v if k != "apikey" else "***") for k, v in request_params.items()}
            print(f"[数据获取][GNews] 请求 {url} 参数: {safe_params}")
            async with self.session.get(url, params=request_params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"GNews API 请求失败: {response.status} - {text}")

                data = await response.json()
                print(f"[数据获取][GNews] 响应状态: {response.status}, 文章数: {len(data.get('articles', []) if isinstance(data, dict) else [])}")
                return data
        except aiohttp.ClientError as e:
            raise Exception(f"GNews 网络请求错误: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"GNews JSON 解析错误: {e}")

    async def get_top_headlines(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        nullable: Optional[str] = None,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        query: Optional[str] = None,
        page: Optional[int] = None,
        truncate: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取头条新闻（Top Headlines Endpoint）

        对应 GNews 参数:
        - category: 分类，如 general, world, business, technology 等
        - lang:     语言（已由实例属性 language 决定）
        - country:  国家（已由实例属性 country 决定，可选）
        - max:      返回条数（limit）
        - nullable: 允许为 null 的字段，如 "description,content"
        - from/to:  ISO8601 时间范围
        - q:        关键字（可选）
        - page:     页码
        - truncate: 内容截断设置，如 "content"
        """
        params: Dict[str, Any] = {
            "lang": self.language,
            "max": min(limit, 100),
        }
        if self.country:
            params["country"] = self.country
        if category:
            params["category"] = category
        if nullable:
            params["nullable"] = nullable
        if from_:
            params["from"] = from_
        if to:
            params["to"] = to
        if query:
            params["q"] = query
        if page is not None:
            params["page"] = page
        if truncate:
            params["truncate"] = truncate

        data = await self._make_request("top-headlines", params)
        articles = data.get("articles", []) or []

        for art in articles:
            self._process_timestamp(art)

        return articles[:limit]

    async def search(
        self,
        query: str,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        limit: int = 10,
        in_fields: Optional[str] = None,
        nullable: Optional[str] = None,
        sortby: Optional[str] = None,
        page: Optional[int] = None,
        truncate: Optional[str] = None,
    ) -> List[Dict]:
        """
        使用 Search Endpoint 按关键字搜索新闻

        对应 GNews 参数:
        - q:       关键字（必填）
        - lang:    语言（已由实例属性 language 决定）
        - country: 国家（已由实例属性 country 决定，可选）
        - max:     返回条数（limit）
        - in:      搜索字段，如 "title,description"
        - nullable: 允许为 null 的字段，如 "description,content"
        - from / to: ISO8601 时间范围
        - sortby:  "publishedAt" | "relevance"
        - page:    页码
        - truncate: 内容截断设置，如 "content"
        """

        params: Dict[str, Any] = {
            "q": query,
            "lang": self.language,
            "max": min(limit, 100),
        }

        if self.country:
            params["country"] = self.country
        if from_:
            params["from"] = from_
        if to:
            params["to"] = to
        if in_fields:
            params["in"] = in_fields
        if nullable:
            params["nullable"] = nullable
        if sortby:
            params["sortby"] = sortby
        if page is not None:
            params["page"] = page
        if truncate:
            params["truncate"] = truncate

        data = await self._make_request("search", params)
        articles = data.get("articles", []) or []

        for art in articles:
            self._process_timestamp(art)

        return articles[:limit]

    def _process_timestamp(self, article: Dict) -> None:
        """
        处理 GNews 的 publishedAt 字段，转换为 datetime 和本地格式化时间
        """
        ts = article.get("publishedAt")
        if not ts:
            article["datetime"] = None
            article["formatted_time"] = "未知时间"
            return
        try:
            # 例如: 2025-12-04T09:30:00Z
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            article["datetime"] = dt
            article["formatted_time"] = dt.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            article["datetime"] = None
            article["formatted_time"] = "未知时间"

    async def get_latest_important_news(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的重要新闻
        """
        return await self.get_top_headlines(limit=limit)

    def news_to_dataframe(self, news_list: List[Dict]) -> pd.DataFrame:
        """
        将 GNews 文章列表转换为与 Agent1 兼容的 DataFrame 结构
        """
        if not news_list:
            return pd.DataFrame()

        processed: List[Dict[str, Any]] = []
        source_name = "gnews"

        for article in news_list:
            url = article.get("url", "")
            title = article.get("title", "") or ""
            content = article.get("content") or article.get("description", "") or ""
            img = article.get("image", "")
            src = article.get("source", {}) or {}
            src_name = src.get("name") or source_name

            processed.append(
                {
                    # 使用 URL 作为全局唯一 ID，后续 Agent1 会组合为 "gnews:<url>"
                    "id": url or tools.md5(title.encode("utf-8")).hexdigest(),
                    "source": src_name,
                    "title": title,
                    "content": content,
                    "type": "article",
                    "link": url,
                    "image_url": img,
                    "create_time": article.get("formatted_time", ""),
                    "timestamp": article.get("datetime"),
                    "is_original": False,
                    "column": src_name,
                    "entities": [],
                    "event_type": None,
                    "raw_json": json.dumps(
                        article, default=lambda obj: obj.isoformat() if isinstance(obj, datetime) else str(obj), ensure_ascii=False
                    ),
                }
            )

        df = pd.DataFrame(processed)
        if not df.empty and "timestamp" in df.columns:
            df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
        return df

    async def get_news_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取指定时间范围内的新闻摘要

        Args:
            hours: 时间范围（小时）

        Returns:
            新闻摘要统计
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # 获取最近的重要新闻
        all_news = await self.get_latest_important_news(limit=100)

        # 过滤时间范围内的新闻
        recent_news = []
        for news in all_news:
            news_time = news.get("datetime")
            if news_time and start_time <= news_time <= end_time:
                recent_news.append(news)

        # 统计信息
        flash_count = sum(1 for news in recent_news if "content" in news)
        article_count = len(recent_news) - flash_count

        # 提取热门关键词（简单实现）
        all_titles = " ".join([news.get("title", "") for news in recent_news])
        words = all_titles.split()
        from collections import Counter
        word_freq = Counter(words)
        top_keywords = [word for word, count in word_freq.most_common(10) if len(word) > 1]

        return {
            "total_news": len(recent_news),
            "flash_count": flash_count,
            "article_count": article_count,
            "time_range": f"最近{hours}小时",
            "top_keywords": top_keywords[:5],
            "latest_news": recent_news[:10]  # 最新10条新闻
        }

    def clear_cache(self):
        """清空缓存"""
        pass