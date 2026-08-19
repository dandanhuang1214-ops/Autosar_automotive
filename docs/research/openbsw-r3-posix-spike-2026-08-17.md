# OpenBSW R3 POSIX Spike Report

Date: 2026-08-17  
Status: POSIX native spike passed; official Docker route deferred

## Scope

This spike only verifies whether Eclipse OpenBSW can be built and started as a POSIX reference runtime for future Workbench adapter research. It does not replace the existing Python virtual ECU, Workbench SocketCAN experiments, vendor BSW generators, or commercial AUTOSAR tooling.

## Clone Evidence

- Local path: `/home/dev/work/openbsw`
- Remote: `https://github.com/eclipse-openbsw/openbsw.git`
- Commit: `dbd6e118a9aaa2db36e4461ce76655e8f285598d`
- License evidence: root `LICENSE` is Apache License 2.0; root `NOTICE.md` declares `SPDX-License-Identifier: Apache-2.0` and lists third-party licenses.

## Readiness Update

New readiness evidence:

- `output/openbsw-readiness/readiness-2026-08-17-docker.json`

Summary:

```text
os_id=ubuntu
os_version=24.04
kernel=6.18.33.2-microsoft-standard-WSL2
official_native_baseline=false
docker_cli_present=true
docker_daemon_available=true
git/gcc/g++/make/cmake/ninja/python3=true
vcan0_present=false at probe time
systemd_running=true
```

`vcan0` was later restored with `bash scripts/linux/setup_vcan.sh --apply` and reported `VCAN_READY`.

## Docker Route Result

The official development service was attempted with:

```bash
DOCKER_UID=$(id -u) DOCKER_GID=$(id -g) docker compose run --build --rm development cmake --preset posix-freertos
```

Result: deferred, not a source/build failure.

Reason: the official `docker/development/Dockerfile` has no skip flag for cross-toolchain dependencies. It downloads ARM GCC, ARM LLVM, treefmt, bazelisk, buildifier, Rust, Python requirements, and other development tools before the POSIX CMake command can run. The build was interrupted at the ARM GCC download stage after about 11% of a 143 MB download, with wget estimating more than 15 minutes remaining for that file alone. This was classified as `docker-image-dependency-download-too-heavy-for-first-spike`.

## Native POSIX Build Result

Native configure command:

```bash
cmake --preset posix-freertos
```

Result: passed.

Key configure evidence:

```text
Target platform: <POSIX>
Target RTOS: <FREERTOS>
PLATFORM_SUPPORT_CAN ON
PLATFORM_SUPPORT_ETHERNET ON
PLATFORM_SUPPORT_MIDDLEWARE ON
PLATFORM_SUPPORT_STORAGE ON
PLATFORM_SUPPORT_TRANSPORT ON
PLATFORM_SUPPORT_UDS ON
GCC/G++ 13.3.0
Doxygen missing only affects documentation generation
Build files: /home/dev/work/openbsw/build/posix-freertos
```

Native build command:

```bash
cmake --build --preset posix-freertos --parallel
```

Result: passed, 379 build steps.

Built artifacts:

```text
/home/dev/work/openbsw/build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf
/home/dev/work/openbsw/build/posix-freertos/platforms/posix/bsp/socketCanTransceiver/Release/libsocketCanTransceiver.a
/home/dev/work/openbsw/build/posix-freertos/libs/bsw/cpp2can/Release/libcpp2can.a
/home/dev/work/openbsw/build/posix-freertos/libs/bsw/docan/Release/libdocan.a
```

## Runtime Smoke

First 5 second run before restoring `vcan0`:

- referenceApp started and initialized lifecycle levels.
- CAN startup reached SocketCAN but logged `Failed to ioctl socket (node=vcan0, error=-1)`.
- Classification: host `vcan0` missing, not build failure.

After `setup_vcan.sh --apply`, a second 5 second run showed:

```text
hello
Initialize can
Run can
DoIp Initialized
Add diag job successfully 0x22
DEMO: DEBUG: Sending frame 0
CAN: DEBUG: [CanDemoListener] CAN frame sent, id=0x558, length=4
```

The command was intentionally wrapped in `timeout 5s`, so exit code `124` is expected for a long-running reference app.

Ethernet/TAP still logged `TapEthernetDriver start failed!`; this is outside the CAN/POSIX spike scope and does not block the CAN build/run evidence.

## Source Entry Index

- POSIX main entry: `executables/referenceApp/platforms/posix/main/src/main.cpp`, `main()` at line 88, `app_main()` handoff at line 94.
- Platform lifecycle registration: same file, `platformLifecycleAdd()` at lines 47-59 adds CAN and Ethernet at lifecycle level 2.
- POSIX CAN system: `executables/referenceApp/platforms/posix/main/src/systems/CanSystem.cpp`, `canConfig{"vcan0", CAN_0}` at line 22, `run()` opens the transceiver at lines 34-40.
- SocketCAN adapter: `platforms/posix/bsp/socketCanTransceiver/src/can/SocketCanTransceiver.cpp`, socket/ioctl/bind path at lines 173-232.
- Demo CAN listener: `executables/referenceApp/application/src/app/CanDemoListener.cpp`, receive echo path at lines 27-40, sent-frame logging at lines 43-50, filters `0x123` and `0x124` at lines 52-61.
- DoCAN unit/integration test example: `libs/bsw/docan/test/src/docan/integration/DemoTest.cpp`, `TEST(DemoTest, DoCanIntegration)` starts at line 46 and shows addressing/filter/transport setup through line 184.
- Unit test root: `executables/unitTest`, documented in `doc/dev/index.rst` lines 64-68.

## Next Step

Use the successful native POSIX baseline to do one narrow adapter research task:

1. Keep Workbench's Python SocketCAN lab as the deterministic baseline.
2. Add an OpenBSW source index note for `CanSystem`, `SocketCanTransceiver`, `CanDemoListener`, and DoCAN transport.
3. Only after that, decide whether to build `tests-posix-debug` or create a small OpenBSW-side candidate test.
