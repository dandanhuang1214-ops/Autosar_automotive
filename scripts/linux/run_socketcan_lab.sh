#!/usr/bin/env bash
set -euo pipefail

channel="vcan0"
output="output/socketcan-smoke"
python_bin=".venv-linux/bin/python"
dbc="examples/window_control/window_control.dbc"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      channel="$2"
      shift 2
      ;;
    --output)
      output="$2"
      shift 2
      ;;
    --python)
      python_bin="$2"
      shift 2
      ;;
    --dbc)
      dbc="$2"
      shift 2
      ;;
    *)
      echo "usage: bash scripts/linux/run_socketcan_lab.sh [--channel vcan0] [--output output/socketcan-smoke] [--python .venv-linux/bin/python] [--dbc examples/window_control/window_control.dbc]" >&2
      exit 2
      ;;
  esac
done

if ! command -v flock >/dev/null 2>&1; then
  echo "BLOCKED: flock is required for per-channel experiment isolation" >&2
  exit 3
fi

lock_dir="${XDG_RUNTIME_DIR:-/tmp}/automotive-workbench"
lock_channel="${channel//[^a-zA-Z0-9_.-]/_}"
mkdir -p "${lock_dir}"
lock_file="${lock_dir}/socketcan-${lock_channel}.lock"
exec 9>"${lock_file}"
if ! flock -w 30 9; then
  echo "BLOCKED: timed out waiting for SocketCAN channel lock: ${lock_file}" >&2
  exit 3
fi
export AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK="${lock_file}"

mkdir -p "${output}"

bash scripts/linux/probe_socketcan.sh \
  > "${output}/socketcan-host-probe.json" \
  2> "${output}/socketcan-host-probe.config.txt"

if ! grep -q '"vcan0_present": true' "${output}/socketcan-host-probe.json"; then
  echo "BLOCKED: ${channel} is not present. Run: bash scripts/linux/setup_vcan.sh --dry-run, then bash scripts/linux/setup_vcan.sh --apply" >&2
  exit 3
fi

if [[ "${channel}" != "vcan0" ]] && ! ip link show "${channel}" >/dev/null 2>&1; then
  echo "BLOCKED: ${channel} is not present" >&2
  exit 3
fi

if ! command -v candump >/dev/null 2>&1 || ! command -v cansend >/dev/null 2>&1; then
  echo "BLOCKED: candump and cansend are required" >&2
  exit 3
fi

if [[ ! -x "${python_bin}" ]]; then
  echo "BLOCKED: Python environment is missing: ${python_bin}" >&2
  echo "Create it with: python3 -m venv .venv-linux && .venv-linux/bin/python -m pip install -e '.[can]'" >&2
  exit 3
fi

raw_log="${output}/can-utils-smoke.log"
rm -f "${raw_log}"
timeout 3s candump -n 1 "${channel}" > "${raw_log}" &
dump_pid=$!
sleep 0.1
cansend "${channel}" 123#2A00010000000000
wait "${dump_pid}"

if ! grep -q '123.*2A 00 01 00 00 00 00 00' "${raw_log}"; then
  echo "FAILED: can-utils smoke frame was not observed in ${raw_log}" >&2
  exit 1
fi

PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli probe-can-backend \
  --interface socketcan \
  --channel "${channel}" \
  --output "${output}/workbench-probe" \
  > "${output}/workbench-probe.stdout.json"

PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli run-backend-lab "${dbc}" \
  --interface socketcan \
  --channel "${channel}" \
  --output "${output}/workbench-lab" \
  > "${output}/workbench-lab.stdout.json"

echo "SOCKETCAN_LAB_PASSED"
echo "Output: ${output}"
