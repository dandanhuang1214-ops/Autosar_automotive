from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LinuxScriptContractTests(unittest.TestCase):
    def test_probe_is_read_only(self) -> None:
        script = (ROOT / "scripts" / "linux" / "probe_socketcan.sh").read_text(encoding="utf-8")
        for mutation in ("sudo ", "modprobe ", "ip link add", "ip link set", "apt "):
            self.assertNotIn(mutation, script)

    def test_setup_defaults_to_dry_run_before_sudo_operations(self) -> None:
        script = (ROOT / "scripts" / "linux" / "setup_vcan.sh").read_text(encoding="utf-8")
        dry_run_exit = script.index('echo "DRY_RUN: no system changes were made"')
        first_sudo = script.index("sudo modprobe can")
        self.assertLess(dry_run_exit, first_sudo)
        self.assertIn('mode="${1:---dry-run}"', script)
        self.assertIn('if ! ip link show vcan0', script)

    def test_remove_script_does_not_unload_shared_modules(self) -> None:
        script = (ROOT / "scripts" / "linux" / "remove_vcan.sh").read_text(encoding="utf-8")
        self.assertIn("ip link delete vcan0", script)
        self.assertNotIn("modprobe -r", script)

    def test_socketcan_lab_entrypoint_does_not_prepare_host(self) -> None:
        script = (ROOT / "scripts" / "linux" / "run_socketcan_lab.sh").read_text(encoding="utf-8")
        for mutation in ("sudo ", "modprobe ", "ip link add", "ip link set", "apt "):
            self.assertNotIn(mutation, script)
        self.assertIn("probe_socketcan.sh", script)
        self.assertIn("setup_vcan.sh --dry-run", script)
        self.assertIn("run-backend-lab", script)
        self.assertIn("candump -n 1", script)
        self.assertIn("cansend", script)
        self.assertIn("flock -w 30", script)
        self.assertIn("AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK", script)

    def test_socketcan_uds_lab_entrypoint_does_not_prepare_host(self) -> None:
        script = (ROOT / "scripts" / "linux" / "run_socketcan_uds_lab.sh").read_text(encoding="utf-8")
        for mutation in ("sudo ", "modprobe ", "ip link add", "ip link set", "apt "):
            self.assertNotIn(mutation, script)
        self.assertIn("probe_socketcan.sh", script)
        self.assertIn("pip install -e '.[diag]'", script)
        self.assertIn("run-uds-lab", script)
        self.assertIn("--interface socketcan", script)
        self.assertIn("SOCKETCAN_UDS_LAB_BLOCKED", script)
        self.assertIn("flock -w 30", script)
        self.assertIn("AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK", script)

    def test_socketcan_communication_entrypoint_is_locked_and_non_mutating(self) -> None:
        script = (ROOT / "scripts" / "linux" / "run_socketcan_communication_chain.sh").read_text(
            encoding="utf-8"
        )
        for mutation in ("sudo ", "modprobe ", "ip link add", "ip link set", "apt "):
            self.assertNotIn(mutation, script)
        self.assertIn("probe_socketcan.sh", script)
        self.assertIn("run-communication-chain", script)
        self.assertIn("--interface socketcan", script)
        self.assertIn("index-evidence", script)
        self.assertIn("verify-evidence", script)
        self.assertIn("flock -w 30", script)
        self.assertIn("AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK", script)

    def test_openbsw_probe_is_read_only_and_does_not_claim_ubuntu_24_support(self) -> None:
        script = (ROOT / "scripts" / "linux" / "probe_openbsw.sh").read_text(encoding="utf-8")
        for mutation in ("sudo ", "apt ", "git clone", "docker compose", "cmake --build"):
            self.assertNotIn(mutation, script)
        self.assertIn('"${os_version}" == "22.04"', script)
        self.assertIn('"vcan0_present"', script)
        self.assertIn('"docker_daemon_available"', script)
        self.assertIn('"cmake_version"', script)


if __name__ == "__main__":
    unittest.main()
