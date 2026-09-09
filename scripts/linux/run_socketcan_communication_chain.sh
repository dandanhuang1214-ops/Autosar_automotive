#!/usr/bin/env bash
set -euo pipefail

channel="vcan0"
output="output/socketcan-communication-chain"
python_bin=".venv-linux/bin/python"
dbc="examples/window_control/window_control.dbc"
intent="examples/window_control/bsw_intent.json"

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
    --intent)
      intent="$2"
      shift 2
      ;;
    *)
      echo "usage: bash scripts/linux/run_socketcan_communication_chain.sh [--channel vcan0] [--output output/socketcan-communication-chain] [--python .venv-linux/bin/python] [--dbc examples/window_control/window_control.dbc] [--intent examples/window_control/bsw_intent.json]" >&2
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

if [[ ! -x "${python_bin}" ]]; then
  echo "BLOCKED: Python CAN environment is missing: ${python_bin}" >&2
  echo "Create it with: python3 -m venv .venv-linux && .venv-linux/bin/python -m pip install -e '.[can]'" >&2
  exit 3
fi

set +e
PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli run-communication-delivery \
  "${dbc}" "${intent}" \
  --interface socketcan \
  --channel "${channel}" \
  --base . \
  --output "${output}/workbench-communication-delivery" \
  > "${output}/workbench-communication-delivery.stdout.json"
chain_rc=$?
set -e

if [[ "${chain_rc}" -eq 0 || "${chain_rc}" -eq 3 ]]; then
  PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli export-evidence-capsule \
    "${output}/workbench-communication-delivery" \
    --base . \
    --output "${output}/workbench-evidence-capsule" \
    > "${output}/workbench-evidence-capsule.stdout.json"
fi

if [[ "${chain_rc}" -eq 0 ]]; then
  echo "SOCKETCAN_COMMUNICATION_CHAIN_PASSED"
  echo "Output: ${output}"
  exit 0
fi
if [[ "${chain_rc}" -eq 3 ]]; then
  echo "SOCKETCAN_COMMUNICATION_CHAIN_BLOCKED"
  echo "Output: ${output}"
  exit 3
fi
echo "SOCKETCAN_COMMUNICATION_CHAIN_FAILED"
echo "Output: ${output}"
exit "${chain_rc}"
