# src/agents/agent2.py
"""
智能体2：实体拓展新闻

核心功能：
1. 从实体库中获取已提取的实体
2. 使用这些实体作为关键词搜索相关新闻
3. 对搜索到的新闻进行处理，提取更多相关实体和事件
4. 更新实体库和事件映射
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime, timezone, timedelta
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from dotenv import load_dotenv
from ..utils.tool_function import tools
from ..data.api_client import DataAPIPool
from ..data.news_collector import NewsType
from .agent1 import llm_extract_events, update_entities, update_abstract_map

# 初始化工具和数据API池
tools = tools()
data_api_pool = DataAPIPool()

async def expand_news_by_entities(entities: List[str], limit_per_entity: int = 10) -> List[Dict]:
    """
    根据实体列表搜索相关新闻
    
    Args:
        entities: 实体列表
        limit_per_entity: 每个实体搜索的新闻数量限制
        
    Returns:
        搜索到的相关新闻列表
    """
    expanded_news = []
    
    # 获取所有可用的新闻收集器
    news_collectors = []
    available_sources = data_api_pool.list_available_sources()
    
    for source_name in available_sources:
        try:
            collector = data_api_pool.get_collector(source_name)
            news_collectors.append(collector)
        except Exception as e:
            tools.log(f"⚠️ 无法创建新闻收集器 {source_name}: {e}")
    
    if not news_collectors:
        tools.log("❌ 未找到可用的新闻收集器")
        return expanded_news
    
    # 为每个实体搜索相关新闻
    for entity in entities:
        tools.log(f"🔍 为实体 '{entity}' 搜索相关新闻...")
        
        for collector in news_collectors:
            try:
                # 使用搜索功能获取相关新闻
                if hasattr(collector, 'search_news_by_keyword'):
                    news_list = await collector.search_news_by_keyword(
                        keyword=entity,
                        limit=limit_per_entity
                    )
                    
                    # 为每条新闻添加实体标签
                    for news in news_list:
                        news['expanded_from_entity'] = entity
                        news['source'] = collector.__class__.__name__.replace('NewsCollector', '').lower()
                        expanded_news.append(news)
                elif hasattr(collector, 'search'):
                    # 兼容不同的搜索方法名
                    news_list = await collector.search(
                        query=entity,
                        limit=limit_per_entity
                    )
                    
                    for news in news_list:
                        news['expanded_from_entity'] = entity
                        news['source'] = collector.__class__.__name__.replace('Collector', '').lower()
                        expanded_news.append(news)
            except Exception as e:
                tools.log(f"⚠️ 从 {collector.__class__.__name__} 搜索实体 '{entity}' 相关新闻失败: {e}")
    
    return expanded_news

def get_recent_entities(time_window_hours: int = 24, limit: int = 50) -> List[str]:
    """
    获取最近时间窗口内的实体列表
    
    Args:
        time_window_hours: 时间窗口（小时）
        limit: 返回的实体数量限制
        
    Returns:
        最近的实体列表
    """
    entities = []
    
    if not tools.ENTITIES_FILE.exists():
        tools.log("⚠️ 实体库文件不存在")
        return entities
    
    # 读取实体库
    with open(tools.ENTITIES_FILE, "r", encoding="utf-8") as f:
        entity_data = json.load(f)
    
    # 根据 first_seen 排序，获取最近的实体
    sorted_entities = sorted(
        entity_data.items(),
        key=lambda x: x[1].get('first_seen', ''),
        reverse=True
    )
    
    # 过滤时间窗口内的实体
    now = datetime.now(timezone.utc)
    time_window = timedelta(hours=time_window_hours)
    
    for entity_name, entity_info in sorted_entities:
        first_seen = entity_info.get('first_seen')
        if first_seen:
            try:
                # 解析时间字符串
                if 'T' in first_seen:
                    # ISO格式时间
                    seen_time = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
                else:
                    # 普通格式时间
                    seen_time = datetime.strptime(first_seen, '%Y-%m-%d %H:%M:%S')
                    seen_time = seen_time.replace(tzinfo=timezone.utc)
                
                # 检查是否在时间窗口内
                if now - seen_time <= time_window:
                    entities.append(entity_name)
                    if len(entities) >= limit:
                        break
            except Exception as e:
                tools.log(f"⚠️ 解析实体 '{entity_name}' 的时间戳失败: {e}")
    
    tools.log(f"✅ 获取了 {len(entities)} 个最近实体")
    return entities

async def process_expanded_news(expanded_news: List[Dict]) -> int:
    """
    处理拓展的新闻，提取实体和事件
    
    Args:
        expanded_news: 拓展的新闻列表
        
    Returns:
        处理的新闻数量
    """
    processed_count = 0
    
    # 创建去重集合
    seen_news = set()
    
    for news in expanded_news:
        try:
            # 检查新闻是否已处理
            news_id = news.get('id')
            source = news.get('source', 'unknown')
            if news_id:
                news_key = f"{source}:{news_id}"
                if news_key in seen_news:
                    continue
                seen_news.add(news_key)
            
            title = news.get('title', '')
            content = news.get('content', '')
            
            if not title:
                continue
            
            # 提取实体和事件
            extracted = llm_extract_events(title, content)
            
            if extracted:
                all_entities = []
                for ev in extracted:
                    all_entities.extend(ev['entities'])
                
                if all_entities:
                    # 优先使用新闻自身的时间戳
                    published_at = news.get('datetime')
                    if published_at and isinstance(published_at, datetime):
                        published_at = published_at.isoformat()
                    
                    # 更新实体库和事件映射
                    update_entities(all_entities, source, published_at)
                    update_abstract_map(extracted, source, published_at)
                    processed_count += 1
                    
        except Exception as e:
            tools.log(f"⚠️ 处理拓展新闻失败: {e}")
    
    return processed_count

async def main():
    """
    主函数
    """
    tools.log("🚀 启动 Agent2：实体拓展新闻...")
    
    # 1. 获取最近的实体
    recent_entities = get_recent_entities(time_window_hours=24, limit=50)
    
    if not recent_entities:
        tools.log("📭 没有可用的实体进行新闻拓展")
        return
    
    # 2. 使用实体搜索相关新闻
    tools.log(f"🔍 开始搜索 {len(recent_entities)} 个实体的相关新闻...")
    expanded_news = await expand_news_by_entities(recent_entities, limit_per_entity=5)
    tools.log(f"✅ 共搜索到 {len(expanded_news)} 条相关新闻")
    
    # 3. 处理搜索到的新闻
    if expanded_news:
        tools.log("📄 开始处理拓展的新闻...")
        processed_count = await process_expanded_news(expanded_news)
        tools.log(f"✅ 成功处理 {processed_count} 条拓展新闻")
    
    tools.log("🎉 实体拓展新闻任务完成！")

if __name__ == "__main__":
    asyncio.run(main())
