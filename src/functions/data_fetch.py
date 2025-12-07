from typing import List, Dict, Any, Optional
import pandas as pd
from ..core.registry import register_tool
from ..data import news_collector
from ..utils.tool_function import tools as Tools

@register_tool(
    name="fetch_news_stream",
    description="从所有配置的数据源（GNews, Blockbeats等）获取最新新闻",
    category="Data Fetch"
)
async def fetch_news_stream(limit: int = 50, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    获取全渠道新闻数据。
    
    Args:
        limit: 每个源获取的最大条数
        sources: 指定源列表 (如 ["GNews-cn"]), 默认为所有可用源
        
    Returns:
        新闻列表 (List[Dict])
    """
    tools = Tools()
    
    # 初始化 API Pool
    news_collector.init_api_pool()
    if news_collector.API_POOL is None:
        raise RuntimeError("API Pool failed to initialize")

    available_sources = news_collector.API_POOL.list_available_sources()
    if sources:
        target_sources = [s for s in sources if s in available_sources]
    else:
        target_sources = available_sources
    
    if not target_sources:
        tools.log("Warning: No valid sources to fetch from.")
        return []

    all_news = []
    
    for source_name in target_sources:
        try:
            collector = news_collector.API_POOL.get_collector(source_name)
            
            # 使用 async with 确保连接正确管理
            async with collector:
                 news = await collector.get_latest_important_news(limit=limit)
                 # 确保 source 字段存在
                 for item in news:
                     if "source" not in item:
                         item["source"] = source_name
                     
                     # 转换 datetime 为 ISO 字符串以便序列化
                     if "datetime" in item and hasattr(item["datetime"], "isoformat"):
                         item["datetime"] = item["datetime"].isoformat()
                         
                 all_news.extend(news)
                 tools.log(f"Fetched {len(news)} items from {source_name}")
                 
        except Exception as e:
            tools.log(f"Error fetching from {source_name}: {e}")

    # 按时间倒序排序
    all_news.sort(key=lambda x: x.get("datetime") or "", reverse=True)
    return all_news

