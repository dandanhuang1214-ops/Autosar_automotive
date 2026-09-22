"""Run the public P18 project baseline/candidate comparison scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from automotive_workbench.project_comparison import (  # noqa: E402
    compare_project_reports,
)
from run_project_review_scenarios import run_scenarios  # noqa: E402


COMPARISONS = (
    ("stable", "baseline", "baseline", "stable"),
    ("scale-regression", "baseline", "scale-change", "regressed"),
    ("generation-regression", "baseline", "missing-init", "regressed"),
    ("generation-improvement", "missing-init", "baseline", "improved"),
)


def run_comparison_scenarios(output: Path) -> dict:
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("P18 scenario output must be empty or absent")
    output = output.resolve()
    if not output.exists():
        output.mkdir(parents=True)

    review_scenarios = run_scenarios(output / "project-runs")
    comparisons = []
    for name, baseline, candidate, expected_status in COMPARISONS:
        project_root = output / "project-runs/projects"
        result = compare_project_reports(
            project_root / baseline / "bundle/project-report.json",
            project_root / candidate / "bundle/project-report.json",
            output / "comparisons" / name,
        )
        if (
            result["status"] != expected_status
            or result["evidence_validation"]["status"] != "passed"
        ):
            raise RuntimeError(
                f"{name}: expected {expected_status}/passed, got "
                f"{result['status']}/{result['evidence_validation']['status']}"
            )
        comparisons.append({
            "comparison": name,
            "baseline": baseline,
            "candidate": candidate,
            "status": result["status"],
            "evidence_validation": result["evidence_validation"]["status"],
            "summary": result["summary"],
        })

    summary = {
        "artifact_type": "project-comparison-scenario-result",
        "schema_version": "project-comparison-scenario-result-0.1",
        "status": "passed",
        "project_review_status": review_scenarios["status"],
        "comparisons": comparisons,
        "boundary": (
            "Regression describes declared report outcomes and finding deltas; it does "
            "not independently prove root cause or physical ECU behavior."
        ),
    }
    (output / "p18-project-comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    descriptions = {
        "stable": "同一基线：稳定不代表覆盖全部需求",
        "scale-regression": "分辨率变化：canonical 失败，通信跳过",
        "generation-regression": "缺少初值：generation 失败，通信跳过",
        "generation-improvement": "恢复初值：从失败报告回到通过基线",
    }
    cards = "\n".join(
        f'<li><a href="comparisons/{escape(item["comparison"])}/index.html">'
        f'{escape(descriptions[item["comparison"]])}</a> — {escape(item["status"])}</li>'
        for item in comparisons
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>公开车窗项目回归演示</title>'
        '<style>body{font:18px/1.7 system-ui,sans-serif;max-width:900px;margin:auto;padding:24px}'
        'li{margin:18px 0}a{color:#0757a0}</style><main>'
        '<h1>公开车窗项目回归演示</h1>'
        '<p>公开合成 DOCX → 固定 Generate-Arxml 导出 → 静态校验 → virtual CAN → 项目比较。</p>'
        f'<ol>{cards}</ol>'
        '<p>阅读顺序：比较结论 → 失败阶段 → finding → 展开两侧证据。'
        '每份比较保留来源文件、SHA-256 和 JSON Pointer。</p>'
        '<p>本次重放消费已保存的导出，不重新运行 Generate-Arxml；'
        '结果不代表客户数据、物理 ECU 或量产验证。</p>'
        '<p>迁移时保留整个场景目录；各比较页提供独立复验命令。</p>'
        '</main></html>\n',
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_comparison_scenarios(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
