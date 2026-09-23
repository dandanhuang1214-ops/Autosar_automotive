#!/usr/bin/env bash
set -euo pipefail
channel="vcan0"
output="output/socketcan-declared-communication"
python_bin=".venv-linux/bin/python"
dbc="examples/thermal_control/thermal_control.dbc"
intent="examples/thermal_control/bsw_intent.json"
declaration="examples/thermal_control/communication_vectors.json"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel) channel="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    --python) python_bin="$2"; shift 2 ;;
    --dbc) dbc="$2"; shift 2 ;;
    --intent) intent="$2"; shift 2 ;;
    --declaration) declaration="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
# Read-only validation precedes all runtime output, locking and backend access.
PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli plan-communication \
  "${dbc}" "${intent}" "${declaration}" > /dev/null
if ! command -v flock >/dev/null 2>&1; then
  echo "BLOCKED: flock required for per-channel isolation" >&2
  exit 3
fi
# Use the same lock namespace as the existing SocketCAN communication entrypoint.
lock_dir="${XDG_RUNTIME_DIR:-/tmp}/automotive-workbench"
lock_channel="${channel//[^a-zA-Z0-9_.-]/_}"
mkdir -p "${lock_dir}"
lock_file="${lock_dir}/socketcan-${lock_channel}.lock"
exec 9>"${lock_file}"
if ! flock -w 30 9; then
  echo "BLOCKED: channel lock timed out: ${lock_file}" >&2
  exit 3
fi
export AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK="${lock_file}"
set +e
PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli run-declared-communication \
  "${dbc}" "${intent}" "${declaration}" --interface socketcan \
  --channel "${channel}" --output "${output}"
runtime_rc=$?
set -e
if [[ "${runtime_rc}" -eq 0 || "${runtime_rc}" -eq 2 || "${runtime_rc}" -eq 3 ]]; then
  bash scripts/linux/probe_socketcan.sh > "${output}/socketcan-host-probe.json" \
    2> "${output}/socketcan-host-probe.config.txt"
fi
exit "${runtime_rc}"
