import json
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional
from .tool_function import tools
from ..agents.agent3 import refresh_graph

def update_entities(entities: List[str], entities_original: List[str], source: str, published_at: Optional[str] = None):
    """自动写入主实体库

    时间戳使用新闻的发布时间（若提供），否则回退到当前时间。
    支持实体的原始语言表述，entities和entities_original数组的索引对应。
    """
    now = datetime.now(timezone.utc).isoformat()
    # 如果提供了发布时间，则优先使用该时间；否则使用当前时间
    base_ts = published_at or now
    existing = {}
    if tools.ENTITIES_FILE.exists():
        with open(tools.ENTITIES_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
    
    # 检查是否需要更新
    needs_update = False
    
    # 确保两个数组长度一致
    for ent, ent_original in zip(entities, entities_original):
        if ent not in existing:
            existing[ent] = {
                "first_seen": base_ts,
                "sources": [source],
                "original_forms": [ent_original]  # 新增：保存原始语言表述
            }
            needs_update = True
        else:
            # 如果已有 first_seen，且新闻时间更早，则更新为更早的时间
            try:
                old_ts = existing[ent].get("first_seen")
                if old_ts and base_ts and base_ts < old_ts:
                    existing[ent]["first_seen"] = base_ts
                    needs_update = True
            except Exception:
                # 异常时不强制更新，避免破坏已有数据
                pass

            if source not in existing[ent]["sources"]:
                existing[ent]["sources"].append(source)
                needs_update = True
            
            # 更新原始语言表述（去重）
            if "original_forms" not in existing[ent]:
                existing[ent]["original_forms"] = []
            if ent_original not in existing[ent]["original_forms"]:
                existing[ent]["original_forms"].append(ent_original)
                needs_update = True
    
    if needs_update:
        with open(tools.ENTITIES_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        # 知识图谱刷新将在上层流程统一触发

def update_abstract_map(extracted_list: List[Dict], source: str, published_at: Optional[str] = None):
    """更新事件映射"""
    abstract_map = {}
    if tools.ABSTRACT_MAP_FILE.exists():
        with open(tools.ABSTRACT_MAP_FILE, "r", encoding="utf-8") as f:
            abstract_map = json.load(f)
    
    now = datetime.now(timezone.utc).isoformat()
    base_ts = published_at or now
    
    # 检查是否需要更新
    needs_update = False
    for item in extracted_list:
        key = item["abstract"]
        if key not in abstract_map:
            abstract_map[key] = {
                "entities": item["entities"],
                "event_summary": item["event_summary"],
                "sources": [source],
                "first_seen": base_ts
            }
            needs_update = True
        else:
            # first_seen 取最早的发布时间
            try:
                old_ts = abstract_map[key].get("first_seen")
                if old_ts and base_ts and base_ts < old_ts:
                    abstract_map[key]["first_seen"] = base_ts
                    needs_update = True
            except Exception:
                pass

            if source not in abstract_map[key]["sources"]:
                abstract_map[key]["sources"].append(source)
                needs_update = True
            
            # 合并实体（去重）
            existing_entities = abstract_map[key]["entities"]
            new_entities = item["entities"]
            for ent in new_entities:
                if ent not in existing_entities:
                    existing_entities.append(ent)
                    needs_update = True
            
            # 事件摘要合并（如果新摘要不为空且与现有不同，则追加）
            existing_summary = abstract_map[key]["event_summary"]
            new_summary = item["event_summary"]
            if new_summary and new_summary != existing_summary:
                # 这里简单追加，可根据需要调整
                abstract_map[key]["event_summary"] = existing_summary + "; " + new_summary
                needs_update = True
    
    if needs_update:
        with open(tools.ABSTRACT_MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(abstract_map, f, ensure_ascii=False, indent=2)
        
        # 知识图谱刷新将在上层流程统一触发