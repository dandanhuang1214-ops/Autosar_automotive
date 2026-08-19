# OpenBSW R3 Readiness Report

Date: 2026-08-17  
Status: readiness complete; clone/build not started

## Scope

R3 is a time-boxed OpenBSW POSIX spike. It must not replace the Workbench Python virtual ECU, vendor BSW generators, or commercial AUTOSAR tools. The spike only verifies whether OpenBSW is useful as an open-source POSIX runtime and source-reading target for future adapters.

## Current Probe Evidence

Saved evidence:

- `output/openbsw-readiness/readiness.json`

Summary:

```text
os_id=ubuntu
os_version=24.04
kernel=6.18.33.2-microsoft-standard-WSL2
official_native_baseline=false
docker_cli_present=false
docker_daemon_available=false
git_present=true
gcc_present=true
gxx_present=true
make_present=true
cmake_present=true
ninja_present=true
python3_present=true
vcan0_present=true
systemd_running=true
git_version=2.43.0
gcc_version=13.3.0
gxx_version=13.3.0
cmake_version=3.28.3
ninja_version=1.11.1
python3_version=3.12.3
```

## Official Context

The OpenBSW repository recommends using its development Docker service and building POSIX with:

```bash
cmake --preset posix
cmake --build --preset posix
```

Official POSIX documentation says the POSIX platform can run without automotive hardware and can use SocketCAN when the host supports it. The documentation also points users to Ubuntu 22.04 or Windows setup instructions, while this host is Ubuntu 24.04.

Primary sources:

- <https://github.com/eclipse-openbsw/openbsw>
- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/platforms/posix/index.html>
- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/index.html>

## Route Decision

Preferred official route is blocked locally:

- Docker CLI is absent in WSL.
- Docker daemon is unavailable.
- Installing or enabling Docker is outside this spike unless explicitly approved.

Practical local route is feasible but not official-native-baseline:

- Ubuntu 24.04 has Git, GCC, G++, Make, CMake, Ninja and Python.
- SocketCAN `vcan0` already works.
- A native build may succeed, but a failure must be classified as Ubuntu 24.04/native compatibility or dependency issue, not as OpenBSW unsuitability.

Recommended R3 first attempt:

1. Use Ubuntu 24.04 native CMake only if explicitly approved.
2. Clone OpenBSW outside `/mnt/d`, preferably under WSL Linux filesystem such as `~/work/openbsw`.
3. Record remote URL, commit SHA, `LICENSE` and `NOTICE.md`.
4. Run only official POSIX configure/build commands.
5. Stop after the first reproducible build result or classified failure.

## Budget And Exit Conditions

Proposed budget:

- Time: 60-90 minutes for first clone/configure/build attempt.
- Disk: reserve 8-12 GB under WSL Linux filesystem.
- Network: one clone plus build dependency downloads required by the project.

Exit immediately if:

- Clone or dependency download repeatedly fails due to network access.
- Configure/build cannot progress after two focused fixes.
- Build requires host changes beyond ordinary user-space tooling.
- Docker becomes required but is not approved.
- The spike starts expanding into a full BSW integration project.

## First Spike Deliverables

- Clone commit SHA and license evidence.
- POSIX configure/build result.
- Short index of:
  - POSIX main entry
  - reference app entry
  - `CanSystem` / CAN-related runtime path
  - unit test entry
- One small candidate change or test target, only after the baseline build result is known.
