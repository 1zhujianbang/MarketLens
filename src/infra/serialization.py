"""
基础设施层 - 序列化模块

提供安全的JSON序列化功能。
"""

import json
from datetime import datetime, date
from typing import Any, Dict


class Serializer:
    """安全序列化工具"""

    @staticmethod
    def safe_json_dumps(obj: Any, **kwargs) -> str:
        """
        安全的JSON序列化，自动处理常见不可序列化对象

        Args:
            obj: 要序列化的对象
            **kwargs: 传递给json.dumps的其他参数

        Returns:
            JSON字符串
        """
        def safe_serialize(o):
            """自定义序列化函数"""
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            elif hasattr(o, '__dict__'):
                return f"<Object: {type(o).__name__}>"
            elif isinstance(o, (set, frozenset)):
                return list(o)
            elif isinstance(o, complex):
                return str(o)
            elif callable(o):
                return f"<Callable: {o.__name__ if hasattr(o, '__name__') else type(o).__name__}>"
            else:
                raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

        json_kwargs = {
            'ensure_ascii': False,
            'indent': 2,
            'default': safe_serialize
        }
        json_kwargs.update(kwargs)

        try:
            return json.dumps(obj, **json_kwargs)
        except Exception as e:
            from .logging import get_logger
            logger = get_logger(__name__)
            logger.warning(f"序列化失败，使用降级方案: {e}")

            return json.dumps({
                "error": f"Serialization failed: {e}",
                "object_type": type(obj).__name__,
                "fallback": True,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False)

    @staticmethod
    def serialize_context(context) -> str:
        """
        专门用于PipelineContext的序列化

        Args:
            context: PipelineContext实例

        Returns:
            序列化后的JSON字符串
        """
        try:
            serializable_store = {}
            for k, v in context._store.items():
                try:
                    json.dumps(v, default=str)
                    serializable_store[k] = v
                except (TypeError, ValueError):
                    serializable_store[k] = f"<Non-serializable: {type(v).__name__}>"

            result = {
                "store": serializable_store,
                "logs": context._logs if hasattr(context, '_logs') else [],
                "execution_history": context._execution_history if hasattr(context, '_execution_history') else []
            }

            return Serializer.safe_json_dumps(result)

        except Exception as e:
            from .logging import get_logger
            logger = get_logger(__name__)
            logger.error(f"Context序列化完全失败: {e}")

            return json.dumps({
                "error": f"Context serialization failed: {e}",
                "store_keys": list(context._store.keys()) if hasattr(context, '_store') else [],
                "logs_count": len(context._logs) if hasattr(context, '_logs') else 0,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False)

    @staticmethod
    def serialize_for_logging(obj: Any) -> str:
        """
        为日志记录优化的序列化，简化输出

        Args:
            obj: 要序列化的对象

        Returns:
            简化的字符串表示
        """
        try:
            if isinstance(obj, dict):
                return f"Dict with keys: {list(obj.keys())}"
            elif isinstance(obj, (list, tuple)):
                return f"{type(obj).__name__} with {len(obj)} items"
            elif isinstance(obj, str) and len(obj) > 100:
                return f"String({len(obj)} chars): {obj[:50]}..."
            else:
                return Serializer.safe_json_dumps(obj, indent=None)
        except Exception:
            return f"<{type(obj).__name__}>"


# =============================================================================
# JSON 解析工具
# =============================================================================

def _strip_markdown_code_fence(text: str) -> str:
    """
    提取 ```json ... ``` 或 ``` ... ``` 的第一个代码块内容（若存在）。
    """
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return ""

    if "```json" in cleaned_text:
        parts = cleaned_text.split("```json", 1)
        if len(parts) > 1:
            return parts[1].split("```", 1)[0].strip()
        return ""

    if "```" in cleaned_text:
        parts = cleaned_text.split("```", 1)
        if len(parts) > 1:
            return parts[1].split("```", 1)[0].strip()
        return ""

    return cleaned_text


def _extract_json_object_span(text: str) -> str:
    """
    从文本中截取可能的 JSON（优先对象 {..}，其次数组 [..]）。
    """
    s = (text or "").strip()
    if not s:
        return ""

    # 优先尝试对象
    l = s.find("{")
    r = s.rfind("}")
    if l != -1 and r != -1 and r > l:
        return s[l:r + 1].strip()

    # 其次尝试数组
    l = s.find("[")
    r = s.rfind("]")
    if l != -1 and r != -1 and r > l:
        return s[l:r + 1].strip()

    return s


def extract_json_from_llm_response(text: str) -> Dict[str, Any]:
    """
    从LLM响应中提取JSON。

    Returns:
        解析后的JSON字典；若解析出的是 list，则自动包装为 {"events": list}

    Raises:
        json.JSONDecodeError: JSON解析失败时抛出
        ValueError: 文本格式异常时抛出
    """
    if not text or not str(text).strip():
        raise ValueError("输入文本为空")

    candidate = _strip_markdown_code_fence(str(text))
    candidate = _extract_json_object_span(candidate)
    candidate = (candidate or "").strip()

    if not candidate:
        raise ValueError("提取的JSON内容为空")

    parsed = json.loads(candidate)
    if isinstance(parsed, list):
        return {"events": parsed}
    if not isinstance(parsed, dict):
        raise ValueError("解析结果不是JSON对象")
    return parsed


def safe_json_loads(text: str, default=None) -> Any:
    """
    安全的JSON解析，失败时返回默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def format_json_for_llm(data: Any, indent: int = 2) -> str:
    """
    格式化数据为LLM友好的JSON字符串
    """
    return json.dumps(data, ensure_ascii=False, indent=indent)
