from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automotive_workbench.knowledge_graph_workspace import active_snapshot
from automotive_workbench.site_graph_sync import sync_site_graph
from tests.test_knowledge_graph_chat import fixture


class SiteGraphSyncTest(unittest.TestCase):
    def test_verified_files_activate_and_repeat_is_idempotent(self) -> None:
        raw, sources = fixture()
        received = []

        def fetch(name, token, _limit):
            received.append((name, token))
            return raw if name == "graph.json" else sources[name]

        with tempfile.TemporaryDirectory() as directory, \
                patch("automotive_workbench.site_graph_sync._fetch", side_effect=fetch):
            root = Path(directory)
            first = sync_site_graph(root, "private-token")
            second = sync_site_graph(root, "private-token")
            self.assertEqual(first["graph_sha256"], second["graph_sha256"])
            self.assertEqual(active_snapshot(root)[1]["graph_sha256"], first["graph_sha256"])
            self.assertEqual([name for name, _ in received],
                             ["graph.json", "source-doc1.md"] * 2)
            self.assertTrue(all(token == "private-token" for _, token in received))

    def test_invalid_source_does_not_switch_active_graph(self) -> None:
        raw, sources = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("automotive_workbench.site_graph_sync._fetch",
                       side_effect=lambda name, _token, _limit:
                       raw if name == "graph.json" else sources[name]):
                first = sync_site_graph(root, "private-token")
            updated = json.loads(raw)
            updated["nodes"][0]["summary"] = "Changed"
            new_raw = json.dumps(updated).encode()
            with patch("automotive_workbench.site_graph_sync._fetch",
                       side_effect=lambda name, _token, _limit:
                       new_raw if name == "graph.json" else b"tampered"):
                with self.assertRaisesRegex(ValueError, "changed source document"):
                    sync_site_graph(root, "private-token")
            self.assertEqual(active_snapshot(root)[1]["graph_sha256"], first["graph_sha256"])

    def test_untrusted_filename_is_rejected_before_fetch(self) -> None:
        raw, _ = fixture()
        graph = json.loads(raw)
        graph["sourceDocuments"][0]["filename"] = "../private.md"
        with tempfile.TemporaryDirectory() as directory, \
                patch("automotive_workbench.site_graph_sync._fetch",
                      return_value=json.dumps(graph).encode()) as fetch:
            with self.assertRaisesRegex(ValueError, "source file name"):
                sync_site_graph(Path(directory), "private-token")
            fetch.assert_called_once()

    def test_update_outage_and_recovery_preserve_verified_snapshot(self) -> None:
        raw, sources = fixture()
        updated = json.loads(raw)
        updated["nodes"][0]["summary"] = "A revised candidate after recovery"
        new_raw = json.dumps(updated, ensure_ascii=False).encode()
        served = {"graph.json": raw, **sources}

        def fetch(name, _token, _limit):
            value = served[name]
            if isinstance(value, OSError):
                raise value
            return value

        with tempfile.TemporaryDirectory() as directory, \
                patch("automotive_workbench.site_graph_sync._fetch", side_effect=fetch):
            root = Path(directory)
            first = sync_site_graph(root, "private-token")
            served["graph.json"] = OSError("site unavailable")
            with self.assertRaisesRegex(OSError, "site unavailable"):
                sync_site_graph(root, "private-token")
            self.assertEqual(active_snapshot(root)[1]["graph_sha256"], first["graph_sha256"])
            served["graph.json"] = new_raw
            second = sync_site_graph(root, "private-token")
            self.assertNotEqual(second["graph_sha256"], first["graph_sha256"])
            self.assertEqual(second["previous_graph_sha256"], first["graph_sha256"])
            self.assertEqual(second["diff"]["nodes"]["changed"], ["K001"])
            self.assertEqual(active_snapshot(root)[0]["nodes"][0]["summary"],
                             "A revised candidate after recovery")


if __name__ == "__main__":
    unittest.main()
