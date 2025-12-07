import json
import time
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
from ..utils.tool_function import tools
from .api_client import LLMAPIPool

class KnowledgeGraph:
    """
    压缩知识图谱系统，用于管理实体和事件，支持重复检测和更新。
    """
    
    def __init__(self):
        self.tools = tools()
        self.entities_file = self.tools.ENTITIES_FILE
        self.events_file = self.tools.EVENTS_FILE
        self.abstract_map_file = self.tools.ABSTRACT_MAP_FILE
        self.kg_file = self.tools.KNOWLEDGE_GRAPH_FILE
        self.graph = {
            "entities": {},  # 实体ID -> 实体信息
            "events": {},   # 事件摘要 -> 事件信息
            "edges": []     # 边列表，连接实体和事件
        }
        self.llm_pool = None  # 延迟初始化
        
    def _init_llm_pool(self):
        """初始化LLM API池"""
        if self.llm_pool is None:
            try:
                self.llm_pool = LLMAPIPool()
                self.tools.log("[知识图谱] LLM API池初始化成功")
            except Exception as e:
                self.tools.log(f"[知识图谱] ❌ 初始化LLM API池失败: {e}")
                self.llm_pool = None
    
    def load_data(self) -> bool:
        """从文件加载实体和事件数据"""
        try:
            if self.entities_file.exists():
                with open(self.entities_file, 'r', encoding='utf-8') as f:
                    self.graph['entities'] = json.load(f)
            else:
                self.graph['entities'] = {}
                
            if self.abstract_map_file.exists():
                with open(self.abstract_map_file, 'r', encoding='utf-8') as f:
                    abstract_map = json.load(f)
                    # 转换abstract_map为事件格式
                    self.graph['events'] = {
                        abstract: {
                            "abstract": abstract,
                            "entities": data["entities"],
                            "event_summary": data.get("event_summary", ""),
                            "sources": data.get("sources", []),
                            "first_seen": data.get("first_seen", "")
                        }
                        for abstract, data in abstract_map.items()
                    }
            else:
                self.graph['events'] = {}
                
            self._build_edges()
            self.tools.log(f"[知识图谱] 数据加载成功: {len(self.graph['entities'])} 实体, {len(self.graph['events'])} 事件")
            return True
        except Exception as e:
            self.tools.log(f"[知识图谱] ❌ 加载数据失败: {e}")
            return False
    
    def _build_edges(self):
        """构建实体和事件之间的边"""
        self.graph['edges'] = []
        for abstract, event in self.graph['events'].items():
            for entity in event.get('entities', []):
                if entity in self.graph['entities']:
                    self.graph['edges'].append({
                        "from": entity,
                        "to": abstract,
                        "type": "involved_in"
                    })
    
    def build_graph(self) -> bool:
        """构建知识图谱"""
        return self.load_data()
    
    def compress_with_llm(self) -> Dict[str, List[str]]:
        """
        使用LLM分析压缩知识图谱，输出重复的实体和事件抽象。
        返回格式: {"duplicate_entities": [实体列表], "duplicate_events": [事件摘要列表]}
        """
        self._init_llm_pool()
        if self.llm_pool is None:
            self.tools.log("[知识图谱] ❌ LLM不可用，跳过压缩")
            return {"duplicate_entities": [], "duplicate_events": []}
        
        # 准备LLM提示
        prompt = self._prepare_compression_prompt()
        
        max_retries = 2
        raw_content = self.llm_pool.call(
            prompt=prompt,
            max_tokens=8000,
            timeout=55,
            retries=max_retries
        )
        
        if not raw_content:
            self.tools.log("[知识图谱] ❌ LLM调用失败")
            return {"duplicate_entities": [], "duplicate_events": []}
        
        # 解析LLM响应
        duplicates = self._parse_llm_response(raw_content)
        return duplicates
    
    def _prepare_compression_prompt(self) -> str:
        """准备LLM提示，用于检测重复实体和事件"""
        entities_list = list(self.graph['entities'].keys())
        events_list = list(self.graph['events'].keys())
        
        prompt = f"""你是一名知识图谱专家，负责检测重复的实体和事件。

【实体列表】
{json.dumps(entities_list, ensure_ascii=False, indent=2)}

【事件列表】
每个事件格式: 摘要 | 实体 | 事件描述
"""
        for abstract, event in self.graph['events'].items():
            entities = event.get('entities', [])
            summary = event.get('event_summary', '')
            prompt += f"{abstract} | {', '.join(entities)} | {summary}\n"
        
        prompt += """
【任务】
1. 分析实体列表，找出可能表示同一实体的重复项（例如，别名、缩写、不同语言表述）。
2. 分析事件列表，找出可能描述同一事件的重复项（基于实体重叠和描述相似性）。
3. 输出JSON格式：
{
  "duplicate_entities": [
    ["实体1", "实体2", ...],  // 第一组重复实体
    ["实体3", "实体4", ...]   // 第二组重复实体
  ],
  "duplicate_events": [
    ["事件摘要1", "事件摘要2", ...],  // 第一组重复事件
    ["事件摘要3", "事件摘要4", ...]   // 第二组重复事件
  ]
}

注意：
- 只输出JSON，不要额外文本。
- 每组重复项至少包含两个元素。
- 如果没有重复，返回空数组。
"""
        return prompt
    
    def _parse_llm_response(self, raw_content: str) -> Dict[str, List[List[str]]]:
        """解析LLM响应，提取重复项"""
        try:
            # 清理Markdown包裹
            if raw_content.startswith("```json"):
                raw_content = raw_content.split("```json", 1)[1].split("```")[0]
            elif raw_content.startswith("```"):
                raw_content = raw_content.split("```", 1)[1].split("```")[0]
            
            data = json.loads(raw_content)
            duplicate_entities = data.get("duplicate_entities", [])
            duplicate_events = data.get("duplicate_events", [])
            
            # 验证格式
            if not isinstance(duplicate_entities, list) or not isinstance(duplicate_events, list):
                raise ValueError("Invalid format")
            
            self.tools.log(f"[知识图谱] LLM检测到 {len(duplicate_entities)} 组重复实体, {len(duplicate_events)} 组重复事件")
            return {
                "duplicate_entities": duplicate_entities,
                "duplicate_events": duplicate_events
            }
        except Exception as e:
            self.tools.log(f"[知识图谱] ❌ 解析LLM响应失败: {e}")
            return {"duplicate_entities": [], "duplicate_events": []}
    
    def update_entities_and_events(self, duplicates: Dict[str, List[List[str]]]):
        """根据重复检测结果更新实体库和事件库"""
        updated = False
        
        # 合并重复实体
        for group in duplicates.get("duplicate_entities", []):
            if len(group) < 2:
                continue
            primary = group[0]  # 选择第一个作为主实体
            for duplicate in group[1:]:
                if duplicate in self.graph['entities']:
                    # 将重复实体的信息合并到主实体
                    self._merge_entities(primary, duplicate)
                    updated = True
        
        # 合并重复事件
        for group in duplicates.get("duplicate_events", []):
            if len(group) < 2:
                continue
            primary = group[0]
            for duplicate in group[1:]:
                if duplicate in self.graph['events']:
                    self._merge_events(primary, duplicate)
                    updated = True
        
        if updated:
            self._save_data()
            self.tools.log("[知识图谱] 实体和事件更新完成")
        else:
            self.tools.log("[知识图谱] 无重复项需要更新")
    
    def _merge_entities(self, primary: str, duplicate: str):
        """合并重复实体"""
        if primary not in self.graph['entities'] or duplicate not in self.graph['entities']:
            return
        
        primary_data = self.graph['entities'][primary]
        duplicate_data = self.graph['entities'][duplicate]
        
        # 合并sources
        primary_sources = set(primary_data.get('sources', []))
        duplicate_sources = set(duplicate_data.get('sources', []))
        primary_data['sources'] = list(primary_sources.union(duplicate_sources))
        
        # 合并original_forms
        primary_forms = set(primary_data.get('original_forms', []))
        duplicate_forms = set(duplicate_data.get('original_forms', []))
        primary_data['original_forms'] = list(primary_forms.union(duplicate_forms))
        
        # 更新first_seen为更早的时间
        primary_first = primary_data.get('first_seen', '')
        duplicate_first = duplicate_data.get('first_seen', '')
        if duplicate_first and (not primary_first or duplicate_first < primary_first):
            primary_data['first_seen'] = duplicate_first
        
        # 删除重复实体
        del self.graph['entities'][duplicate]
        
        # 更新事件中的实体引用
        for abstract, event in self.graph['events'].items():
            entities = event.get('entities', [])
            if duplicate in entities:
                # 替换为primary，并去重
                new_entities = [primary if ent == duplicate else ent for ent in entities]
                # 去重
                unique_entities = []
                seen = set()
                for ent in new_entities:
                    if ent not in seen:
                        seen.add(ent)
                        unique_entities.append(ent)
                event['entities'] = unique_entities
        
        self.tools.log(f"[知识图谱] 合并实体: {duplicate} -> {primary}")
    
    def _merge_events(self, primary: str, duplicate: str):
        """合并重复事件"""
        if primary not in self.graph['events'] or duplicate not in self.graph['events']:
            return
        
        primary_event = self.graph['events'][primary]
        duplicate_event = self.graph['events'][duplicate]
        
        # 合并sources
        primary_sources = set(primary_event.get('sources', []))
        duplicate_sources = set(duplicate_event.get('sources', []))
        primary_event['sources'] = list(primary_sources.union(duplicate_sources))
        
        # 合并entities
        primary_entities = set(primary_event.get('entities', []))
        duplicate_entities = set(duplicate_event.get('entities', []))
        primary_event['entities'] = list(primary_entities.union(duplicate_entities))
        
        # 更新first_seen
        primary_first = primary_event.get('first_seen', '')
        duplicate_first = duplicate_event.get('first_seen', '')
        if duplicate_first and (not primary_first or duplicate_first < primary_first):
            primary_event['first_seen'] = duplicate_first
        
        # 事件描述合并：保留更详细的
        if not primary_event.get('event_summary') and duplicate_event.get('event_summary'):
            primary_event['event_summary'] = duplicate_event['event_summary']
        
        # 删除重复事件
        del self.graph['events'][duplicate]
        
        self.tools.log(f"[知识图谱] 合并事件: {duplicate} -> {primary}")
    
    def _save_data(self):
        """保存更新后的数据到文件"""
        try:
            # 保存实体
            with open(self.entities_file, 'w', encoding='utf-8') as f:
                json.dump(self.graph['entities'], f, ensure_ascii=False, indent=2)
            
            # 保存事件（abstract_map格式）
            abstract_map = {}
            for abstract, event in self.graph['events'].items():
                abstract_map[abstract] = {
                    "entities": event.get('entities', []),
                    "event_summary": event.get('event_summary', ''),
                    "sources": event.get('sources', []),
                    "first_seen": event.get('first_seen', '')
                }
            
            with open(self.abstract_map_file, 'w', encoding='utf-8') as f:
                json.dump(abstract_map, f, ensure_ascii=False, indent=2)
            
            # 保存知识图谱状态（可选）
            with open(self.kg_file, 'w', encoding='utf-8') as f:
                json.dump(self.graph, f, ensure_ascii=False, indent=2)
            
            self.tools.log("[知识图谱] 数据保存完成")
        except Exception as e:
            self.tools.log(f"[知识图谱] ❌ 保存数据失败: {e}")
    
    def refresh_graph(self):
        """刷新知识图谱：构建、压缩、更新"""
        self.tools.log("[知识图谱] 开始刷新知识图谱")
        
        # 构建图
        if not self.build_graph():
            self.tools.log("[知识图谱] ❌ 构建图失败")
            return
        
        # 压缩：使用LLM检测重复
        duplicates = self.compress_with_llm()
        
        # 更新实体和事件
        self.update_entities_and_events(duplicates)
        
        self.tools.log("[知识图谱] 知识图谱刷新完成")

# 全局函数，供agent1和agent2调用
def refresh_graph():
    """刷新知识图谱（供外部调用）"""
    kg = KnowledgeGraph()
    kg.refresh_graph()

def build_graph() -> bool:
    """构建知识图谱"""
    kg = KnowledgeGraph()
    return kg.build_graph()

if __name__ == "__main__":
    # 测试代码
    kg = KnowledgeGraph()
    kg.refresh_graph()
