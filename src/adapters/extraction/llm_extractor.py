"""
适配器层 - LLM 抽取适配器

使用 LLM 实现实体和事件的抽取。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ...ports.extraction import (
    EntityExtractor, EventExtractor,
    ExtractedEntity, ExtractedEvent,
    EntityExtractionResult, EventExtractionResult
)
from ...ports.llm_client import LLMClient, LLMCallConfig
from ...infra import get_logger, extract_json_from_llm_response


class LLMEntityExtractor(EntityExtractor):
    """基于 LLM 的实体抽取器"""

    PROMPT_TEMPLATE = """请从以下新闻文本中抽取所有命名实体（人名、组织名、地点名）。

新闻文本：
{text}

请以 JSON 格式返回，格式如下：
{{
  "entities": [
    {{"name": "实体名称", "type": "PERSON/ORG/LOCATION", "confidence": 0.9}}
  ]
}}

只返回 JSON，不要有其他解释文字。"""

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        self._logger = get_logger(__name__)

    async def extract(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EntityExtractionResult:
        """从文本中抽取实体"""
        import time
        start_time = time.monotonic()

        try:
            prompt = self.PROMPT_TEMPLATE.format(text=text[:4000])

            response = self._llm.call(prompt, LLMCallConfig(max_tokens=1000))

            if not response.success:
                return EntityExtractionResult(
                    entities=[],
                    source_text=text,
                    success=False,
                    error=response.error
                )

            # 解析 JSON 响应
            try:
                data = extract_json_from_llm_response(response.content)
                entities = []

                for item in data.get("entities", []):
                    entities.append(ExtractedEntity(
                        name=item.get("name", ""),
                        entity_type=item.get("type", "UNKNOWN"),
                        confidence=float(item.get("confidence", 1.0)),
                        context=text[:200]
                    ))

                processing_time = (time.monotonic() - start_time) * 1000

                return EntityExtractionResult(
                    entities=entities,
                    source_text=text,
                    success=True,
                    processing_time_ms=processing_time
                )

            except Exception as e:
                self._logger.warning(f"Failed to parse entity extraction response: {e}")
                return EntityExtractionResult(
                    entities=[],
                    source_text=text,
                    success=False,
                    error=f"Parse error: {e}"
                )

        except Exception as e:
            self._logger.error(f"Entity extraction failed: {e}")
            return EntityExtractionResult(
                entities=[],
                source_text=text,
                success=False,
                error=str(e)
            )

    async def extract_batch(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[EntityExtractionResult]:
        """批量抽取实体"""
        results = []
        for text in texts:
            result = await self.extract(text, context)
            results.append(result)
        return results


class LLMEventExtractor(EventExtractor):
    """基于 LLM 的事件抽取器"""

    PROMPT_TEMPLATE = """请从以下新闻文本中抽取所有事件。

新闻文本：
{text}

请以 JSON 格式返回，格式如下：
{{
  "events": [
    {{
      "abstract": "事件简要描述（一句话）",
      "type": "事件类型（如：政治、经济、社会等）",
      "time": "事件发生时间（如有）",
      "location": "事件发生地点（如有）",
      "participants": ["参与实体1", "参与实体2"]
    }}
  ]
}}

只返回 JSON，不要有其他解释文字。"""

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        self._logger = get_logger(__name__)

    async def extract(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EventExtractionResult:
        """从文本中抽取事件"""
        import time
        start_time = time.monotonic()

        try:
            prompt = self.PROMPT_TEMPLATE.format(text=text[:4000])

            response = self._llm.call(prompt, LLMCallConfig(max_tokens=1500))

            if not response.success:
                return EventExtractionResult(
                    events=[],
                    source_text=text,
                    success=False,
                    error=response.error
                )

            # 解析 JSON 响应
            try:
                data = extract_json_from_llm_response(response.content)
                events = []

                for item in data.get("events", []):
                    event_time = None
                    if item.get("time"):
                        try:
                            event_time = datetime.fromisoformat(item["time"])
                        except Exception:
                            pass

                    events.append(ExtractedEvent(
                        abstract=item.get("abstract", ""),
                        event_type=item.get("type"),
                        time=event_time,
                        location=item.get("location"),
                        participants=item.get("participants", []),
                        confidence=float(item.get("confidence", 1.0))
                    ))

                processing_time = (time.monotonic() - start_time) * 1000

                return EventExtractionResult(
                    events=events,
                    source_text=text,
                    success=True,
                    processing_time_ms=processing_time
                )

            except Exception as e:
                self._logger.warning(f"Failed to parse event extraction response: {e}")
                return EventExtractionResult(
                    events=[],
                    source_text=text,
                    success=False,
                    error=f"Parse error: {e}"
                )

        except Exception as e:
            self._logger.error(f"Event extraction failed: {e}")
            return EventExtractionResult(
                events=[],
                source_text=text,
                success=False,
                error=str(e)
            )

    async def extract_batch(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[EventExtractionResult]:
        """批量抽取事件"""
        results = []
        for text in texts:
            result = await self.extract(text, context)
            results.append(result)
        return results
