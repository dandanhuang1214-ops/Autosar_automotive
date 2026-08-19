#!/usr/bin/env bash
set -euo pipefail

if ip link show vcan0 >/dev/null 2>&1; then
  sudo ip link delete vcan0
  echo "VCAN0_REMOVED"
else
  echo "VCAN0_ALREADY_ABSENT"
fi
echo "Kernel modules were left loaded because other processes may use them."
