from typing import Any, Dict, List, Optional
from datetime import datetime
import json

class PipelineContext:
    """
    流程执行上下文
    用于在 Pipeline 的不同 Task 之间传递数据，并记录执行日志。
    """
    def __init__(self, initial_data: Dict[str, Any] = None, log_callback=None):
        self._store: Dict[str, Any] = initial_data or {}
        self._logs: List[Dict[str, str]] = []
        self._execution_history: List[Dict[str, Any]] = []
        self.log_callback = log_callback

    def set(self, key: str, value: Any):
        """设置上下文变量"""
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        # 支持嵌套键访问，例如 "news.data.0" (简化版暂只支持一级)
        return self._store.get(key, default)

    def log(self, message: str, level: str = "INFO", source: str = "System"):
        """记录日志"""
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "message": message
        }
        self._logs.append(entry)
        # 简单控制台输出，后续可对接更复杂的日志系统
        print(f"[{timestamp}] [{level}] [{source}] {message}")
        
        if self.log_callback:
            try:
                self.log_callback(entry)
            except Exception:
                pass

    def record_execution(self, tool_name: str, status: str, duration: float, error: str = None):
        """记录工具执行情况"""
        self._execution_history.append({
            "tool": tool_name,
            "status": status,
            "duration": duration,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

    def get_all(self) -> Dict[str, Any]:
        """获取所有数据"""
        return self._store

    @property
    def logs(self) -> List[Dict[str, str]]:
        return self._logs

    def to_json(self) -> str:
        """导出上下文状态（仅序列化部分）"""
        # 实际生产中要注意 value 是否可序列化
        serializable_store = {}
        for k, v in self._store.items():
            try:
                json.dumps(v)
                serializable_store[k] = v
            except (TypeError, OverflowError):
                serializable_store[k] = f"<Non-serializable: {type(v).__name__}>"
                
        return json.dumps({
            "store": serializable_store,
            "logs": self._logs,
            "history": self._execution_history
        }, ensure_ascii=False, indent=2)

