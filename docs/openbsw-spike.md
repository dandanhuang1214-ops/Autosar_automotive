# OpenBSW POSIX Spike Boundary

The spike starts only after SocketCAN/vcan and the Workbench backend lab pass on Linux.

The official repository currently recommends its development Docker image and builds POSIX with:

```bash
cmake --preset posix
cmake --build --preset posix
```

Before cloning or installing dependencies, run:

```bash
bash scripts/linux/probe_openbsw.sh
```

Ubuntu 24.04 is not treated as equivalent to the documentation's Ubuntu 22.04 native baseline without a real build. Missing Docker, CMake or Ninja is reported as readiness evidence, not silently installed.

The spike must remain time-boxed and preserve the boundary that OpenBSW is an automotive embedded SDK, not a free complete AUTOSAR Classic vendor stack.
