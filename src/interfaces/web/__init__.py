"""
Web Interfaces 子包。

提供 Web UI 相关的接口和协议：
- snapshot_protocol: 快照协议（统一的 nodes/edges/meta 格式）
"""

from .snapshot_protocol import (
    GRAPH_TYPE_LABELS,
    NODE_COLORS,
    SnapshotLoader,
    RenderConfig,
    FilterConfig,
    SnapshotTransformer,
)

__all__ = [
    "GRAPH_TYPE_LABELS",
    "NODE_COLORS",
    "SnapshotLoader",
    "RenderConfig",
    "FilterConfig",
    "SnapshotTransformer",
]
