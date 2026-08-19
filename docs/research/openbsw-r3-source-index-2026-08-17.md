# OpenBSW R3 Source Index

Date: 2026-08-17  
Scope: POSIX referenceApp, SocketCAN, CAN demo, DoCAN, and unit test entry points

## Baseline

OpenBSW local clone:

- Path: `/home/dev/work/openbsw`
- Remote: `https://github.com/eclipse-openbsw/openbsw.git`
- Commit: `dbd6e118a9aaa2db36e4461ce76655e8f285598d`
- Built preset: `posix-freertos`

This index is for adapter research only. It does not treat OpenBSW as a full AUTOSAR Classic BSW replacement.

## POSIX Application Entry

Primary POSIX entry:

- `/home/dev/work/openbsw/executables/referenceApp/platforms/posix/main/src/main.cpp`
- `platformLifecycleAdd()` adds POSIX-specific systems at lifecycle level 2.
- CAN is added with `canSystem.create(TASK_CAN)`.
- `main()` sets up signal handling, initializes platform BSP, then calls `app_main()`.

Generic application entry:

- `/home/dev/work/openbsw/executables/referenceApp/application/src/app/app.cpp`
- `LifecycleManager` is declared with 16 components and 9 levels.
- Generic typed systems include `RuntimeSystem`, `SysAdminSystem`, `DemoSystem`, and `SafetySystem`.
- When CAN and transport are enabled, `DoCanSystem` is included and stored as a typed system.

Useful line anchors from commit `dbd6e118`:

```text
platforms/posix/main/src/main.cpp:47 platformLifecycleAdd()
platforms/posix/main/src/main.cpp:53 lifecycleManager.addComponent("can", ...)
platforms/posix/main/src/main.cpp:88 main()
platforms/posix/main/src/main.cpp:94 app_main()
application/src/app/app.cpp:123 MaxNumComponents/MaxNumLevels
application/src/app/app.cpp:136 lifecycleManager
application/src/app/app.cpp:153 transportSystem
application/src/app/app.cpp:156 doCanSystem
```

## POSIX CAN Path

POSIX CAN system:

- `/home/dev/work/openbsw/executables/referenceApp/platforms/posix/main/src/systems/CanSystem.cpp`
- Static device config is `{"vcan0", CAN_0}`.
- `run()` initializes and opens the `SocketCanTransceiver`, then schedules cyclic execution every 1 ms.
- `execute()` calls `_canTransceiver.run(MAX_SENT_PER_RUN, MAX_RECEIVED_PER_RUN)`.

SocketCAN adapter:

- `/home/dev/work/openbsw/platforms/posix/bsp/socketCanTransceiver/src/can/SocketCanTransceiver.cpp`
- `guardedOpen()` creates a raw CAN socket, resolves the interface index with `SIOCGIFINDEX`, enables CAN FD frames, makes the socket non-blocking, then binds to the CAN interface.
- `writeImpl()` queues a `CANFrame`; `guardedRun()` later sends/receives queued frames.

CAN frame model:

- `/home/dev/work/openbsw/libs/bsw/cpp2can/include/can/canframes/CANFrame.h`
- Default classic CAN max payload is 8 bytes unless `CPP2CAN_USE_64_BYTE_FRAMES` is defined.
- Base CAN max ID is `0x7FF`; extended max ID is `0x1FFFFFFF`.
- `CANFrame(uint32_t id, uint8_t const payload[], uint8_t length)` is the constructor used by the demo path.

Useful line anchors:

```text
platforms/posix/main/src/systems/CanSystem.cpp:22 canConfig{"vcan0", CAN_0}
platforms/posix/main/src/systems/CanSystem.cpp:34 CanSystem::run()
platforms/posix/main/src/systems/CanSystem.cpp:60 CanSystem::execute()
platforms/posix/bsp/socketCanTransceiver/src/can/SocketCanTransceiver.cpp:123 writeImpl()
platforms/posix/bsp/socketCanTransceiver/src/can/SocketCanTransceiver.cpp:173 guardedOpen()
cpp2can/include/can/canframes/CANFrame.h:47 MAX_FRAME_LENGTH
cpp2can/include/can/canframes/CANFrame.h:54 MAX_FRAME_ID
cpp2can/include/can/canframes/CANFrame.h:82 CANFrame(id,payload,length)
```

## Demo CAN Behavior

Demo system:

- `/home/dev/work/openbsw/executables/referenceApp/application/src/systems/DemoSystem.cpp`
- Constructor obtains `CAN_0` through `canSystem.getCanTransceiver()`.
- `run()` starts the `CanDemoListener`.
- `cyclic()` sends one CAN frame per second with ID `0x558` and a 4-byte big-endian counter payload.

Demo listener:

- `/home/dev/work/openbsw/executables/referenceApp/application/src/app/CanDemoListener.cpp`
- `run()` registers as both receive listener and sent-frame listener.
- Filters include `0x123` and `0x124`.
- On receive, it logs the received frame and queues a response with ID `frame.getId() + 1`.
- On send, it logs the sent frame ID and length.

Useful line anchors:

```text
application/src/systems/DemoSystem.cpp:71 _canSystem
application/src/systems/DemoSystem.cpp:72 _canDemoListener(canSystem.getCanTransceiver(CAN_0))
application/src/systems/DemoSystem.cpp:113 DemoSystem::run()
application/src/systems/DemoSystem.cpp:178 CAN cyclic block
application/src/systems/DemoSystem.cpp:192 CANFrame frame(0x558,...,4)
application/src/app/CanDemoListener.cpp:27 frameReceived()
application/src/app/CanDemoListener.cpp:37 response frame id + 1
application/src/app/CanDemoListener.cpp:43 canFrameSent()
application/src/app/CanDemoListener.cpp:54 filters 0x123 and 0x124
```

## DoCAN Path

Reference app DoCAN system:

- `/home/dev/work/openbsw/executables/referenceApp/application/src/systems/DoCanSystem.cpp`
- Static address mapping uses receive ID `0x02A`, transmit ID `0x0F0`, and `LOGICAL_ADDRESS`.
- `initLayer()` gets `CAN_0`, creates a `DoCanPhysicalCanTransceiver`, then creates a `DoCanTransportLayer`.
- `run()` registers transport layers with the transport system and schedules cyclic execution every 10 ms.
- `execute()` calls `_transportLayers.cyclicTask(systemUs())`.

DoCAN integration test example:

- `/home/dev/work/openbsw/libs/bsw/docan/test/src/docan/integration/DemoTest.cpp`
- `TEST(DemoTest, DoCanIntegration)` demonstrates normal addressing, parameters, addressing filter, physical CAN transceiver, transport layer config, init/cyclic/shutdown, and send-data setup.

Useful line anchors:

```text
application/src/systems/DoCanSystem.cpp:43 _addresses
application/src/systems/DoCanSystem.cpp:80 initLayer()
application/src/systems/DoCanSystem.cpp:82 getCanTransceiver(CAN_0)
application/src/systems/DoCanSystem.cpp:84 DoCanPhysicalCanTransceiver
application/src/systems/DoCanSystem.cpp:91 transportLayers.emplace_back()
application/src/systems/DoCanSystem.cpp:113 run()
application/src/systems/DoCanSystem.cpp:142 execute()
libs/bsw/docan/test/src/docan/integration/DemoTest.cpp:46 DoCanIntegration
libs/bsw/docan/test/src/docan/integration/DemoTest.cpp:87 CAN reception IDs must be ascending
libs/bsw/docan/test/src/docan/integration/DemoTest.cpp:127 DoCanPhysicalCanTransceiver
libs/bsw/docan/test/src/docan/integration/DemoTest.cpp:148 DoCanTransportLayer
```

## Unit Test Entry

Documented root:

- `/home/dev/work/openbsw/doc/dev/index.rst`
- Lines 64-68 identify `executables/unitTest` as the unit test entry point.

CMake presets:

- `tests-posix-debug`
- `tests-posix-release`

Relevant CAN/DoCAN tests:

```text
libs/bsw/cpp2can/test/CMakeLists.txt
libs/bsw/cpp2can/test/src/can/canframes/CANFrameTest.cpp
libs/bsw/cpp2can/test/src/can/transceiver/AbstractCANTransceiverTest.cpp
libs/bsw/docan/test/CMakeLists.txt
libs/bsw/docan/test/src/docan/integration/DemoTest.cpp
libs/bsw/docan/test/src/docan/datalink/DoCanFrameCodecTest.cpp
```

## Test Build and Execution Evidence

`tests-posix-debug` was verified after this source index was created.

Commands:

```bash
cmake --preset tests-posix-debug
cmake --build --preset tests-posix-debug --parallel
ctest --preset tests-posix-debug --output-on-failure
```

Results:

- Configure passed and generated `/home/dev/work/openbsw/build/tests/posix/Debug`.
- Build passed: 223/223 build steps completed.
- CTest passed: 1878/1878 tests passed, 0 failed, total real time 33.79 seconds.

Relevant label summary:

```text
cpp2canTest              33 tests
docanTest               168 tests
socketCanTransceiverTest  5 tests
udsTest                 286 tests
```

## Workbench Adapter Implications

The current Workbench SocketCAN baseline sends and validates deterministic DBC-defined public window-control frames. OpenBSW's referenceApp CAN path is useful as a runtime/source-reading target, but its demo frame IDs and payload semantics are unrelated to the Workbench public DBC.

Near-term adapter should therefore stay read-only/index-based:

1. Link Workbench CAN evidence to OpenBSW source locations for SocketCAN open/send/receive.
2. Compare Workbench `BusConfig(interface=socketcan, channel=vcan0)` with OpenBSW's fixed `canConfig{"vcan0", CAN_0}`.
3. Treat OpenBSW demo `0x558` and DoCAN `0x02A/0x0F0` as separate reference traffic, not as the public window-control contract.

## Minimal Test Candidate

`tests-posix-debug` builds and executes locally, so the follow-up candidate was kept narrower than a full adapter or runtime change.

Selected target:

- File: `/home/dev/work/openbsw/libs/bsw/cpp2can/test/src/can/canframes/CANFrameTest.cpp`
- Test: `CANFrameTest.ClassicCanFrameInvariants`
- Purpose: verify the classic CAN assumptions Workbench relies on while reading OpenBSW as a runtime reference.

Role:

This test is a narrow guardrail, not a runtime feature or adapter integration. It locks down the
CAN frame model assumptions that Workbench depends on before any OpenBSW adapter work is attempted.
If OpenBSW later changes classic CAN payload sizing, base/extended ID limits, or ID encoding
semantics, this test should fail early and force the adapter assumptions to be reviewed explicitly.

```text
Assertions:
  CANFrame::MAX_FRAME_LENGTH == 8
  CANFrame::MAX_FRAME_ID == CanId::MAX_RAW_BASE_ID
  CANFrame::MAX_FRAME_ID_EXTENDED == CanId::MAX_RAW_EXTENDED_ID
  max base ID constructor stays a base ID and preserves raw ID/payload length
  max extended ID constructor stays extended and preserves raw ID/payload length
```

Validation after adding the test:

```bash
cmake --build --preset tests-posix-debug --target cpp2canTest --parallel
ctest --preset tests-posix-debug -R CANFrameTest --output-on-failure
ctest --preset tests-posix-debug -L cpp2canTest --output-on-failure
ctest --preset tests-posix-debug --output-on-failure
```

Results:

```text
CANFrameTest: 7/7 passed
cpp2canTest label: 34/34 passed
full tests-posix-debug CTest: 1879/1879 passed, 0 failed, total real time 34.81 seconds
```
