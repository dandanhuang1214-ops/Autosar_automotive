from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automotive_workbench.domain import TraceNode, TraceResult


TRACE_FIELDS = (
    ("network", "dbc_signal"),
    ("contract", "canonical_signal"),
    ("asw", "swc_data_element"),
    ("asw", "swc_port"),
    ("bsw", "com_signal"),
    ("bsw", "i_pdu"),
    ("bsw", "pdur_route"),
    ("bsw", "canif_pdu"),
)


def load_intent(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != "bsw-intent-0.1":
        raise ValueError("Unsupported or missing bsw-intent schema_version")
    if not isinstance(payload.get("signals"), list):
        raise ValueError("BSW intent requires a signals list")
    return payload


def trace_signal(path: Path, query: str) -> TraceResult:
    payload = load_intent(path)
    query_folded = query.casefold()
    signal = next(
        (
            item for item in payload["signals"]
            if isinstance(item, dict)
            and query_folded in {
                str(item.get("dbc_signal") or "").casefold(),
                str(item.get("canonical_signal") or "").casefold(),
                str(item.get("com_signal") or "").casefold(),
            }
        ),
        None,
    )
    if signal is None:
        raise KeyError(f"Signal not found: {query}")

    nodes = []
    for layer, field in TRACE_FIELDS:
        identity = str(signal.get(field) or "")
        if identity:
            nodes.append(TraceNode(
                layer=layer,
                kind=field,
                identity=identity,
                source_status=str(signal.get(f"{field}_status") or "designed"),
            ))
    return TraceResult(
        query=query,
        model_status=str(payload.get("model_status") or "unknown"),
        nodes=tuple(nodes),
        unknowns=tuple(str(value) for value in signal.get("unknowns", [])),
    )

