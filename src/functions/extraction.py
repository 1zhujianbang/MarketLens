from typing import List, Dict, Any, Optional
from ..core.registry import register_tool
from ..agents.agent1 import llm_extract_events as _llm_extract
from ..agents.agent1 import NewsDeduplicator
from ..agents import agent2
import json
from pathlib import Path
import time
import threading
import yaml

@register_tool(
    name="extract_entities_events",
    description="使用 LLM 从新闻标题和内容中提取实体和事件",
    category="Information Extraction"
)
def extract_entities_events(title: str, content: str) -> List[Dict[str, Any]]:
    """
    从新闻中提取实体和事件
    
    Args:
        title: 新闻标题
        content: 新闻内容
        
    Returns:
        事件列表，每项包含 entities, event_summary 等
    """
    return _llm_extract(title, content)

@register_tool(
    name="deduplicate_news_batch",
    description="对新闻列表进行批量去重 (基于 SimHash)",
    category="Data Processing"
)
def deduplicate_news_batch(news_list: List[Dict[str, Any]], threshold: int = 3) -> List[Dict[str, Any]]:
    """
    批量去重
    
    Args:
        news_list: 新闻字典列表
        threshold: SimHash 汉明距离阈值
        
    Returns:
        去重后的新闻列表
    """
    if not news_list:
        return []
        
    deduper = NewsDeduplicator(threshold=threshold)
    unique_news = []
    
    for news in news_list:
        # 构造指纹文本
        text = (news.get("title", "") + " " + news.get("content", "")).strip()
        if not text: 
            continue
            
        # 检查重复
        if not deduper.is_duplicate(text):
            unique_news.append(news)
            
    return unique_news

@register_tool(
    name="batch_process_news",
    description="[工作流] 批量处理新闻：去重并提取事件",
    category="Workflow"
)
async def batch_process_news(news_list: List[Dict[str, Any]], limit: int = -1) -> List[Dict[str, Any]]:
    """
    批量处理新闻：
    1. 去重
    2. 提取实体和事件
    3. 附加元数据 (source, published_at)
    
    Args:
        news_list: 新闻列表
        limit: 限制处理的新闻数量，-1 表示不限制。用于测试/节省 Token。
    
    Returns:
        扁平化的事件列表
    """
    # 1. 去重
    unique_news = deduplicate_news_batch(news_list)
    if limit > 0:
        unique_news = unique_news[:limit]
    
    # 读取并发/限速配置（仅来自 config.yaml）
    cfg_path = Path(agent2.tools.CONFIG_DIR) / "config.yaml"
    max_workers = 7
    rate_limit = 20
    if cfg_path.exists():
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            a1_cfg = data.get("agent1_config", {}) or {}
            if isinstance(a1_cfg, dict):
                max_workers = int(a1_cfg.get("max_workers", max_workers))
                rate_limit = float(a1_cfg.get("rate_limit_per_sec", rate_limit))
        except Exception:
            pass

    class RateLimiter:
        def __init__(self, rate_per_sec: float):
            self.interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0
            self._lock = threading.Lock()
            self._next = 0.0

        def acquire(self):
            if self.interval <= 0:
                return
            with self._lock:
                now = time.time()
                if now < self._next:
                    time.sleep(self._next - now)
                self._next = max(self._next, now) + self.interval

    limiter = RateLimiter(rate_limit)

    def process_one(news: Dict[str, Any]) -> (List[Dict[str, Any]], Optional[str]):
        events_out = []
        processed_id = None
        try:
            title = news.get("title", "")
            content = news.get("content", "")
            source = news.get("source", "unknown")
            timestamp = news.get("datetime") or news.get("formatted_time")
            news_id = str(news.get("id", "")).strip()
            if news_id and source:
                processed_id = f"{source}:{news_id}"
            limiter.acquire()
            extracted = _llm_extract(title, content)
            for ev in extracted:
                ev["source"] = source
                ev["published_at"] = timestamp
                ev["news_id"] = news.get("id")
                events_out.append(ev)
        except Exception as e:
            print(f"Extraction failed for news {news.get('id', '')}: {e}")
        return events_out, processed_id

    all_events: List[Dict[str, Any]] = []
    processed_ids: List[str] = []
    if not unique_news:
        return all_events

    if max_workers <= 1:
        for n in unique_news:
            evs, pid = process_one(n)
            all_events.extend(evs)
            if pid:
                processed_ids.append(pid)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_one, n) for n in unique_news]
            for fut in as_completed(futures):
                evs, pid = fut.result()
                all_events.extend(evs or [])
                if pid:
                    processed_ids.append(pid)

    # 记录 processed_ids，避免重复处理
    if processed_ids:
        try:
            agent2.tools.PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(agent2.tools.PROCESSED_IDS_FILE, "a", encoding="utf-8") as f:
                for pid in processed_ids:
                    f.write(pid + "\n")
        except Exception:
            pass

    return all_events


@register_tool(
    name="persist_expanded_news_tmp",
    description="将拓展新闻写入 tmp/raw_news & tmp/deduped_news，并返回路径",
    category="Workflow"
)
def persist_expanded_news_tmp(expanded_news: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    为前端调用的包装：落地拓展新闻到 tmp，并返回文件路径。
    """
    processed_ids = set()
    if Path(agent2.tools.PROCESSED_IDS_FILE).exists():
        try:
            processed_ids = set(
                line.strip()
                for line in Path(agent2.tools.PROCESSED_IDS_FILE).read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        except Exception:
            processed_ids = set()

    deduped_path = agent2.persist_expanded_news_to_tmp(expanded_news, processed_ids)
    return {
        "deduped_path": str(deduped_path) if deduped_path else "",
        "raw_path": str(agent2.tools.RAW_NEWS_TMP_DIR) if deduped_path else "",
    }


@register_tool(
    name="save_extracted_events_tmp",
    description="将提取的事件列表写入 data/tmp/extracted_events_*.jsonl，并返回路径",
    category="Data Processing"
)
def save_extracted_events_tmp(events: List[Dict[str, Any]]) -> Dict[str, str]:
    if not events:
        return {"path": ""}
    ts = time.strftime("%Y%m%d%H%M%S")
    out_dir = agent2.tools.DATA_TMP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"extracted_events_{ts}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return {"path": str(out_path)}
