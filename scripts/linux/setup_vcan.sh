#!/usr/bin/env bash
set -euo pipefail

mode="${1:---dry-run}"
if [[ "${mode}" != "--dry-run" && "${mode}" != "--apply" ]]; then
  echo "usage: bash scripts/linux/setup_vcan.sh [--dry-run|--apply]" >&2
  exit 2
fi

echo "Planned idempotent operations:"
echo "  1. load can"
echo "  2. load can_raw"
echo "  3. load vcan"
echo "  4. create vcan0 only when absent"
echo "  5. set vcan0 UP"

if [[ "${mode}" == "--dry-run" ]]; then
  echo "DRY_RUN: no system changes were made"
  exit 0
fi

sudo modprobe can
sudo modprobe can_raw
sudo modprobe vcan
if ! ip link show vcan0 >/dev/null 2>&1; then
  sudo ip link add dev vcan0 type vcan
fi
sudo ip link set dev vcan0 up
echo "VCAN_READY"
ip -details -statistics link show vcan0
