from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    source_artifact: str
    kind: str = "unknown"
    field: str = ""
    location: str = ""
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceNode:
    layer: str
    kind: str
    identity: str
    source_status: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class TraceResult:
    query: str
    model_status: str
    nodes: tuple[TraceNode, ...]
    unknowns: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "model_status": self.model_status,
            "nodes": [node.to_dict() for node in self.nodes],
            "unknowns": list(self.unknowns),
        }

