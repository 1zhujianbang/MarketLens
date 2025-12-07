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
        self.merge_rules_file = self.tools.CONFIG_DIR / "entity_merge_rules.json" # 规则文件路径
        self.merge_rules = {} # 内存中的规则缓存
        self.graph = {
            "entities": {},  # 实体ID -> 实体信息
            "events": {},   # 事件摘要 -> 事件信息
            "edges": []     # 边列表，连接实体和事件
        }
        self.llm_pool = None  # 延迟初始化
        self._load_merge_rules() # 初始化时加载规则
        
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
    
    def _load_merge_rules(self):
        """加载实体合并规则"""
        if self.merge_rules_file.exists():
            try:
                with open(self.merge_rules_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.merge_rules = data.get("merge_rules", {})
                self.tools.log(f"[知识图谱] 已加载 {len(self.merge_rules)} 条实体合并规则")
            except Exception as e:
                self.tools.log(f"[知识图谱] ⚠️ 加载合并规则失败: {e}")
        else:
            self.merge_rules = {}

    def _save_merge_rules(self):
        """保存实体合并规则"""
        try:
            data = {
                "merge_rules": self.merge_rules,
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            with open(self.merge_rules_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.tools.log(f"[知识图谱] 已保存合并规则库 (共 {len(self.merge_rules)} 条)")
        except Exception as e:
            self.tools.log(f"[知识图谱] ❌ 保存合并规则失败: {e}")

    def _apply_merge_rules(self) -> bool:
        """
        应用本地合并规则
        返回: 是否有更新
        """
        updated = False
        if not self.merge_rules:
            return False
            
        # 遍历现有实体，看是否匹配规则
        # 注意：需要在遍历时处理，避免字典大小变化问题，通常收集后再处理
        to_merge = []
        for entity in list(self.graph['entities'].keys()):
            if entity in self.merge_rules:
                target = self.merge_rules[entity]
                # 只有当目标实体也存在，或者目标就是我们想要统一到的名称时（这里简化为如果目标在库里或我们决定改名）
                # 为简单起见，我们假设规则是 A -> B，如果 A 存在，就尝试合并到 B。
                # 如果 B 不在库里，就把 A 重命名为 B。
                if target != entity:
                    to_merge.append((target, entity))
        
        for primary, duplicate in to_merge:
            # 如果目标实体不存在，先重命名
            if primary not in self.graph['entities'] and duplicate in self.graph['entities']:
                self.graph['entities'][primary] = self.graph['entities'][duplicate]
                del self.graph['entities'][duplicate]
                # 更新事件引用
                for abstract, event in self.graph['events'].items():
                    entities = event.get('entities', [])
                    if duplicate in entities:
                        event['entities'] = [primary if e == duplicate else e for e in entities]
                self.tools.log(f"[知识图谱][规则] 重命名实体: {duplicate} -> {primary}")
                updated = True
            elif primary in self.graph['entities'] and duplicate in self.graph['entities']:
                # 如果都存在，则合并
                self._merge_entities(primary, duplicate)
                updated = True
                
        return updated

    def compress_with_llm(self) -> Dict[str, List[str]]:
        """
        使用LLM分析压缩知识图谱，输出重复的实体和事件抽象。
        分批处理以避免上下文超长。
        集成规则优先策略。
        """
        # 0. 首先应用本地规则
        rule_applied = self._apply_merge_rules()
        if rule_applied:
            self._save_data() # 规则应用后先保存一次状态
            
        self._init_llm_pool()
        if self.llm_pool is None:
            self.tools.log("[知识图谱] ❌ LLM不可用，跳过压缩")
            return {"duplicate_entities": [], "duplicate_events": []}
        
        all_duplicate_entities = []
        all_duplicate_events = []
        
        # 1. 处理实体 (分批)
        # 排序以增加相似实体相邻的概率
        entities_list = sorted(list(self.graph['entities'].keys()))
        BATCH_SIZE_ENT = 100
        
        for i in range(0, len(entities_list), BATCH_SIZE_ENT):
            batch = entities_list[i:i+BATCH_SIZE_ENT]
            # 过滤掉已经在规则库中的实体作为duplicate的情况，避免重复计算（可选优化）
            
            self.tools.log(f"[知识图谱] 处理实体批次 {i//BATCH_SIZE_ENT + 1}/{(len(entities_list)-1)//BATCH_SIZE_ENT + 1} (大小: {len(batch)})")
            
            prompt = self._prepare_entity_compression_prompt(batch)
            response = self._call_llm(prompt, timeout=90)
            if response:
                batch_dupes = self._parse_entity_response(response)
                if batch_dupes:
                    # 更新规则库
                    new_rules_count = 0
                    for group in batch_dupes:
                        if len(group) >= 2:
                            primary = group[0]
                            for duplicate in group[1:]:
                                if duplicate not in self.merge_rules:
                                    self.merge_rules[duplicate] = primary
                                    new_rules_count += 1
                    if new_rules_count > 0:
                        self._save_merge_rules()
                        
                all_duplicate_entities.extend(batch_dupes)
                
        # 2. 处理事件 (分批)
        # 简单按key排序，理想情况下应按内容聚类，这里暂用排序
        events_list = sorted(list(self.graph['events'].keys()))
        BATCH_SIZE_EVT = 30
        
        for i in range(0, len(events_list), BATCH_SIZE_EVT):
            batch_keys = events_list[i:i+BATCH_SIZE_EVT]
            batch_events = {k: self.graph['events'][k] for k in batch_keys}
            self.tools.log(f"[知识图谱] 处理事件批次 {i//BATCH_SIZE_EVT + 1}/{(len(events_list)-1)//BATCH_SIZE_EVT + 1} (大小: {len(batch_keys)})")
            
            prompt = self._prepare_event_compression_prompt(batch_events)
            response = self._call_llm(prompt, timeout=120)
            if response:
                batch_dupes = self._parse_event_response(response)
                all_duplicate_events.extend(batch_dupes)

        return {
            "duplicate_entities": all_duplicate_entities, 
            "duplicate_events": all_duplicate_events
        }

    def _call_llm(self, prompt: str, timeout: int) -> Optional[str]:
        """统一LLM调用"""
        return self.llm_pool.call(
            prompt=prompt,
            max_tokens=4000,
            timeout=timeout,
            retries=2
        )

    def _prepare_entity_compression_prompt(self, entities_batch: List[str]) -> str:
        prompt = f"""你是一名知识图谱专家。请分析以下实体列表，找出表示**同一真实世界主体**的重复项（如别名、缩写、中英文名）。

【实体列表】
{json.dumps(entities_batch, ensure_ascii=False, indent=2)}

【实体定义参考】
- 自然人、注册公司、政府机构、国际组织等。

【输出格式】
严格返回 JSON：
{{
  "duplicate_entities": [
    ["实体A的全称", "实体A的缩写"], 
    ["实体B中文名", "实体B英文名"]
  ]
}}
如果没有重复，返回 {{ "duplicate_entities": [] }}。只输出JSON，不要其他废话。
"""
        return prompt

    def _prepare_event_compression_prompt(self, events_batch: Dict) -> str:
        prompt = f"""你是一名知识图谱专家。请分析以下事件列表，找出描述**同一具体事件**的重复项。

【事件列表】
格式: 摘要 | 参与实体 | 事件描述
"""
        for abstract, event in events_batch.items():
            entities = event.get('entities', [])
            summary = event.get('event_summary', '')
            prompt += f"{abstract} | {', '.join(entities)} | {summary}\n"

        prompt += """
【任务】
找出语义上高度重叠、描述同一事实的事件。

【输出格式】
严格返回 JSON：
{
  "duplicate_events": [
    ["事件摘要1", "事件摘要2"],
    ["事件摘要3", "事件摘要4", "事件摘要5"]
  ]
}
如果没有重复，返回 { "duplicate_events": [] }。只输出JSON。
"""
        return prompt

    def _parse_entity_response(self, raw_content: str) -> List[List[str]]:
        try:
            data = self._extract_json(raw_content)
            res = data.get("duplicate_entities", [])
            return res if isinstance(res, list) else []
        except Exception:
            return []

    def _parse_event_response(self, raw_content: str) -> List[List[str]]:
        try:
            data = self._extract_json(raw_content)
            res = data.get("duplicate_events", [])
            return res if isinstance(res, list) else []
        except Exception:
            return []

    def _extract_json(self, text: str) -> Dict:
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```")[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```")[0]
        return json.loads(text)
    
    # 旧方法保留或删除（这里替换旧的 _prepare_compression_prompt 和 _parse_llm_response）
    
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
        
        # 合并sources (确保转换为可哈希的tuple或直接列表处理)
        primary_sources = set()
        for s in primary_data.get('sources', []):
            if isinstance(s, list): primary_sources.add(tuple(s))
            elif isinstance(s, dict): continue # 暂时忽略复杂结构
            else: primary_sources.add(s)
            
        for s in duplicate_data.get('sources', []):
            if isinstance(s, list): primary_sources.add(tuple(s))
            elif isinstance(s, dict): continue 
            else: primary_sources.add(s)
            
        # 转回list
        primary_data['sources'] = list(primary_sources)
        
        # 合并original_forms
        primary_forms = set()
        for f in primary_data.get('original_forms', []):
            if isinstance(f, list): primary_forms.add(tuple(f))
            elif isinstance(f, dict): continue
            else: primary_forms.add(f)
            
        for f in duplicate_data.get('original_forms', []):
            if isinstance(f, list): primary_forms.add(tuple(f))
            elif isinstance(f, dict): continue
            else: primary_forms.add(f)
            
        primary_data['original_forms'] = list(primary_forms)
        
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
        primary_sources = set()
        for s in primary_event.get('sources', []):
            if isinstance(s, list): primary_sources.add(tuple(s))
            elif isinstance(s, dict): continue
            else: primary_sources.add(s)
            
        for s in duplicate_event.get('sources', []):
            if isinstance(s, list): primary_sources.add(tuple(s))
            elif isinstance(s, dict): continue
            else: primary_sources.add(s)
            
        primary_event['sources'] = list(primary_sources)
        
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
