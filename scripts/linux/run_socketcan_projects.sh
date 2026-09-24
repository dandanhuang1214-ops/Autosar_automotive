#!/usr/bin/env bash
set -euo pipefail
channel="${1:-vcan0}"
output="${2:-output/socketcan-projects}"
python_bin="${3:-.venv/bin/python}"
if [[ -e "${output}" ]]; then
  echo "Output must be absent: ${output}" >&2
  exit 1
fi
lock_dir="${XDG_RUNTIME_DIR:-/tmp}/automotive-workbench"
lock_channel="${channel//[^a-zA-Z0-9_.-]/_}"
mkdir -p "${lock_dir}"
lock_file="${lock_dir}/socketcan-${lock_channel}.lock"
exec 9>"${lock_file}"
if ! flock -w 30 9; then
  echo "BLOCKED: channel lock unavailable" >&2
  exit 3
fi
export AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK="${lock_file}"
for sample in window_control thermal_control; do
  project="examples/${sample}/project.json"
  if [[ "${sample}" == "window_control" ]]; then
    project="examples/${sample}/project-declared.json"
  fi
  PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli run-project "${project}" \
    --interface socketcan --channel "${channel}" --output "${output}/${sample}"
  report="${output}/${sample}/bundle/project-report.json"
  PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli run-project-review \
    "${report}" --output "${output}/${sample}-review"
  PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli compare-projects \
    "${report}" "${report}" --output "${output}/${sample}-comparison"
  PYTHONPATH=src "${python_bin}" -m automotive_workbench.cli verify-project-comparison \
    "${output}/${sample}-comparison/project-comparison.json"
done
bash scripts/linux/probe_socketcan.sh > "${output}/socketcan-host-probe.json" \
  2> "${output}/socketcan-host-probe.config.txt"
