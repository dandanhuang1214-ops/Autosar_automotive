# SocketCAN on WSL2

## Boundary

Workbench never installs WSL, changes the kernel, edits `/etc/wsl.conf` or `.wslconfig`, loads modules, or creates network interfaces from Python. Host preparation remains an explicit operator action.

## Current verified host facts

The development host uses Ubuntu 24.04.1 on WSL2 with Microsoft kernel `6.18.33.2-microsoft-standard-WSL2`. CAN, CAN_RAW, CAN_BCM, CAN_ISOTP and CAN_VCAN are configured as modules and matching `.ko` files exist. A custom kernel is not required.

## Probe without changes

From the repository root inside WSL:

```bash
bash scripts/linux/probe_socketcan.sh
bash scripts/linux/setup_vcan.sh --dry-run
```

## Apply and verify

Only after reviewing the dry run:

```bash
bash scripts/linux/setup_vcan.sh --apply
```

Optional can-utils verification:

```bash
candump vcan0
cansend vcan0 100#2A01020000000000
```

Workbench verification requires a Linux virtual environment; a Windows `.venv` cannot run inside WSL:

```bash
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -e '.[diag]'
PYTHONPATH=src .venv-linux/bin/python -m automotive_workbench.cli probe-can-backend --interface socketcan --channel vcan0 --output output/socketcan-probe
PYTHONPATH=src .venv-linux/bin/python -m automotive_workbench.cli run-backend-lab examples/window_control/window_control.dbc --interface socketcan --channel vcan0 --output output/socketcan-lab
PYTHONPATH=src .venv-linux/bin/python -m automotive_workbench.cli probe-uds-backend --interface socketcan --channel vcan0 --output output/socketcan-uds-probe
PYTHONPATH=src .venv-linux/bin/python -m automotive_workbench.cli run-uds-lab examples/window_control/uds_intent.json --interface socketcan --channel vcan0 --output output/socketcan-uds-lab
```

Do not create `.venv-linux` until `python3-venv` availability and package installation are explicitly approved.

## Repeatable lab entry

After `vcan0` is present and `.venv-linux` is installed, run the non-sudo lab entry:

```bash
bash scripts/linux/run_socketcan_lab.sh --output output/socketcan-smoke
```

This command does not prepare the host. It records:

- `socketcan-host-probe.json`
- `can-utils-smoke.log`
- `workbench-probe/backend-probe.json`
- `workbench-lab/backend-lab-report.json`
- capture, decode and replay reports under `workbench-lab/`

For the UDS/ISO-TP diagnostic path, run:

```bash
bash scripts/linux/run_socketcan_uds_lab.sh --output output/socketcan-uds-smoke
```

This command also does not prepare the host. It records:

- `socketcan-host-probe.json`
- `workbench-uds-probe/uds-backend-probe.json`
- `workbench-uds-lab/probe/backend-probe.json`
- `workbench-uds-lab/uds-lab-report.json`
- `workbench-uds-lab/uds-lab-report.md`

If `vcan0` is missing, the UDS probe returns `SOCKETCAN_UDS_PROBE_BLOCKED` and keeps the blocked report under `workbench-uds-probe/`.

If WSL is shut down, `vcan0` may disappear. Restore it explicitly:

```bash
bash scripts/linux/setup_vcan.sh --dry-run
bash scripts/linux/setup_vcan.sh --apply
bash scripts/linux/run_socketcan_lab.sh --output output/socketcan-smoke
bash scripts/linux/run_socketcan_uds_lab.sh --output output/socketcan-uds-smoke
```

## Rollback

```bash
bash scripts/linux/remove_vcan.sh
```

The rollback intentionally leaves kernel modules loaded, because blindly unloading shared modules can disrupt other CAN processes. WSL shutdown also clears the runtime interface.
