#!/usr/bin/env bash
set -euo pipefail

channel="vcan0"
output="output/socketcan-uds-smoke"
python_bin=".venv-linux/bin/python"
intent="examples/window_control/uds_intent.json"

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
    --intent)
      intent="$2"
      shift 2
      ;;
    *)
      echo "usage: bash scripts/linux/run_socketcan_uds_lab.sh [--channel vcan0] [--output output/socketcan-uds-smoke] [--python .venv-linux/bin/python] [--intent examples/window_control/uds_intent.json]" >&2
      exit 2
      ;;
  esac
done

mkdir -p "${output}"

bash scripts/linux/probe_socketcan.sh \
  > "${output}/socketcan-host-probe.json" \
  2> "${output}/socketcan-host-probe.config.txt"

if [[ ! -x "${python_bin}" ]]; then
  echo "BLOCKED: Python diagnostic environment is missing: ${python_bin}" >&2
  echo "Create it with: python3 -m venv .venv-linux && .venv-linux/bin/python -m pip install -e '.[diag]'" >&2
  exit 3
fi

set +e
PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli run-uds-lab "${intent}" \
  --interface socketcan \
  --channel "${channel}" \
  --output "${output}/workbench-uds-lab" \
  > "${output}/workbench-uds-lab.stdout.json"
rc=$?
set -e

if [[ "${rc}" -eq 0 ]]; then
  echo "SOCKETCAN_UDS_LAB_PASSED"
  echo "Output: ${output}"
  exit 0
fi

if [[ "${rc}" -eq 3 ]]; then
  echo "SOCKETCAN_UDS_LAB_BLOCKED"
  echo "Output: ${output}"
  exit 3
fi

echo "SOCKETCAN_UDS_LAB_FAILED"
echo "Output: ${output}"
exit "${rc}"
