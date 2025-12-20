"""
导出适配器实现。

提供 JSON 导出和快照写入的具体实现。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...ports.snapshot import (
    GraphSnapshotType,
    Snapshot,
    SnapshotMeta,
    SnapshotWriter,
    SnapshotReader,
)


def _ensure_dir(p: Path) -> None:
    """确保目录存在"""
    p.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# JSON Snapshot Writer
# =============================================================================


class JsonSnapshotWriter(SnapshotWriter):
    """JSON 格式快照写入器"""

    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        self._indent = indent
        self._ensure_ascii = ensure_ascii

    def write(
        self,
        snapshot: Snapshot,
        output_path: Path,
    ) -> bool:
        try:
            _ensure_dir(output_path.parent)
            data = snapshot.to_dict()
            output_path.write_text(
                json.dumps(data, indent=self._indent, ensure_ascii=self._ensure_ascii),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            print(f"Failed to write snapshot to {output_path}: {e}")
            return False

    def write_all(
        self,
        snapshots: Dict[GraphSnapshotType, Snapshot],
        output_dir: Path,
    ) -> Dict[str, str]:
        _ensure_dir(output_dir)
        paths = {}
        for graph_type, snapshot in snapshots.items():
            filename = f"{graph_type.value}.json"
            output_path = output_dir / filename
            if self.write(snapshot, output_path):
                paths[graph_type.value] = str(output_path)
        return paths


# =============================================================================
# JSON Snapshot Reader
# =============================================================================


class JsonSnapshotReader(SnapshotReader):
    """JSON 格式快照读取器"""

    def read(
        self,
        input_path: Path,
    ) -> Optional[Snapshot]:
        if not input_path.exists():
            return None
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
            meta_data = data.get("meta", {})
            
            # 解析 graph_type
            graph_type_str = meta_data.get("graph_type", "KG")
            try:
                graph_type = GraphSnapshotType(graph_type_str)
            except ValueError:
                graph_type = GraphSnapshotType.KG
            
            # 解析 generated_at
            generated_at_str = meta_data.get("generated_at", "")
            try:
                generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
            except Exception:
                generated_at = datetime.now(timezone.utc)
            
            meta = SnapshotMeta(
                graph_type=graph_type,
                generated_at=generated_at,
                schema_version=meta_data.get("schema_version", ""),
                params=meta_data.get("params", {}),
                node_count=len(data.get("nodes", [])),
                edge_count=len(data.get("edges", [])),
            )
            
            # 这里简化处理，直接返回包含原始数据的 Snapshot
            # 完整实现需要解析 nodes 和 edges 为 SnapshotNode/SnapshotEdge 对象
            from ...ports.snapshot import SnapshotNode, SnapshotEdge
            
            nodes = []
            for n in data.get("nodes", []):
                if isinstance(n, dict):
                    nodes.append(SnapshotNode(
                        id=str(n.get("id", "")),
                        label=str(n.get("label", "")),
                        type=str(n.get("type", "entity")),
                        color=str(n.get("color", "#1f77b4")),
                        attrs={k: v for k, v in n.items() if k not in ["id", "label", "type", "color"]},
                    ))
            
            edges = []
            for e in data.get("edges", []):
                if isinstance(e, dict):
                    time_str = str(e.get("time", ""))
                    edge_time = None
                    if time_str:
                        try:
                            edge_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        except Exception:
                            pass
                    edges.append(SnapshotEdge(
                        from_node=str(e.get("from", "")),
                        to_node=str(e.get("to", "")),
                        type=str(e.get("type", "")),
                        title=str(e.get("title", "")),
                        time=edge_time,
                        attrs={k: v for k, v in e.items() if k not in ["from", "to", "type", "title", "time"]},
                    ))
            
            return Snapshot(meta=meta, nodes=nodes, edges=edges)
        except Exception as e:
            print(f"Failed to read snapshot from {input_path}: {e}")
            return None

    def list_snapshots(
        self,
        snapshot_dir: Path,
    ) -> Dict[GraphSnapshotType, Path]:
        if not snapshot_dir.exists():
            return {}
        
        result = {}
        for graph_type in GraphSnapshotType:
            path = snapshot_dir / f"{graph_type.value}.json"
            if path.exists():
                result[graph_type] = path
        return result


# =============================================================================
# Compat JSON Exporter（兼容导出）
# =============================================================================


class CompatJsonExporter:
    """
    兼容 JSON 导出器。
    用于导出 entities.json / abstract_to_event_map.json 等兼容格式。
    """

    def export_entities(
        self,
        entities: Dict[str, Any],
        output_path: Path,
    ) -> bool:
        """导出实体 JSON"""
        try:
            _ensure_dir(output_path.parent)
            output_path.write_text(
                json.dumps(entities, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            print(f"Failed to export entities: {e}")
            return False

    def export_events(
        self,
        events: Dict[str, Any],
        output_path: Path,
    ) -> bool:
        """导出事件 JSON"""
        try:
            _ensure_dir(output_path.parent)
            output_path.write_text(
                json.dumps(events, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            print(f"Failed to export events: {e}")
            return False

    def export_knowledge_graph(
        self,
        kg_data: Dict[str, Any],
        output_path: Path,
    ) -> bool:
        """导出知识图谱 JSON"""
        try:
            _ensure_dir(output_path.parent)
            output_path.write_text(
                json.dumps(kg_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            print(f"Failed to export knowledge graph: {e}")
            return False
