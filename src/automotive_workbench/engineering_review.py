"""Bounded engineering questions over replay-verified P21--P23 evidence.

These are exact structured queries, not free-text retrieval or model reasoning.
Domain validators retain ownership of engineering conclusions.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from automotive_workbench.arxml_bridge import verify_report
from automotive_workbench.communication_graph import _json, verify_graph_report
from automotive_workbench.external_ecu import verify_external_ecu
from automotive_workbench.project_declared import validate_declared_sources
from automotive_workbench.project_review import load_project_report
from automotive_workbench.review import _resolve_json_pointer


# id, category, input version, question, exact evidence selectors, refusal reason.
# No caller-supplied prompt can change selectors, policy or engineering results.
QUESTIONS = (
    ("impact-acceptance", "impact", "communication-impact-0.1", "配置变化后需要重跑哪些验收项和测试向量？", ("/reason", "/requirements", "/vectors"), ""),
    ("impact-paths", "impact", "communication-impact-0.1", "变化通过哪些依赖路径影响其他通信对象？", ("/reason", "/affected"), ""),
    ("impact-objects", "impact", "communication-impact-0.1", "哪些通信对象发生了什么语义变化？", ("/reason", "/changes"), ""),
    ("impact-comparability", "impact", "communication-impact-0.1", "这两份配置是否可比较，依据是什么？", ("/status", "/reason"), ""),
    ("impact-unknowns", "impact", "communication-impact-0.1", "影响分析有哪些无法确定的范围？", ("/unknowns",), ""),
    ("graph-references", "graph", "communication-graph-0.1", "通信对象有哪些断引用及其源位置？", ("/findings",), ""),
    ("graph-identities", "graph", "communication-graph-0.1", "哪些通信对象身份重复或冲突？", ("/findings",), ""),
    ("graph-directions", "graph", "communication-graph-0.1", "本地 ECU 的通信方向哪里不一致？", ("/findings",), ""),
    ("graph-layout", "graph", "communication-graph-0.1", "信号长度或布局有哪些冲突？", ("/findings",), ""),
    ("graph-routes", "graph", "communication-graph-0.1", "哪些路由端点与所属 PDU 不一致？", ("/findings",), ""),
    ("arxml-version", "arxml", "arxml-import-0.1", "此 XML 按哪个 AUTOSAR 版本和命名空间解析？", ("/autosar_version", "/namespace", "/coverage"), ""),
    ("arxml-unsupported", "arxml", "arxml-import-0.1", "哪些 XML 元素或属性超出了支持范围？", ("/coverage", "/unsupported"), ""),
    ("arxml-references", "arxml", "arxml-import-0.1", "XML 引用检查发现了哪些错误及原位置？", ("/status", "/findings"), ""),
    ("arxml-timing", "arxml", "arxml-comparison-0.1", "两版 ARXML 中的时序对象具体发生了什么变化？", ("/status", "/changes"), ""),
    ("arxml-ecuc", "arxml", "arxml-import-0.1", "能否从此 SWC XML 确定量产 COM/PduR/CanIf ECUC 映射？", ("/boundaries",), "SWC XML does not establish vendor ECUC mappings."),
    ("project-gates", "project", "project-acceptance-0.5", "静态失败时通信和独立 ECU 阶段实际是否执行？", ("/status", "/stages"), ""),
    ("project-requirements", "project", "project-acceptance-0.5", "哪些验收项未满足，预期值、实际值和原因是什么？", ("/requirements",), ""),
    ("project-runtime", "project", "project-acceptance-0.5", "通信阶段和独立 ECU 阶段分别记录了什么状态？", ("/stages/communication", "/stages/external_ecu"), ""),
    ("project-basis", "project", "project-acceptance-0.5", "此项目保存了哪些配置和运行条件作为比较依据？", ("/comparison_basis",), ""),
    ("project-dbc-ecu", "project", "project-acceptance-0.5", "项目通信通过能否证明 OpenBSW 内部使用了该 DBC？", ("/stages",), "Separate communication and ECU stages do not prove an internal DBC mapping."),
    ("ecu-diagnostic", "external", "external-ecu-run-0.1", "独立 ECU 诊断实际记录了什么响应或阻断原因？", ("/status", "/reason", "/diagnostic"), ""),
    ("ecu-build", "external", "external-ecu-run-0.1", "外部执行记录绑定了哪个源码提交和通道？", ("/source_commit", "/channel", "/evidence_kind"), ""),
    ("ecu-lifecycle", "external", "external-ecu-run-0.1", "是否启动了独立进程，退出和清理情况如何？", ("/launch_ecu", "/ecu_pid", "/client_pid", "/cleanup"), ""),
    ("ecu-lock", "external", "external-ecu-run-0.1", "外部执行是否获得通道锁，未执行原因是什么？", ("/lock", "/status", "/reason"), ""),
    ("ecu-root-cause", "external", "external-ecu-run-0.1", "能否仅凭超时或阻断报告断定 ECU 软件存在缺陷？", ("/status", "/reason", "/diagnostic"), "Timeout or blocked evidence does not establish a unique ECU software root cause."),
    ("source-drift", "provenance", "communication-impact-0.1", "哪些源文件字节和源位置发生变化？", ("/source_changes", "/locator_changes"), ""),
    ("source-producer", "provenance", "arxml-import-0.1", "XML 记录了哪个生产者版本及输入产物哈希？", ("/source/name", "/source/sha256", "/source/producer"), ""),
    ("source-project", "provenance", "project-acceptance-0.5", "项目快照记录了哪些源文件和哈希用于迁移复验？", ("/source_artifacts",), ""),
    ("source-identity", "provenance", "external-ecu-run-0.1", "保存文件的哈希复验能否认证目标 ECU 身份？", ("/target_identity_verified", "/evidence_kind"), "Saved-byte integrity does not authenticate ECU identity."),
    ("source-physical", "provenance", "external-ecu-run-0.1", "这些 POSIX/vcan 证据能否证明物理 ECU 或量产验收通过？", ("/evidence_kind", "/channel", "/target_identity_verified"), "POSIX/vcan evidence does not establish physical ECU or production acceptance."),
)
FILTERS = {
    "graph-references": "GRAPH-MISSING-REFERENCE",
    "graph-identities": "GRAPH-DUPLICATE-IDENTITY",
    "graph-directions": "GRAPH-DIRECTION",
    "graph-layout": "GRAPH-LENGTH-LAYOUT",
    "graph-routes": "GRAPH-ROUTE-ENDPOINT",
}
BOUNDARY = (
    "Recorded evidence only; no new execution, ECU authentication, commercial tool "
    "acceptance, full AUTOSAR conformance, or unique root-cause inference. "
    "Empty findings mean no matching recorded finding, not absence of all defects."
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def catalog() -> dict[str, Any]:
    return {
        "questions": [
            dict(id=q[0], category=q[1], input_version=q[2], question=q[3], pointers=list(q[4]), refusal=q[5])
            for q in QUESTIONS
        ],
        "finding_filters": FILTERS,
    }


def _validate_source(path: Path, report: dict[str, Any]) -> None:
    version = report.get("schema_version")
    if version in ("communication-graph-0.1", "communication-impact-0.1"):
        result = verify_graph_report(path)
        if result["status"] != "passed":
            raise ValueError("Graph source replay failed: " + result["reason"])
    elif version in ("arxml-import-0.1", "arxml-comparison-0.1"):
        verify_report(report)
    elif version == "external-ecu-run-0.1":
        verify_external_ecu(path)
    elif version == "project-acceptance-0.5":
        load_project_report(path)
        validate_declared_sources(path, report)
    else:
        raise ValueError("Unsupported engineering source version")


def answer(source: Path, question_id: str, destination: Path) -> dict[str, Any]:
    """Read/replay source, then select exact structured facts without writing."""
    question = next((q for q in QUESTIONS if q[0] == question_id), None)
    if question is None:
        raise ValueError("Unknown engineering question; use list-engineering-questions")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Engineering source must be a regular non-symlink file")
    raw = source.read_bytes()
    report = _json(raw)
    if report.get("schema_version") != question[2]:
        raise ValueError("Question requires " + question[2])
    _validate_source(source, report)
    if source.read_bytes() != raw:
        raise ValueError("Engineering source changed during validation")
    facts = []
    for pointer in question[4]:
        try:
            value = _resolve_json_pointer(report, pointer)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("Required engineering evidence is missing: " + pointer) from exc
        facts.append(dict(pointer=pointer, value=value, value_sha256=digest(canonical(value).encode())))
    # Keep original collections in citations; filtered answers are reproducible views.
    selected = None
    if question_id in FILTERS:
        selected = [f for f in report["findings"] if f["code"] == FILTERS[question_id]]
    if question_id == "project-requirements":
        selected = [r for r in report["requirements"] if r["status"] != "passed"]
    if question_id == "arxml-timing":
        selected = [c for c in report["changes"] if any(
            isinstance(c.get(side), dict) and c[side]["kind"] == "TIMING-EVENT"
            for side in ("before", "after")
        )]
    relative = Path(os.path.relpath(source.resolve(), destination.resolve())).as_posix()
    return {
        "schema_version": "engineering-review-0.1",
        "status": "refused" if question[5] else "answered",
        "question_id": question_id,
        "question": question[3],
        "category": question[1],
        "catalog_sha256": digest(canonical(catalog()).encode()),
        "source": {"path": relative, "sha256": digest(raw), "schema_version": question[2]},
        "facts": facts,
        "selected": selected,
        "refusal_reason": question[5] or None,
        "boundary": BOUNDARY,
        "method": {"retrieval": "fixed-json-pointer", "validation": "domain-source-replay", "model": "not-run"},
    }


def run_engineering_review(source: Path, question_id: str, output: Path) -> dict[str, Any]:
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Engineering review output must be absent or empty")
    # Source directories may have complete inventories: do not put new files inside them.
    if output.resolve().is_relative_to(source.resolve().parent):
        raise ValueError("Engineering review output must be outside the source directory")
    result = answer(source, question_id, output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "engineering-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Engineering evidence review", "", result["question"], "", "Status: " + result["status"], ""]
    if result["refusal_reason"]:
        lines += [result["refusal_reason"], ""]
    if result["selected"] is not None:
        lines += ["Selected answer:", "", "```json", json.dumps(result["selected"], ensure_ascii=False, indent=2), "```", ""]
    for fact in result["facts"]:
        lines += [f"Source: `{result['source']['path']}#{fact['pointer']}`", "", "```json", json.dumps(fact["value"], ensure_ascii=False, indent=2), "```", ""]
    lines += [BOUNDARY, ""]
    (output / "engineering-review.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def verify_engineering_review(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("Engineering review must not be a symlink")
    result = _json(path.read_bytes())
    try:
        relative = result["source"]["path"]
        if not isinstance(relative, str) or Path(relative).is_absolute() or "\\" in relative:
            raise ValueError("Engineering source must use a relative POSIX path")
        source = path.parent / relative
        expected = answer(source, result["question_id"], path.parent)
        if canonical(result) != canonical(expected):
            raise ValueError("Engineering review differs from verified source and question policy")
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed engineering review") from exc
    return {"status": "passed", "question_id": result["question_id"], "citations": len(result["facts"]), "scope": "source-integrity-and-domain-replay; no ECU execution"}
