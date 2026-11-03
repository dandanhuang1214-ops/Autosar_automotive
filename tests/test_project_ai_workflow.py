from __future__ import annotations

import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from automotive_workbench.knowledge_chat import ask, new_session
from automotive_workbench.project_ai_workflow import propose, validate

PROJECT = Path(__file__).resolve().parents[1] / "examples/ecuc_acceptance/transmitter.project.json"


class FakeModel:
    records: list[dict] = []

    def __init__(self, selected_id: str):
        self.selected_id = selected_id

    def identity(self, name: str) -> dict:
        return {"name": name, "digest": "a" * 64}

    def service_version(self) -> str:
        return "test-service"

    def complete(self, payload: dict) -> dict:
        self.records = [{"path": "/api/chat", "status": "completed"}]
        return {"model": payload["model"], "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": self.selected_id},
                "prompt_eval_count": 70, "eval_count": 25}


class ProjectAiWorkflowTests(unittest.TestCase):
    def test_model_selected_project_is_generated_and_really_validated(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            proposal = propose(root, PROJECT, "Verify the COM communication chain", "fake-model",
                               "http://unused", FakeModel("COMMUNICATION"))
            self.assertEqual(proposal["status"], "draft_unassessed")
            self.assertEqual(proposal["selection"]["acceptance_ids"], ["COMMUNICATION"])
            self.assertTrue(Path(proposal["generated_project"]["path"]).is_file())
            result = validate(root, proposal["id"])
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["verification_status"], "passed")
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual([row["id"] for row in report["requirements"]], ["COMMUNICATION"])
            db = root / "chat.sqlite3"
            answer = ask(root, db, session_id=new_session(db), question="通信验收状态是什么？",
                         report=Path(result["report"]), model="unused", ollama_url="http://unused",
                         use_model=False)
            self.assertEqual(answer["evidence"]["graph_status"], "not_imported")
            self.assertEqual(answer["evidence"]["project_status"], "passed")
            with self.assertRaisesRegex(ValueError, "already been executed"):
                validate(root, proposal["id"])

    def test_unknown_model_check_is_rejected_before_generation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "unknown check"):
                propose(root, PROJECT, "Verify the COM chain", "fake-model", "http://unused",
                        FakeModel("INVENTED"))
            tasks = list((root / "project-tasks").iterdir())
            self.assertEqual(len(tasks), 1)
            self.assertEqual(json.loads((tasks[0] / "model-trace.json").read_text())["status"], "rejected")
            self.assertFalse((tasks[0] / "generated-project.json").exists())

    def test_generated_declaration_and_input_drift_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            proposal = propose(root, PROJECT, "Verify the COM chain", "fake-model", "http://unused",
                               FakeModel("COMMUNICATION"))
            generated = Path(proposal["generated_project"]["path"])
            generated.write_text(generated.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Generated project differs"):
                validate(root, proposal["id"])

            copied = root / "copied-project"
            shutil.copytree(PROJECT.parent, copied)
            copied_project = copied / PROJECT.name
            second = propose(root, copied_project, "Verify the COM chain", "fake-model", "http://unused",
                             FakeModel("COMMUNICATION"))
            module = copied / "transmitter/modules.arxml"
            module.write_bytes(module.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                validate(root, second["id"])

            third = propose(root, PROJECT, "Verify the COM chain", "fake-model", "http://unused",
                            FakeModel("COMMUNICATION"))
            trace = root / "project-tasks" / third["id"] / "model-trace.json"
            changed = json.loads(trace.read_text(encoding="utf-8"))
            changed["response"]["message"]["content"] = "IMPACT"
            trace.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "saved model response"):
                validate(root, third["id"])

    def test_proposal_requires_absolute_static_project_and_valid_requirement(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            model = FakeModel("COMMUNICATION")
            with self.assertRaisesRegex(ValueError, "Requirement"):
                propose(root, PROJECT, "", "fake-model", "http://unused", model)
            with self.assertRaisesRegex(ValueError, "absolute project"):
                propose(root, Path("relative.json"), "Verify COM", "fake-model", "http://unused", model)
