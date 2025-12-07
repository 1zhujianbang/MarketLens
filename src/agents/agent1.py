# src/agents/agent1.py
"""
智能体1：流式新闻去重 + LLM驱动的真实世界实体与事件提取器

核心原则：
- 实体 = 能签署合同、被起诉、发布公告、拥有银行账户的主体
  （自然人、公司、政府机构、国家、地区、国际组织）
- 排除：代币名称、技术术语、抽象概念、情绪词、泛称
- 提取即自动写入 entities.json，无需人工审核
- 每个事件生成唯一摘要，并关联实体与事件描述
- 自动更新知识图谱，维护实体-事件关系网络
"""

import os
import sys
import json
import re
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime, timezone
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from dotenv import load_dotenv
from ..utils.tool_function import tools
tools = tools()
from .api_client import LLMAPIPool
from ..utils.entity_updater import update_entities, update_abstract_map
from .agent3 import refresh_graph
API_POOL = None

def init_api_pool():
    global API_POOL
    if API_POOL is None:
        API_POOL = LLMAPIPool()


# ======================
# 新闻去重器
# ======================

class NewsDeduplicator:
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.seen_hashes: Set[int] = set()

    @staticmethod
    def _news_key(news: Dict) -> str:
        """构造用于去重的唯一键，包含 source 前缀，兼容多数据源。"""
        return f"{news.get('source', 'unknown')}:{news.get('id')}"

    def is_duplicate(self, text: str) -> bool:
        h = tools.simhash(text)
        for seen_h in self.seen_hashes:
            if tools.hamming_distance(h, seen_h) <= self.threshold:
                return True
        self.seen_hashes.add(h)
        return False

    def dedupe_file(self, input_path: Path, output_path: Path, processed_ids: Optional[Set[str]] = None):
        """
        对单个原始文件做去重：
        - 先用 processed_ids（全局已处理 ID，如 blockbeats:323066）过滤历史已处理新闻
        - 再结合已有去重文件 & simhash 去掉本批内/跨批的重复内容
        """
        tools.log(f"🔍 去重中: {input_path.name}")

        # 先加载“全局已处理 ID”，避免老新闻再次进入去重结果
        seen_ids: Set[str] = set(processed_ids or set())
        if processed_ids:
            tools.log(f"🔍 已有历史 processed_ids 数量: {len(processed_ids)}")

        # 再加载已有去重结果文件中的 ID，实现跨批次的本地去重
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                        seen_ids.add(self._news_key(item))
                    except Exception as e:
                        tools.log(f"⚠️ 读取历史去重文件时跳过无效行: {e}")
        
        kept, skipped_id, skipped_sim = 0, 0, 0
        with open(input_path, "r", encoding="utf-8") as fin, \
             open(output_path, "a", encoding="utf-8") as fout:
            for line in fin:
                try:
                    news = json.loads(line)
                    key = self._news_key(news)

                    # 1) 按全局 ID 去重（包括 processed_ids 和已有去重文件中的 ID）
                    if key in seen_ids:
                        skipped_id += 1
                        continue

                    # 2) 构造文本，按内容相似度去重
                    raw_text = (news.get("title", "") + " " + news.get("content", "")).strip()
                    if not raw_text:
                        continue
                    if self.is_duplicate(raw_text):
                        skipped_sim += 1
                        continue
                    fout.write(line)
                    seen_ids.add(key)
                    kept += 1
                except Exception as e:
                    tools.log(f"⚠️ 跳过无效行: {e}")
        tools.log(f"✅ 去重完成: 保留 {kept} 条, 按 ID 跳过 {skipped_id} 条, 按相似度跳过 {skipped_sim} 条")

# ======================
# LLM 结构化提取器（含精准提示词）
# ======================

def llm_extract_events(title: str, content: str, max_retries=2) -> List[Dict]:
    # 初始化 API 池（单例）
    init_api_pool()
    if API_POOL is None:
        tools.log("[LLM请求] ❌ API 池未初始化")
        return []

    prompt = f"""你是一名专业的金融与法律信息结构化专家。请从以下新闻中提取所有**真实存在的、具有法律人格或行政职能的实体**。

【实体定义】
✅ 必须满足以下任一条件：
- 是自然人（如 Elon Musk、Cathie Wood、Warren Buffett）
- 是注册公司（如 Apple Inc.、Goldman Sachs、中国工商银行、Volkswagen AG）
- 是政府机构或部门（如 美国证券交易委员会、中国人民银行、欧盟委员会、日本金融厅）
- 是主权国家或明确行政区（如 美国、新加坡、加利福尼亚州、香港特别行政区、德意志联邦共和国）
- 是国际组织（如 国际货币基金组织、世界银行、联合国、金融稳定理事会）

❌ 以下内容**不得**视为实体：
- 抽象概念（如 “市场波动”、“系统性风险”、“资本流动”）
- 技术或金融术语（如 “期权定价”、“资产负债表”、“量化宽松”）
- 金融工具或资产名称（如 “标普500指数”、“10年期美债”、“黄金期货”、“BTC”）——除非指代其发行方、管理方或关联法人（如 “标普道琼斯指数公司”）
- 泛称（如 “投资者”、“监管机构”、“某银行”、“大型科技公司”）
- 情绪/行情描述（如 “暴涨”、“抛售潮”、“经济衰退担忧”）

【任务要求】
1. 判断新闻是否包含一个或多个独立事件。
2. 对每个事件，输出：
   - 一个简洁、客观、无情绪的中文摘要（作为事件唯一标识）
   - 所有符合上述定义的实体（全称优先，避免缩写；若原文使用英文名且无通用中文译名，则保留英文）
   - 所有符合上述定义的实体的原始语言表述（保留新闻中实体的原始语言形式；原始语言实体数组的索引与实体数组索引一一对应）
   - 该事件的本质描述（一句话说明“谁对谁做了什么”）

【输出格式】
严格返回 JSON，不要任何额外文本：
{{
  "events": [
    {{
      "abstract": "美国证券交易委员会推迟对VanEck比特币ETF申请的决定",
      "entities": ["美国证券交易委员会", "VanEck"],
      "entities_original": ["SEC", "VanEck"],
      "event_summary": "监管机构延长了对某资产管理公司比特币ETF申请的审查期"
    }}
  ]
}}

【新闻】
标题：{title}
正文：{content}"""

    # 调用 API 池
    raw_content = API_POOL.call(
        prompt=prompt,
        max_tokens=1500,
        timeout=55,      # 避开 60s 代理超时
        retries=max_retries
    )

    if not raw_content:
        return []

    # 清理 Markdown 包裹
    try:
        if raw_content.startswith("```json"):
            raw_content = raw_content.split("```json", 1)[1].split("```")[0]
        elif raw_content.startswith("```"):
            raw_content = raw_content.split("```", 1)[1].split("```")[0]

        data = json.loads(raw_content)
        events = data.get("events", [])
        result = []
        for item in events:
            abstract = item.get("abstract", "").strip()
            # 确保entities和entities_original一一对应，且都有效
            entities_raw = item.get("entities", [])
            entities_original_raw = item.get("entities_original", [])
            entities = []
            entities_original = []
            
            # 遍历并过滤，确保索引对应
            for ent, ent_original in zip(entities_raw, entities_original_raw):
                if tools.is_valid_entity(ent) and tools.is_valid_entity(ent_original):
                    entities.append(ent)
                    entities_original.append(ent_original)
            summary = item.get("event_summary", "").strip()
            if abstract and entities and summary:
                result.append({
                    "abstract": abstract,
                    "entities": entities,
                    "entities_original": entities_original,
                    "event_summary": summary
                })
        return result
    except Exception as e:
        tools.log(f"[LLM获取] ❌ LLM 返回内容解析失败: {e}")
        return []
    


# ======================
# 主处理流程
# ======================

def get_unprocessed_news_files() -> List[Path]:
    processed_ids = set()
    if tools.PROCESSED_IDS_FILE.exists():
        with open(tools.PROCESSED_IDS_FILE, "r") as f:
            processed_ids = set(line.strip() for line in f if line.strip())
    
    unprocessed = []
    for raw_file in sorted(tools.RAW_NEWS_DIR.glob("*.jsonl")):
        deduped_file = tools.DEDUPED_NEWS_DIR / f"{raw_file.stem}_deduped.jsonl"
        if not deduped_file.exists():
            deduper = NewsDeduplicator(threshold=tools.DEDUPE_THRESHOLD)
            # 先用 processed_ids 过滤“历史已处理新闻”，再写入去重文件
            deduper.dedupe_file(raw_file, deduped_file, processed_ids)
        unprocessed.append(deduped_file)
    return unprocessed

def process_news_stream():
    tools.log("🚀 启动 Agent1：流式事件与真实实体提取...")
    files = get_unprocessed_news_files()
    if not files:
        tools.log("📭 无可处理新闻文件")
        return

    processed_ids = set()
    if tools.PROCESSED_IDS_FILE.exists():
        with open(tools.PROCESSED_IDS_FILE, "r") as f:
            processed_ids = set(line.strip() for line in f if line.strip())

    total_processed = 0
    with open(tools.PROCESSED_IDS_FILE, "a") as id_log:
        for file_path in files:
            tools.log(f"📄 处理文件: {file_path.name}")
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        news = json.loads(line)
                        raw_id = str(news.get("id", "")).strip()
                        source = news.get("source", "unknown").strip().lower()
                        
                        if not raw_id or not source:
                            tools.log("⚠️ 跳过无 ID 或无 source 的新闻")
                            continue

                        global_id = f"{source}:{raw_id}"  # 👈 关键：带前缀的全局唯一 ID

                        if global_id in processed_ids:
                            continue

                        title = news.get("title", "")
                        content = news.get("content", "")

                        # 为避免超长正文导致 LLM 超出 token 或返回异常 JSON，这里对正文做长度截断
                        MAX_CONTENT_CHARS = 2000  # 可调，比如 1500 / 3000
                        if isinstance(content, str) and len(content) > MAX_CONTENT_CHARS:
                            content = content[:MAX_CONTENT_CHARS] + "……【后文已截断】"

                        extracted = llm_extract_events(title, content)

                        if extracted:
                            all_entities = []
                            all_entities_original = []
                            for ev in extracted:
                                all_entities.extend(ev["entities"])
                                all_entities_original.extend(ev["entities_original"])
                            if all_entities and len(all_entities) == len(all_entities_original):
                                # 优先使用新闻自身的时间戳（由采集器提供），否则使用当前时间
                                ts = news.get("timestamp")
                                # 部分旧数据可能是 datetime 对象或其他类型，统一转为字符串
                                published_at = None
                                if ts:
                                    try:
                                        published_at = (
                                            ts if isinstance(ts, str) else str(ts)
                                        )
                                    except Exception:
                                        published_at = None

                                update_entities(all_entities, all_entities_original, source, published_at)
                                update_abstract_map(extracted, source, published_at)
                                total_processed += 1

                                id_log.write(global_id + "\n")  # 👈 写入带前缀的 ID
                                processed_ids.add(global_id)
                            else:
                                tools.log(f"🔍 新闻 {global_id}：LLM 返回事件但无有效实体，暂不标记")
                        else:
                            tools.log(f"⏳ 新闻 {global_id}：LLM 未返回有效事件，保留重试机会")

                    except Exception as e:
                        tools.log(f"⚠️ 处理单条新闻失败: {e}")
            
            # 处理完文件后删除对应的raw_news文件和该deduped_news文件
            try:
                # 找到对应的raw_news文件（去掉"_deduped"后缀）
                raw_file_name = file_path.stem.replace("_deduped", "") + ".jsonl"
                raw_file_path = tools.RAW_NEWS_DIR / raw_file_name
                
                # 删除raw_news文件
                if raw_file_path.exists():
                    raw_file_path.unlink()
                    tools.log(f"🗑️ 删除原始新闻文件: {raw_file_path.name}")
                
                # 删除deduped_news文件
                if file_path.exists():
                    file_path.unlink()
                    tools.log(f"🗑️ 删除去重新闻文件: {file_path.name}")
            except Exception as e:
                tools.log(f"⚠️ 删除文件失败: {e}")

    tools.log(f"✅ 完成！共处理 {total_processed} 条含有效实体的新闻")
    
    # 在所有新闻处理完成后统一刷新知识图谱
    if total_processed > 0:
        try:
            with tools._refresh_lock:
                threading.Thread(target=refresh_graph, daemon=True).start()
                tools.log("🔄 已启动知识图谱刷新线程")
        except Exception as e:
            tools.log(f"⚠️ 启动知识图谱刷新失败: {e}")
    else:
        tools.log("📭 未处理任何新闻，跳过知识图谱刷新")


# ======================
# 入口
# ======================

if __name__ == "__main__":
    process_news_stream()