"""
Snapshot/Run/Log 端口（Port）：
定义快照输出、运行记录、日志记录的抽象接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# Snapshot 相关
# =============================================================================


class GraphSnapshotType(Enum):
    """图谱快照类型"""
    GE = "GE"  # 实体-事件图
    GET = "GET"  # 实体-事件时间线
    EE = "EE"  # 实体-实体关系图
    EE_EVO = "EE_EVO"  # 实体-实体演化图
    EVENT_EVO = "EVENT_EVO"  # 事件演化图
    KG = "KG"  # 原始知识图谱


@dataclass
class SnapshotMeta:
    """快照元数据"""
    graph_type: GraphSnapshotType
    generated_at: datetime
    schema_version: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    node_count: int = 0
    edge_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_type": self.graph_type.value,
            "generated_at": self.generated_at.isoformat() if self.generated_at else "",
            "schema_version": self.schema_version,
            "params": self.params,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


@dataclass
class SnapshotNode:
    """快照节点（统一输出协议）"""
    id: str
    label: str
    type: str  # "entity" | "event" | "relation_state"
    color: str = "#1f77b4"
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "color": self.color,
            **self.attrs,
        }


@dataclass
class SnapshotEdge:
    """快照边（统一输出协议，强制带 time）"""
    from_node: str
    to_node: str
    type: str  # "involved_in" | "relation" | "follows" | "affects" | ...
    title: str = ""
    time: Optional[datetime] = None
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "type": self.type,
            "title": self.title,
            "time": self.time.isoformat() if self.time else "",
            **self.attrs,
        }


@dataclass
class Snapshot:
    """完整快照（统一输出协议）"""
    meta: SnapshotMeta
    nodes: List[SnapshotNode] = field(default_factory=list)
    edges: List[SnapshotEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


@dataclass
class SnapshotParams:
    """快照生成参数"""
    top_entities: int = 500
    top_events: int = 500
    max_edges: int = 5000
    days_window: int = 0  # 0 = 全部
    gap_days: int = 30  # EE_EVO 分段阈值


class SnapshotWriter(ABC):
    """
    快照写入器端口。
    """

    @abstractmethod
    def write(
        self,
        snapshot: Snapshot,
        output_path: Path,
    ) -> bool:
        """
        写入快照到文件。
        
        Args:
            snapshot: 快照数据
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        ...

    @abstractmethod
    def write_all(
        self,
        snapshots: Dict[GraphSnapshotType, Snapshot],
        output_dir: Path,
    ) -> Dict[str, str]:
        """
        批量写入所有快照。
        
        Args:
            snapshots: 快照字典
            output_dir: 输出目录
            
        Returns:
            文件路径映射
        """
        ...


class SnapshotReader(ABC):
    """
    快照读取器端口。
    """

    @abstractmethod
    def read(
        self,
        input_path: Path,
    ) -> Optional[Snapshot]:
        """
        从文件读取快照。
        
        Args:
            input_path: 输入路径
            
        Returns:
            快照数据，或 None
        """
        ...

    @abstractmethod
    def list_snapshots(
        self,
        snapshot_dir: Path,
    ) -> Dict[GraphSnapshotType, Path]:
        """
        列出目录下的快照文件。
        
        Args:
            snapshot_dir: 快照目录
            
        Returns:
            类型 -> 路径映射
        """
        ...


# =============================================================================
# Run Store（运行记录）
# =============================================================================


class RunStatus(Enum):
    """运行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunRecord:
    """运行记录"""
    run_id: str
    pipeline_name: str
    status: RunStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    snapshots_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "snapshots_paths": self.snapshots_paths,
            "error": self.error,
            "logs": self.logs[-100:],  # 只保留最近 100 条
        }


class RunStore(ABC):
    """
    运行记录仓储端口。
    """

    @abstractmethod
    def create_run(
        self,
        pipeline_name: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建运行记录，返回 run_id。
        """
        ...

    @abstractmethod
    def update_run(
        self,
        run_id: str,
        status: Optional[RunStatus] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        snapshots_paths: Optional[List[str]] = None,
    ) -> bool:
        """
        更新运行记录。
        """
        ...

    @abstractmethod
    def finish_run(
        self,
        run_id: str,
        status: RunStatus,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        完成运行。
        """
        ...

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """
        获取运行记录。
        """
        ...

    @abstractmethod
    def list_runs(
        self,
        pipeline_name: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[RunRecord]:
        """
        列出运行记录。
        """
        ...

    @abstractmethod
    def append_log(self, run_id: str, message: str) -> bool:
        """
        追加日志到运行记录。
        """
        ...


# =============================================================================
# Log Store（日志仓储）
# =============================================================================


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime
    level: LogLevel
    message: str
    source: str = ""  # 来源模块
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
            "context": self.context,
        }


class LogStore(ABC):
    """
    日志仓储端口。
    """

    @abstractmethod
    def log(
        self,
        level: LogLevel,
        message: str,
        source: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        记录日志。
        """
        ...

    @abstractmethod
    def info(self, message: str, source: str = "", **context) -> None:
        """记录 INFO 日志"""
        ...

    @abstractmethod
    def warning(self, message: str, source: str = "", **context) -> None:
        """记录 WARNING 日志"""
        ...

    @abstractmethod
    def error(self, message: str, source: str = "", **context) -> None:
        """记录 ERROR 日志"""
        ...

    @abstractmethod
    def debug(self, message: str, source: str = "", **context) -> None:
        """记录 DEBUG 日志"""
        ...

    @abstractmethod
    def list_logs(
        self,
        level: Optional[LogLevel] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[LogEntry]:
        """
        查询日志。
        """
        ...

    @abstractmethod
    def clear_logs(
        self,
        before: Optional[datetime] = None,
    ) -> int:
        """
        清理日志，返回清理数量。
        """
        ...
