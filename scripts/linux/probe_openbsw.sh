#!/usr/bin/env bash
set -u

os_id="unknown"
os_version="unknown"
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  os_id="${ID:-unknown}"
  os_version="${VERSION_ID:-unknown}"
fi

present() {
  command -v "$1" >/dev/null 2>&1 && echo true || echo false
}

version_or_empty() {
  if command -v "$1" >/dev/null 2>&1; then
    "$@" 2>/dev/null | head -n 1
  fi
}

vcan0_present=false
ip link show vcan0 >/dev/null 2>&1 && vcan0_present=true
systemd_running=false
[[ "$(ps -p 1 -o comm= 2>/dev/null)" == "systemd" ]] && systemd_running=true
official_native_baseline=false
[[ "${os_id}" == "ubuntu" && "${os_version}" == "22.04" ]] && official_native_baseline=true
docker_cli_present="$(present docker)"
docker_daemon_available=false
if [[ "${docker_cli_present}" == "true" ]] && docker info >/dev/null 2>&1; then
  docker_daemon_available=true
fi

printf '{\n'
printf '  "artifact_type": "openbsw-readiness-probe",\n'
printf '  "os_id": "%s",\n' "${os_id}"
printf '  "os_version": "%s",\n' "${os_version}"
printf '  "kernel": "%s",\n' "$(uname -r)"
printf '  "official_native_baseline": %s,\n' "${official_native_baseline}"
printf '  "docker_cli_present": %s,\n' "${docker_cli_present}"
printf '  "docker_daemon_available": %s,\n' "${docker_daemon_available}"
printf '  "git_present": %s,\n' "$(present git)"
printf '  "gcc_present": %s,\n' "$(present gcc)"
printf '  "gxx_present": %s,\n' "$(present g++)"
printf '  "make_present": %s,\n' "$(present make)"
printf '  "cmake_present": %s,\n' "$(present cmake)"
printf '  "ninja_present": %s,\n' "$(present ninja)"
printf '  "python3_present": %s,\n' "$(present python3)"
printf '  "vcan0_present": %s,\n' "${vcan0_present}"
printf '  "systemd_running": %s,\n' "${systemd_running}"
printf '  "git_version": "%s",\n' "$(version_or_empty git --version)"
printf '  "gcc_version": "%s",\n' "$(version_or_empty gcc --version)"
printf '  "gxx_version": "%s",\n' "$(version_or_empty g++ --version)"
printf '  "cmake_version": "%s",\n' "$(version_or_empty cmake --version)"
printf '  "ninja_version": "%s",\n' "$(version_or_empty ninja --version)"
printf '  "python3_version": "%s"\n' "$(version_or_empty python3 --version)"
printf '}\n'
