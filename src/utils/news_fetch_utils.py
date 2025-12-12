"""
新闻数据获取公共工具函数

统一处理新闻数据获取、转换和处理的重复逻辑。
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def normalize_news_items(news_list: List[Dict[str, Any]], source_name: str) -> List[Dict[str, Any]]:
    """
    标准化新闻数据项

    Args:
        news_list: 原始新闻列表
        source_name: 数据源名称

    Returns:
        标准化后的新闻列表
    """
    for item in news_list:
        # 设置数据源
        if "source" not in item:
            item["source"] = source_name

        # 转换datetime对象为ISO格式字符串
        if "datetime" in item and hasattr(item["datetime"], "isoformat"):
            item["datetime"] = item["datetime"].isoformat()

    return news_list


async def fetch_from_collector(
    collector: Any,
    source_name: str,
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    nullable: Optional[str] = None,
    truncate: Optional[str] = None,
    sortby: Optional[str] = None,
    in_fields: Optional[str] = None,
    page: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    从新闻收集器获取数据的统一接口

    Args:
        collector: 新闻收集器实例
        source_name: 数据源名称
        query: 搜索关键词
        category: 分类
        limit: 限制条数
        from_: 开始时间
        to: 结束时间
        nullable: 可空字段
        truncate: 截断字段
        sortby: 排序方式
        in_fields: 搜索字段
        page: 页码

    Returns:
        新闻数据列表
    """
    try:
        async with collector:
            if query:
                # 使用搜索接口
                news = await collector.search(
                    query=query,
                    from_=from_,
                    to=to,
                    limit=limit,
                    in_fields=in_fields,
                    nullable=nullable,
                    sortby=sortby,
                    page=page,
                    truncate=truncate,
                )
            else:
                # 使用头条接口
                news = await collector.get_top_headlines(
                    category=category,
                    limit=limit,
                    nullable=nullable,
                    from_=from_,
                    to=to,
                    query=query,
                    page=page,
                    truncate=truncate,
                )

        # 标准化数据
        normalized_news = normalize_news_items(news, source_name)
        logger.debug(f"成功从 {source_name} 获取 {len(normalized_news)} 条新闻")
        return normalized_news

    except Exception as e:
        logger.error(f"从 {source_name} 获取数据失败: {e}")
        return []


async def fetch_from_multiple_sources(
    api_pool: Any,
    source_names: List[str],
    concurrency_limit: int,
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    nullable: Optional[str] = None,
    truncate: Optional[str] = None,
    sortby: Optional[str] = None,
    in_fields: Optional[str] = None,
    page: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    从多个数据源并发获取新闻数据

    Args:
        api_pool: API池实例
        source_names: 数据源名称列表
        concurrency_limit: 并发限制
        其他参数同 fetch_from_collector

    Returns:
        合并后的新闻数据列表
    """
    from ..utils.llm_utils import AsyncExecutor

    async_executor = AsyncExecutor()

    async def fetch_one(source_name: str) -> List[Dict[str, Any]]:
        try:
            collector = api_pool.get_collector(source_name)
            return await fetch_from_collector(
                collector=collector,
                source_name=source_name,
                query=query,
                category=category,
                limit=limit,
                from_=from_,
                to=to,
                nullable=nullable,
                truncate=truncate,
                sortby=sortby,
                in_fields=in_fields,
                page=page,
            )
        except Exception as e:
            logger.error(f"获取数据源 {source_name} 失败: {e}")
            return []

    # 并发执行
    results = await async_executor.run_concurrent_tasks(
        tasks=[lambda src=src: fetch_one(src) for src in source_names],
        concurrency=concurrency_limit
    )

    # 合并结果
    all_news = []
    for news in results:
        all_news.extend(news)

    # 按时间排序
    all_news.sort(key=lambda x: x.get("datetime") or "", reverse=True)

    return all_news