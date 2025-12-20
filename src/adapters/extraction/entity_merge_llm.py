"""
适配器层 - 基于LLM的实体合并决策器

使用LLM完全替代硬编码的实体类型判断和合并决策逻辑。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from ...ports.llm_client import LLMClient, LLMCallConfig, LLMResponse
from ...infra import get_logger, extract_json_from_llm_response


class EntityType(Enum):
    """实体类型枚举"""
    PERSON = "自然人"
    ORGANIZATION = "注册公司"
    GOVERNMENT = "政府机构或部门"
    GEOGRAPHIC = "主权国家或明确行政区"
    INTERNATIONAL_ORG = "国际组织"
    PRODUCT = "重要产品品牌及其型号"
    OTHER = "其他"


@dataclass
class EntityAnalysis:
    """实体分析结果"""
    entity: str
    entity_type: EntityType
    confidence: float
    reasoning: str = ""


@dataclass
class MergeGroup:
    """合并组"""
    primary_entity: str
    duplicate_entities: List[str]
    reason: str
    confidence: float


@dataclass
class EntityMergeDecision:
    """实体合并决策结果"""
    entity_analyses: List[EntityAnalysis]
    merge_groups: List[MergeGroup]
    processing_log: str = ""


class LLMEntityMergeDecider:
    """基于LLM的实体合并决策器"""

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        self._logger = get_logger(__name__)

    def decide_entity_merges(
        self,
        entities_batch: List[str],
        evidence_map: Optional[Dict[str, List[str]]] = None,
        timeout_seconds: int = 90
    ) -> EntityMergeDecision:
        """
        使用LLM决定实体合并策略
        
        Args:
            entities_batch: 实体列表
            evidence_map: 实体相关证据映射
            timeout_seconds: LLM调用超时时间
            
        Returns:
            EntityMergeDecision: 合并决策结果
        """
        if not entities_batch:
            return EntityMergeDecision([], [])

        try:
            # 构建提示
            prompt = self._create_merge_prompt(entities_batch, evidence_map or {})
            
            # 调用LLM
            config = LLMCallConfig(
                max_tokens=4000,
                timeout_seconds=timeout_seconds,
                temperature=0.3  # 使用较低温度以获得更一致的结果
            )
            
            response = self._llm.call(prompt, config)
            
            if not response.success:
                self._logger.error(f"LLM调用失败: {response.error}")
                return EntityMergeDecision(
                    [], 
                    [], 
                    processing_log=f"LLM调用失败: {response.error}"
                )
            
            # 解析响应
            return self._parse_llm_response(response.content)
            
        except Exception as e:
            self._logger.error(f"实体合并决策过程中出错: {e}", exc_info=True)
            return EntityMergeDecision(
                [], 
                [], 
                processing_log=f"处理过程中出错: {str(e)}"
            )

    def _create_merge_prompt(
        self, 
        entities_batch: List[str], 
        evidence_map: Dict[str, List[str]]
    ) -> str:
        """
        创建实体合并决策提示
        
        Args:
            entities_batch: 实体列表
            evidence_map: 实体相关证据映射
            
        Returns:
            str: 完整的提示文本
        """
        # 构建证据行
        evidence_lines = []
        for ent, evs in evidence_map.items():
            if evs:
                for ev in evs:
                    evidence_lines.append(f"{ent} <= {ev}")

        return f"""你是一名专业的知识图谱专家。你的任务是对一组实体进行分析，判断它们是否代表同一主体的不同表述，并为可合并的实体选择最佳的主实体名称。

【任务说明】
你需要完成三个子任务：
1. 为每个实体判断其准确的实体类型（自然人/注册公司/政府机构或部门/主权国家或明确行政区/国际组织/重要产品品牌及其型号/其他）
2. 判断哪些实体可以合并（代表同一主体）
3. 为可合并的实体组选择最佳的主实体名称

【实体列表】
{json.dumps(entities_batch, ensure_ascii=False, indent=2)}

【证据（相关事件摘要，供参考）】
格式: 实体 <= 摘要 | 参与实体 | 描述
{chr(10).join(evidence_lines) if evidence_lines else "（无可用事件，谨慎合并）"}

【实体类型判断标准】
- 自然人：真实存在的人，如 Elon Musk、Cathie Wood、Warren Buffett
- 注册公司：依法注册的企业法人，如 Apple Inc.、Goldman Sachs、中国工商银行、Volkswagen AG
- 政府机构或部门：行使公共职能的政府部门，如 美国证券交易委员会、中国人民银行、欧盟委员会、日本金融厅
- 主权国家或明确行政区：国家、省、州、市等明确的地理行政单位，如 美国、新加坡、加利福尼亚州、香港特别行政区、德意志联邦共和国
- 国际组织：跨国的政府间或非政府组织，如 国际货币基金组织、世界银行、联合国、金融稳定理事会
- 重要产品品牌及其型号：由明确主体生产/提供的具体产品或品牌，如 iPhone 15 Pro、Tesla Model 3、ChatGPT、Windows 11、Redmi 12C
- 其他：不属于以上分类的实体

【合并判断标准】
- 只有在同一类型且代表同一主体的实体才可以合并
- 合并包括：同名不同表述、中英文译名、缩写与全称、官方名称与常用名称等
- 以下是绝对不可以合并的情况：
  * 不同类型的实体（如人名与公司名）
  * 行使职能的组织与其下辖的具体职能部门
  * 不同国家/地区的同名机构
  * 上市公司与子公司/控股股东
  * 政府部门与上级政府
  * 国家/省州/城市/区县之间的层级关系
  * 公司/机构与它们的产品/品牌/型号
  * 媒体名称与地理位置/政府/企业/人名
  * 体育俱乐部/赛事与城市/国家/政府/个人

【主实体选择标准】
对于可以合并的实体组，选择最佳主实体的标准（按优先级排序）：
1. 更通用、更标准的表述
2. 更倾向于中文的表述
3. 更详细、更精确的表述
4. 更学术、更正式的表述
5. 在证据中出现频率更高的表述

【输出格式】
严格按照以下JSON格式输出：

{{
  "entity_analysis": [
    {{
      "entity": "实体名称",
      "type": "实体类型（从上面的分类中选择）",
      "confidence": 0.95,  // 置信度，0-1之间
      "reasoning": "判断理由（简要说明为什么认为该实体属于此类型）"
    }}
  ],
  "merge_groups": [
    {{
      "primary_entity": "最佳主实体名称",
      "duplicate_entities": ["别名1", "别名2"],  // 不包括主实体本身
      "reason": "合并理由（简要说明为什么这些实体代表同一主体）",
      "confidence": 0.90  // 合并置信度，0-1之间
    }}
  ]
}}

如果没有可合并的实体，merge_groups返回空数组。
只输出JSON，不要有任何额外的解释文字。
"""

    def _parse_llm_response(self, response_text: str) -> EntityMergeDecision:
        """
        解析LLM响应
        
        Args:
            response_text: LLM响应文本
            
        Returns:
            EntityMergeDecision: 解析后的决策结果
        """
        try:
            # 提取JSON
            data = extract_json_from_llm_response(response_text)
            
            # 解析实体分析结果
            entity_analyses = []
            for item in data.get("entity_analysis", []):
                try:
                    entity_type = EntityType(item["type"])
                except ValueError:
                    # 如果类型不匹配，使用OTHER
                    entity_type = EntityType.OTHER
                    
                analysis = EntityAnalysis(
                    entity=item["entity"],
                    entity_type=entity_type,
                    confidence=float(item.get("confidence", 0.0)),
                    reasoning=item.get("reasoning", "")
                )
                entity_analyses.append(analysis)
            
            # 解析合并组
            merge_groups = []
            for item in data.get("merge_groups", []):
                group = MergeGroup(
                    primary_entity=item["primary_entity"],
                    duplicate_entities=item["duplicate_entities"],
                    reason=item["reason"],
                    confidence=float(item.get("confidence", 0.0))
                )
                merge_groups.append(group)
            
            return EntityMergeDecision(
                entity_analyses=entity_analyses,
                merge_groups=merge_groups,
                processing_log="成功解析LLM响应"
            )
            
        except Exception as e:
            self._logger.error(f"解析LLM响应时出错: {e}", exc_info=True)
            return EntityMergeDecision(
                [], 
                [], 
                processing_log=f"解析LLM响应时出错: {str(e)}"
            )


# 便捷函数
def create_entity_merge_decider(llm_client: LLMClient) -> LLMEntityMergeDecider:
    """
    创建实体合并决策器实例
    
    Args:
        llm_client: LLM客户端
        
    Returns:
        LLMEntityMergeDecider: 实体合并决策器实例
    """
    return LLMEntityMergeDecider(llm_client)