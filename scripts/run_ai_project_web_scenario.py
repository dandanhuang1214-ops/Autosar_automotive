"""Exercise the local AI project form API with one public static ECUC requirement."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8767")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--requirement", default="请生成 COMMUNICATION 验收项目，验证静态 COM 通信结构")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    opener = build_opener(ProxyHandler({}))
    with opener.open(args.url + "/", timeout=10) as response:
        html = response.read().decode("utf-8")
    token_match = re.search(r"const token = '([^']+)'", html)
    if not token_match or 'id="projectRequirement"' not in html or 'id="validateProject"' not in html:
        raise ValueError("AI project form or local token is missing")
    token = token_match.group(1)

    def post(route: str, body: dict, key: str = token) -> dict:
        request = Request(args.url + route, json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          {"Content-Type": "application/json", "X-Workbench-Token": key})
        with opener.open(request, timeout=120) as response:
            return json.load(response)

    with_error = False
    try:
        post("/api/project/validate", {"task_id": "0" * 32}, "wrong")
    except HTTPError as exc:
        with_error = exc.code == 403
    if not with_error:
        raise ValueError("Project API accepted an invalid local token")
    proposal = post("/api/project/propose", {
        "project": str(args.project.resolve()),
        "requirement": args.requirement,
    })
    if proposal["status"] != "draft_unassessed" or proposal["selection"]["acceptance_ids"] != ["COMMUNICATION"]:
        raise ValueError("AI did not select the expected public check")
    validation = post("/api/project/validate", {"task_id": proposal["id"]})
    if (validation["status"] != "passed" or validation["integrity_status"] != "passed"
            or validation["verification_status"] != "passed"):
        raise ValueError("Generated project validation did not pass")
    session = post("/api/session", {})["session_id"]
    answer = post("/api/chat", {"session_id": session, "question": "通信验收状态是什么？",
                                "report": validation["report"], "use_model": False})
    if (answer["evidence"]["project_status"] != "passed"
            or answer["evidence"]["graph_status"] != "not_imported"):
        raise ValueError("Generated project report did not reach graph-free chat")
    summary = {"contract_version": "ai-project-web-scenario-0.1", "status": "passed",
               "token_gate": "rejected", "model": proposal["model"],
               "selected_acceptance_ids": proposal["selection"]["acceptance_ids"],
               "generated_project": proposal["generated_project"],
               "validation": validation, "chat_status": answer["status"],
               "scope": "Public static ECUC project; model choice is a reviewable draft, not semantic quality acceptance"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "task_id": proposal["id"],
                      "selected_acceptance_ids": summary["selected_acceptance_ids"],
                      "validation_status": validation["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
