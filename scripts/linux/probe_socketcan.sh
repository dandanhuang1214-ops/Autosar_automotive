#!/usr/bin/env bash
set -u

kernel="$(uname -r)"
config_source=""
config_lines=""
if [[ -r /proc/config.gz ]]; then
  config_source="/proc/config.gz"
  config_lines="$(zcat /proc/config.gz | grep -E 'CONFIG_CAN(=|_)|CONFIG_VCAN' || true)"
elif [[ -r "/boot/config-${kernel}" ]]; then
  config_source="/boot/config-${kernel}"
  config_lines="$(grep -E 'CONFIG_CAN(=|_)|CONFIG_VCAN' "/boot/config-${kernel}" || true)"
fi

module_dir="/lib/modules/${kernel}"
module_dir_present=false
vcan_module_present=false
if [[ -d "${module_dir}" ]]; then
  module_dir_present=true
  if find "${module_dir}" -type f -name 'vcan.ko*' -print -quit 2>/dev/null | grep -q .; then
    vcan_module_present=true
  fi
fi

vcan0_present=false
ip link show vcan0 >/dev/null 2>&1 && vcan0_present=true
python3_present=false
command -v python3 >/dev/null 2>&1 && python3_present=true
can_utils_present=false
if command -v candump >/dev/null 2>&1 && command -v cansend >/dev/null 2>&1; then
  can_utils_present=true
fi
systemd_running=false
[[ "$(ps -p 1 -o comm= 2>/dev/null)" == "systemd" ]] && systemd_running=true

printf '{\n'
printf '  "artifact_type": "socketcan-host-probe",\n'
printf '  "kernel": "%s",\n' "${kernel}"
printf '  "config_source": "%s",\n' "${config_source}"
printf '  "can_config_present": %s,\n' "$([[ -n "${config_lines}" ]] && echo true || echo false)"
printf '  "module_dir_present": %s,\n' "${module_dir_present}"
printf '  "vcan_module_present": %s,\n' "${vcan_module_present}"
printf '  "vcan0_present": %s,\n' "${vcan0_present}"
printf '  "python3_present": %s,\n' "${python3_present}"
printf '  "can_utils_present": %s,\n' "${can_utils_present}"
printf '  "systemd_running": %s\n' "${systemd_running}"
printf '}\n'

if [[ -n "${config_lines}" ]]; then
  printf '\n# Matching kernel configuration\n' >&2
  printf '%s\n' "${config_lines}" >&2
fi
