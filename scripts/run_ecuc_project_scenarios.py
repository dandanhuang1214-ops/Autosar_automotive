"""Public synthetic ECUC scenarios; no vendor or customer input is loaded."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(output: Path) -> dict[str, Any]:
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Scenario output must be empty or absent")
    output = output.resolve()
    work = output / "original"
    rows = []
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}

    def cli(name: str, args: list[str], code: int) -> dict[str, Any]:
        p = subprocess.run([sys.executable, "-m", "automotive_workbench.cli", *args],
                           cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
        log = {"case": name, "argv": args, "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
        output.mkdir(parents=True, exist_ok=True)
        (output / (name + ".json")).write_text(json.dumps(log, indent=2), encoding="utf-8")
        if p.returncode != code:
            raise RuntimeError(f"{name}: expected {code}, got {p.returncode}: {p.stdout} {p.stderr}")
        return json.loads(p.stdout)

    cases = {
        "normal": (None, None),
        "unbound": ("/Demo/Os/Task10ms", ""),
        "missing-target": ("/Demo/Os/Task10ms", "/Demo/Os/Absent"),
        "ambiguous": ("</CONTAINERS>", '<ECUC-CONTAINER-VALUE><SHORT-NAME>Task10ms</SHORT-NAME><DEFINITION-REF>/Synthetic/OsTask</DEFINITION-REF></ECUC-CONTAINER-VALUE></CONTAINERS>'),
    }
    codes = {"unbound": "ECUC-TASK-UNBOUND", "missing-target": "ECUC-MISSING-REFERENCE", "ambiguous": "ECUC-AMBIGUOUS-PATH"}
    for name, (before, after) in cases.items():
        source = work / "inputs" / name
        shutil.copytree(ROOT / "tests/fixtures/ecuc-project", source)
        if before is not None and after is not None:
            p = source / "modules.arxml"
            p.write_text(p.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
        result = cli(name, ["inspect-ecuc-project", str(source / "demo.dpa"), "--output", str(work / "reports" / name)], 0 if name == "normal" else 2)
        if name in codes and codes[name] not in {f["code"] for f in result["findings"]}:
            raise RuntimeError("Expected structural finding absent")
        if name == "normal" and (result["findings"] or result["references"]["unassessed"] != 1):
            raise RuntimeError("External references or unselected modules misclassified")
        rows.append({"case": name, "status": result["status"], "findings": sorted({f["code"] for f in result["findings"]})})
    moved = output / "portable"
    work.rename(moved)
    # Remove input originals, forcing verifiers to use only the portable snapshots.
    shutil.rmtree(moved / "inputs")
    for name in cases:
        result = cli("replay-" + name, ["verify-ecuc-inspection", str(moved / "reports" / name / "ecuc-inspection.json")], 0)
        if result["status"] != "passed":
            raise RuntimeError("Migrated snapshot replay failed")
    forged = moved / "forged"
    shutil.copytree(moved / "reports/normal", forged)
    path = forged / "ecuc-inspection.json"
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["references"]["resolved"] = 0
    path.write_text(json.dumps(changed), encoding="utf-8")
    rejection = cli("tamper-rejection", ["verify-ecuc-inspection", str(path)], 1)
    if rejection["status"] != "error":
        raise RuntimeError("Tampered conclusions accepted")
    result = {"status": "passed", "cases": rows, "migration": "4/4 passed with original inputs absent", "tamper_rejection": "passed"}
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
