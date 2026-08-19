from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.adapters.openbsw_patch import prepare_openbsw_patch


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


class OpenBswPatchTests(unittest.TestCase):
    def test_prepare_openbsw_patch_writes_manifest_and_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "openbsw"
            repo.mkdir()
            _git(repo, "init")
            _git(repo, "config", "user.name", "Workbench Test")
            _git(repo, "config", "user.email", "workbench@example.invalid")
            _git(repo, "remote", "add", "origin", "https://github.com/eclipse-openbsw/openbsw.git")
            source = repo / "CANFrameTest.cpp"
            source.write_text("baseline\n", encoding="utf-8")
            _git(repo, "add", "CANFrameTest.cpp")
            _git(repo, "commit", "-m", "baseline")
            source.write_text("baseline\nclassic can invariant\n", encoding="utf-8")

            output = root / "evidence"
            result = prepare_openbsw_patch(repo, output)
            patch = (output / "openbsw-local-changes.patch").read_text(encoding="utf-8")
            manifest = json.loads((output / "openbsw-patch-manifest.json").read_text(encoding="utf-8"))
            markdown = (output / "openbsw-patch-manifest.md").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["remote_url"], "https://github.com/eclipse-openbsw/openbsw.git")
        self.assertEqual(result["tracked_dirty_files"], ["CANFrameTest.cpp"])
        self.assertEqual(result["untracked_files"], [])
        self.assertIn("+classic can invariant", patch)
        self.assertEqual(manifest["patch_sha256"], hashlib.sha256(patch.encode("utf-8")).hexdigest())
        self.assertIn("does not submit or claim acceptance", markdown)


if __name__ == "__main__":
    unittest.main()
