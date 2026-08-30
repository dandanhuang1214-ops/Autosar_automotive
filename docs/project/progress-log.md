# Automotive Workbench 平台升级进度账本

> 本文是平台进度的唯一主记录。平台代码、技术文档、调研和运行环境记录均统一保存在 `D:\ＬＬＭ\automotive-workbench`。

## 固定更新制度

每次平台升级必须同时完成以下事项，才可标记为“完成”：

1. 记录日期、升级编号、目标和边界；
2. 记录实际代码或文档变更；
3. 写明运行过的测试、实验和结果，不把“已编码”等同于“已验证”；
4. 区分 `完成`、`部分完成`、`等待环境验证` 和 `未开始`；
5. 写明限制、回退方式和下一步；
6. 路线改变时同步更新 `roadmap.md`；
7. 产生新学习内容时同步更新相应 `learning/` 文档。

编号约定：`P` 表示平台功能，`R` 表示运行时实验底座，`E` 表示环境与基础设施，`L` 表示学习材料。

## 当前总览（2026-08-31）

当前阶段：`R4p — 冗余修复与中断写入边界调研已完成`。

总体结论：静态分析、故障套件、虚拟 CAN、日志回放和 backend 抽象已经形成；WSL2 已确认具备 CAN/VCAN 内核能力，`vcan0` 可通过脚本恢复并通过 can-utils 原始帧收发与 Workbench SocketCAN backend lab。Linux 探测、环境准备、实验和报告已固化为可重复入口；Windows 原生回归已由用户复验通过。R3 已完成首次 OpenBSW POSIX spike：Docker daemon 当前可用，但官方 development 镜像下载 ARM/Rust/Bazel 等完整工具链，首轮被分类为镜像依赖下载过重；Ubuntu 24.04 原生 `posix-freertos` configure/build 通过，referenceApp 在 `vcan0` 上完成 CAN 发送 smoke。

| 能力 | 状态 | 当前证据 |
|---|---|---|
| Artifact/Finding/Trace/TestResult | 完成 | schema、CLI、单元测试 |
| Generate-Arxml 报告适配 | 完成 | `issues.json` → Finding |
| DBC → BSW intent 静态映射 | 完成 | 公开车窗样例与映射校验 |
| DBC → canonical contract 校验 | 完成 | 名称、缩放、偏移、单位、范围检查 |
| 故障注入与证据报告 | 完成 | 基线及多类配置故障 |
| python-can virtual 实验 | 完成 | 收发、超时、恢复、监督状态 |
| can-utils 日志解析与回放 | 完成 | capture/decode/replay 与 hash |
| backend-neutral 实验接口 | 完成 | virtual/SocketCAN 共用契约 |
| WSL2 Linux 执行环境 | 完成 | Ubuntu 24.04、CAN/VCAN 模块、can-utils、CMake、Ninja 已确认 |
| `vcan0` 真实收发 | 完成 | `candump` 收到 `123#2A00010000000000` |
| Workbench SocketCAN 实验 | 完成 | backend probe/lab 通过，含错误 ID 与接收超时 |
| 可重复 Linux lab 入口 | 完成 | `scripts/linux/run_socketcan_lab.sh` 通过并归档报告 |
| Windows 原生回归 | 完成 | 用户在 PowerShell 复验通过 |
| OpenBSW POSIX spike | 部分完成 | Docker 路线因 development 镜像下载过重暂缓；Ubuntu 24.04 原生 `posix-freertos` build、referenceApp CAN smoke、源码入口索引、`tests-posix-debug` 全量 CTest 通过；最小 CANFrame 测试候选已整理为 patch artifact |
| ISO-TP/UDS 诊断链 | 部分完成 | R4a-R4i 已完成架构、virtual/SocketCAN 和 isolation 证据；R4j-R4o 已完成 DTC 生命周期到冗余恢复证据；R4p 已完成 repair 与中断写入边界调研 |
| AI 工程审查 | 未开始 | 确定性通信与诊断闭环后进入 |

## 已完成升级历史

### P0：平台边界与统一证据模型

- 确立 Windows 工程面、Workbench Core、Linux 执行面三层边界。
- 建立 Artifact、Finding、Trace、TestResult、Evidence 基础对象。
- 平台连接 Generate-Arxml、DBC/CAN 与未来 BSW/诊断适配器，不复制商业 AUTOSAR 工具链。
- 状态：完成。

### P1：DBC、canonical contract 与 BSW intent 竖切

- 读取公开车窗 DBC，输出消息、信号和属性。
- 建立 DBC Signal → canonical signal → SWC/COM/I-PDU/PduR/CanIf 研究映射。
- 增加名称、长度、端序、缩放、偏移、单位、范围和引用检查。
- 对接 Generate-Arxml 报告，不把 Workbench 扩成完整 ECUC generator。
- 状态：完成。

### P2：确定性故障套件

- 加入正常基线和配置故障注入。
- 生成 JSON 与 Markdown 双层证据报告。
- 确立“确定性规则最终判定，AI 不覆盖规则结果”。
- 状态：完成。

### R0：python-can virtual 运行时

- 双节点收发、DBC 编解码、错误 ID、越界值和接收超时。
- 周期发送、抖动、丢帧、超时及恢复状态实验。
- 状态：完成。

### R1：CAN 日志、解码与回放

- 支持 can-utils `.log`、DBC 离线解码和两种时间策略回放。
- 记录 BusConfig、日志/DBC SHA-256、Finding 和实验报告。
- 状态：完成。

### R2a：backend 抽象与能力探测

- 增加 backend capability probe 和结构化 blocked reason。
- virtual 与 SocketCAN 复用同一实验契约。
- 最近记录：22 项测试通过，1 项因 Windows 无 SocketCAN 条件跳过。
- 状态：代码完成，Linux 实机验收未完成。

### R2b：SocketCAN 真实闭环（2026-08-17）

- `probe_socketcan.sh` 复核：`can_config_present=true`、`module_dir_present=true`、`vcan_module_present=true`、`vcan0_present=true`、`can_utils_present=true`、`systemd_running=true`。
- `setup_vcan.sh --dry-run` 先列出幂等操作，随后 `setup_vcan.sh --apply` 创建并拉起 `vcan0`。
- can-utils 原始验证通过：`candump vcan0` 收到 `vcan0 123 [8] 2A 00 01 00 00 00 00 00`。
- 建立 Linux 专用虚拟环境 `.venv-linux`，安装 `automotive-workbench 0.1.0`、`cantools 41.4.3`、`python-can 4.6.1`。
- `probe-can-backend --interface socketcan --channel vcan0` 返回 `status=available`，`open/send/receive/capture/replay=true`。
- `run-backend-lab --interface socketcan --channel vcan0` 返回 `status=passed`，`captured_count=3`、`decoded_count=3`、`finding_count=0`、`replayed_count=3`、`replay_integrity=true`。
- backend lab 已补充后端中立故障场景：`wrong_arbitration_id` 检出 `0x101`，`receive_timeout` 检出 30 ms 超时。
- Linux 测试：`.venv-linux` 下 `PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v`，22 项通过，1 项非 Linux 行为测试跳过。
- Windows 侧：PowerShell 可调用 `Python 3.14.4`；但当前 WSL→PowerShell 桥接运行 unittest 返回 `WSL ... UtilBindVsockAnyPort ... socket failed 1`，未进入 Python 测试输出。Windows 回归需在原生 PowerShell 或 CI 中复验。
- 报告路径：`output/socketcan-probe/backend-probe.json`、`output/socketcan-lab/backend-lab-report.json`、`output/socketcan-lab/capture/capture.log`、`output/socketcan-lab/decode/decode-report.json`、`output/socketcan-lab/replay/replay-report.json`。
- 状态：Linux SocketCAN 闭环完成；Windows 原生回归待复验。

### R2c：可重复 Linux 实验入口（2026-08-17）

- 新增 `scripts/linux/run_socketcan_lab.sh`，作为普通用户可运行的非 sudo lab 入口。
- 入口职责：运行 `probe_socketcan.sh`、检查 `vcan0`、用 `candump -n 1`/`cansend` 做原始帧 smoke、运行 Workbench `probe-can-backend` 和 `run-backend-lab`。
- 输出目录默认 `output/socketcan-smoke`，包含 `socketcan-host-probe.json`、`can-utils-smoke.log`、`workbench-probe` 和 `workbench-lab` 报告。
- 入口不包含 `sudo`、`modprobe`、`ip link add`、`ip link set` 或包安装；host 准备仍由 `setup_vcan.sh --dry-run` 和 `setup_vcan.sh --apply` 显式完成。
- `docs/socketcan-wsl.md` 已补充一条命令 lab 入口和 WSL shutdown 后恢复 `vcan0` 的步骤。
- R2c 入口实测通过：`bash scripts/linux/run_socketcan_lab.sh --output output/socketcan-smoke` 返回 `SOCKETCAN_LAB_PASSED`。
- Linux 测试：`.venv-linux` 下 `PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v`，23 项通过，1 项非 Linux 行为测试跳过。
- Windows 桥接复验：WSL 中调用 PowerShell 和 `cmd.exe` 运行 Windows unittest 均返回 `WSL ... UtilBindVsockAnyPort ... socket failed 1`，未进入 Python 测试输出。
- Windows 原生 PowerShell 回归：用户反馈已测试完毕且无问题。
- 状态：完成。

### R3a：OpenBSW readiness 与路线判断（2026-08-17）

- 增强 `scripts/linux/probe_openbsw.sh`，新增 Docker daemon 状态和 Git/GCC/G++/CMake/Ninja/Python 版本输出，仍保持只读。
- readiness 结果已保存到 `output/openbsw-readiness/readiness.json`。
- 新增 readiness 报告：`docs/research/openbsw-r3-readiness-2026-08-17.md`。
- 当前环境：Ubuntu 24.04、Microsoft WSL2 kernel `6.18.33.2`、`vcan0_present=true`、`git/gcc/g++/make/cmake/ninja/python3` 均存在。
- Docker 路线：`docker_cli_present=false`、`docker_daemon_available=false`，官方 development container 路线当前不可直接执行。
- 原生路线：CMake `3.28.3`、Ninja `1.11.1`、GCC/G++ `13.3.0` 可用；但 `official_native_baseline=false`，因为官方原生说明不是 Ubuntu 24.04 baseline。
- 推荐首次尝试：如用户批准，clone OpenBSW 到 WSL Linux 文件系统例如 `~/work/openbsw`，用 Ubuntu 24.04 原生 CMake 做一次限时 POSIX configure/build，并把失败明确分类。
- 建议预算：60-90 分钟，WSL Linux 文件系统预留 8-12 GB。
- 状态：readiness 完成；等待是否批准 native clone/build。

### R3b：OpenBSW POSIX native baseline（2026-08-17）

- Docker 重新复核：`docker_cli_present=true`、`docker_daemon_available=true`，证据保存到 `output/openbsw-readiness/readiness-2026-08-17-docker.json`。
- OpenBSW 已克隆到 WSL Linux 文件系统：`/home/dev/work/openbsw`。
- Remote：`https://github.com/eclipse-openbsw/openbsw.git`。
- Commit：`dbd6e118a9aaa2db36e4461ce76655e8f285598d`。
- License/NOTICE：根 `LICENSE` 为 Apache License 2.0，根 `NOTICE.md` 声明 `SPDX-License-Identifier: Apache-2.0` 并列出第三方许可证。
- 官方 Docker development service 已尝试：`DOCKER_UID=$(id -u) DOCKER_GID=$(id -g) docker compose run --build --rm development cmake --preset posix-freertos`。
- Docker 路线结果：未进入 CMake；官方 `docker/development/Dockerfile` 无跳过交叉工具链的开关，必须下载 ARM GCC、ARM LLVM、treefmt、bazelisk、buildifier、Rust 和 Python 依赖。首轮在 ARM GCC 143 MB 下载约 11% 时中止，分类为 `docker-image-dependency-download-too-heavy-for-first-spike`。
- 原生 configure：`cmake --preset posix-freertos` 通过，平台为 `POSIX`，RTOS 为 `FREERTOS`，`PLATFORM_SUPPORT_CAN/ETHERNET/MIDDLEWARE/STORAGE/TRANSPORT/UDS` 均为 ON；Doxygen 缺失仅影响文档生成。
- 原生 build：`cmake --build --preset posix-freertos --parallel` 通过，完成 379 个构建步骤。
- 产物：`build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf`、`libsocketCanTransceiver.a`、`libcpp2can.a`、`libdocan.a`。
- 首次运行时 `vcan0_present=false`，referenceApp 报 `SocketCanTransceiver Failed to ioctl socket (node=vcan0)`；随后执行 `bash scripts/linux/setup_vcan.sh --apply` 恢复 `vcan0`。
- 恢复后 5 秒 smoke：referenceApp 完成 lifecycle 初始化，DoIP/UDS 初始化，CAN demo 发出 `id=0x558,length=4`；`timeout 5s` 返回 124 属于预期终止。
- TAP Ethernet 报 `TapEthernetDriver start failed!`，暂不纳入本次 CAN/POSIX spike 阻塞项。
- Workbench 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 在沙箱外权限下通过，23 项通过、1 项非 Linux 行为测试跳过；普通沙箱内因 `socket.if_nameindex()` 读取网络接口权限不足失败，不是代码断言失败。
- R3 报告：`docs/research/openbsw-r3-posix-spike-2026-08-17.md`。
- 状态：部分完成；baseline build/run 完成，下一步是源码入口索引固化和最小测试候选，不进入完整 BSW 集成。

### R3c：OpenBSW 源码入口索引与测试 baseline（2026-08-17）

- 已固化源码入口索引：`docs/research/openbsw-r3-source-index-2026-08-17.md`。
- 索引覆盖 POSIX `main()`/`app_main()`、`platformLifecycleAdd()`、`CanSystem`、`SocketCanTransceiver`、`CanDemoListener`、DoCAN transport 和 unit test 入口。
- 明确 Workbench SocketCAN lab 与 OpenBSW referenceApp demo traffic 是两条不同语义链：Workbench 继续以公开车窗 DBC 为确定性 baseline，OpenBSW 当前只作为源码和 POSIX runtime 学习底座。
- `cmake --preset tests-posix-debug` 通过，生成目录为 `/home/dev/work/openbsw/build/tests/posix/Debug`。
- `cmake --build --preset tests-posix-debug --parallel` 通过，223/223 构建步骤完成。
- `ctest --preset tests-posix-debug --output-on-failure` 通过，1878/1878 测试通过、0 失败，总耗时 33.79 秒。
- 相关标签：`cpp2canTest` 33 项、`docanTest` 168 项、`socketCanTransceiverTest` 5 项、`udsTest` 286 项。
- Workbench 回归：普通沙箱内因 `socket.if_nameindex()` 网络接口权限限制在 `test_can_backend` import 阶段失败；沙箱外重跑 `PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，23 项运行、2 项跳过（当前 `vcan0` 不可用和非 Linux 行为测试）。
- 最小测试候选调整：后续若改 OpenBSW，优先选择 CANFrame invariant 或 DoCAN addressing/filter 的小测试；暂不修改 referenceApp runtime 行为。
- 状态：完成。

### R3d：OpenBSW 最小测试候选落地（2026-08-17）

- 在 OpenBSW 本地 clone 中新增最小测试：`/home/dev/work/openbsw/libs/bsw/cpp2can/test/src/can/canframes/CANFrameTest.cpp`。
- 新增测试名：`CANFrameTest.ClassicCanFrameInvariants`。
- 测试意图：验证 Workbench 读取 OpenBSW 作为 runtime/source reference 时依赖的 classic CAN 假设，包括 `MAX_FRAME_LENGTH == 8`、base ID 上限等于 `CanId::MAX_RAW_BASE_ID`、extended ID 上限等于 `CanId::MAX_RAW_EXTENDED_ID`，并确认 base/extended constructor 保留 raw ID 和 payload length。
- 作用说明：这是一个窄 guardrail，不是 runtime 功能或 adapter 集成；如果 OpenBSW 后续改变 classic CAN payload、base/extended ID 上限或 ID 编码语义，该测试应提前失败，迫使 Workbench adapter 假设被显式复核。
- 未修改 OpenBSW runtime、referenceApp、SocketCAN adapter 或 Workbench 代码。
- 验证：`cmake --build --preset tests-posix-debug --target cpp2canTest --parallel` 通过。
- 验证：`ctest --preset tests-posix-debug -R CANFrameTest --output-on-failure` 通过，7/7。
- 验证：`ctest --preset tests-posix-debug -L cpp2canTest --output-on-failure` 通过，34/34。
- 验证：`ctest --preset tests-posix-debug --output-on-failure` 通过，1879/1879、0 失败、总耗时 34.81 秒。
- 构建时出现一次 `libgcov profiling error ... overwriting an existing profile data with a different checksum`，原因是 coverage `.gcda` 旧数据与新对象校验不一致；构建退出码为 0，后续 CTest 全量通过。
- 状态：完成。

### R3e：OpenBSW patch artifact 整理（2026-08-18）

- 保留 OpenBSW 本地 clone 的唯一代码改动：`libs/bsw/cpp2can/test/src/can/canframes/CANFrameTest.cpp` 中的 `CANFrameTest.ClassicCanFrameInvariants`。
- 在 Workbench 仓库中新增 patch artifact：`patches/openbsw/0001-cpp2can-add-classic-canframe-invariant-test.patch`。
- 新增 patch 说明：`patches/openbsw/README.md`，记录 base commit、目标文件、测试意图、已完成验证和上游准备状态。
- 复核 OpenBSW `CONTRIBUTING.md`：PR 前应先通过 issue 与团队沟通；贡献合入需要 Eclipse Contributor Agreement。
- 当前结论：先把该测试作为 Workbench R3 研究证据和可复用 patch 保留；若要上游化，下一步应先开或加入 OpenBSW issue，说明这是 classic CAN frame contract 的窄 guardrail。
- 验证：`git diff --check` 在 `/home/dev/work/openbsw` 通过；本次 Workbench 只新增文档/patch artifact，未改运行时代码。
- 状态：完成。

### R4a：UDS/ISO-TP 架构调研（2026-08-18）

- 新增调研文档：`docs/research/uds-isotp-architecture-research-2026-08-18.md`。
- 调研对象：`python-can` Bus/virtual backend、`can-isotp` v2.x、`udsoncan` connection/client、Linux kernel SocketCAN ISO-TP。
- 架构选择：以 `udsoncan Client -> PythonIsoTpConnection -> can-isotp NotifierBasedCanStack -> python-can BusConfig` 作为 R4 主路径。
- backend 策略：`python-can virtual` 作为 CI-safe 和 Windows/WSL 通用 baseline；Linux kernel ISO-TP socket 作为后续 SocketCAN 集成路径；OpenBSW DoCAN 暂作为源码学习和后续比较路径。
- 决策原因：最大化复用现有 `BusConfig`、backend probe、JSON/Markdown evidence 和 deterministic Finding 模型；避免手写 ISO-TP/UDS 协议栈。
- 建议新增 optional dependency group：`diag = ["cantools>=41.4,<42", "python-can>=4.6,<5", "can-isotp>=2.0,<3", "udsoncan>=1.26,<2"]`。
- 下一步：新增 `schemas/uds-intent.schema.json`、`examples/window_control/uds_intent.json`，再实现 virtual UDS lab 的 positive DID read、NRC 和 timeout 三个场景。
- 状态：完成。

### R4b：最小 UDS intent/schema（2026-08-18）

- 新增 `schemas/uds-intent.schema.json`，定义 `uds-intent-0.1` 顶层字段、normal 11-bit transport、DID 和 `ReadDataByIdentifier` 场景。
- 新增 `examples/window_control/uds_intent.json`，包含 `WindowController`、request ID `0x700`、response ID `0x708`、VIN DID `0xF190`、窗口位置快照 DID `0xF111`，以及 positive/NRC/timeout 三个诊断场景。
- 新增 `src/automotive_workbench/diag_intent.py`，提供 `load_uds_intent()` 和 `summarize_uds_intent()`，做版本、ID范围、request/response ID差异、DID重复、codec、场景引用等确定性校验。
- `inspect` CLI 已支持 `uds_intent.json` 摘要输出，README 已加入示例命令和边界说明。
- 新增 `tests/test_diag_intent.py` 覆盖正常加载、positive 场景引用未知 DID、request/response ID 混淆三类行为。
- 状态：完成。

### R4c：virtual UDS/ISO-TP lab（2026-08-18）

- 新增 `src/automotive_workbench/uds_runtime.py`，实现 `run_uds_lab()`。
- 运行路径：`udsoncan Client -> PythonIsoTpConnection -> can-isotp NotifierBasedCanStack -> python-can virtual BusConfig`。
- 实验内置本地确定性 ECU responder，只支持 R4 的最小 `0x22 ReadDataByIdentifier` 场景，不实现完整 DCM/DEM/security/flash。
- 当前覆盖三个场景：`read_vin` 正响应 `0x62 F190 ...`、`unknown_did_nrc` 负响应 `0x7F 22 31`、`response_timeout` 无响应超时。
- 新增 CLI：`run-uds-lab examples/window_control/uds_intent.json --output output/uds-lab`。
- 输出：`uds-lab-report.json` 和 `uds-lab-report.md`，包含 request/response CAN ID、ISO-TP params、raw UDS payload、decoded value、responder observed requests/responses 和 findings。
- 新增 `tests/test_uds_runtime.py` 覆盖 virtual UDS lab 的三类场景。
- 新增依赖 extra：`diag = ["cantools>=41.4,<42", "python-can>=4.6,<5", "can-isotp>=2.0,<3", "udsoncan>=1.26,<2"]`。
- 依赖安装：`.venv-linux/bin/pip install -e '.[diag]'` 完成，安装 `can-isotp 2.0.7` 和 `udsoncan 1.26.1`。
- 验证：`PYTHONPATH=src .venv-linux/bin/python -m automotive_workbench.cli run-uds-lab examples/window_control/uds_intent.json --output output/uds-lab` 通过，输出 `status=passed`、`scenario_count=3`、`passed_count=3`。
- 验证：`output/uds-lab/uds-lab-report.json` 和 `output/uds-lab/uds-lab-report.md` 已生成，包含 `0x700 -> 0x708`、`22F190 -> 62F190...`、`221234 -> 7F2231` 和 `22F191` timeout 证据。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，28 项运行、2 项因环境跳过。
- 状态：完成。

### R4d：UDS backend probe 与 blocked 证据（2026-08-19）

- `run_uds_lab()` 现在在建立 ISO-TP client/responder 前先复用 `probe_can_backend()`。
- virtual 默认 channel 仍会自动替换为唯一 channel，避免多次运行互相串扰；probe evidence 会随 `uds-lab-report.json` 一起归档。
- 当 `--interface socketcan --channel <iface>` 不可用时，诊断 lab 返回 `status=blocked` 和结构化 `reason`，例如 `interface_missing`；这类情况不再混同为业务诊断场景失败。
- blocked 情况会同时写出 `output/.../probe/backend-probe.json` 与 `uds-lab-report.json/md`，便于后续 Linux SocketCAN/ISO-TP 实机复验时留证。
- 新增 `tests/test_uds_runtime.py` 覆盖 virtual probe evidence 和 SocketCAN 接口缺失 blocked 路径。
- 验证：`PYTHONPATH=src .venv-linux/bin/python -m unittest tests.test_uds_runtime -v` 通过，2/2。
- 状态：完成；下一步是在 `vcan0` 可用时运行 `run-uds-lab --interface socketcan --channel vcan0`，确认用户空间 ISO-TP 在 SocketCAN backend 上的表现。

### R4e：SocketCAN UDS 复验入口（2026-08-19）

- 新增 `scripts/linux/run_socketcan_uds_lab.sh`，作为普通用户可运行的非 sudo UDS/ISO-TP 复验入口。
- 入口职责：运行 `probe_socketcan.sh` 归档 host evidence，然后调用 `run-uds-lab --interface socketcan --channel <channel>`。
- 入口不包含 `sudo`、`modprobe`、`ip link add`、`ip link set` 或包安装；host 准备仍由 `setup_vcan.sh --dry-run/--apply` 显式完成。
- 输出目录默认 `output/socketcan-uds-smoke`，包含 `socketcan-host-probe.json`、`socketcan-host-probe.config.txt`、`workbench-uds-lab.stdout.json` 和 `workbench-uds-lab/` 下的 probe/lab 报告。
- 当 `vcan0` 缺失、接口权限不足或 backend 不可打开时，CLI 返回 `status=blocked`，脚本返回 blocked 标记和退出码 3；R4f 后优先在独立 probe 阶段返回 `SOCKETCAN_UDS_PROBE_BLOCKED`。
- `docs/socketcan-wsl.md` 已补充 SocketCAN UDS lab 命令、输出清单和 WSL shutdown 后恢复步骤。
- 新增 `tests/test_linux_scripts.py` 脚本契约测试，确保 UDS 复验入口不会准备或修改 host。
- 状态：代码与文档完成；等待 `vcan0` 可用时实机运行。

### R4f：UDS backend 独立探测（2026-08-19）

- 新增 CLI：`probe-uds-backend --interface <backend> --channel <channel>`。
- 探测内容：`python-can`、`can-isotp`、`udsoncan` 可选依赖是否存在，复用 `probe_can_backend()` 的 CAN backend 结果，并记录 Linux kernel ISO-TP module 是否 loaded/file present。
- 探测结论区分 `available`、`blocked` 和结构化 `reason`；缺少诊断依赖时为 `missing_diag_dependency`，CAN backend 不可用时沿用 `interface_missing` 等 backend reason。
- 输出：`uds-backend-probe.json` 和 `uds-backend-probe.md`；Markdown 明确当前 lab 走 user-space `can-isotp`，kernel ISO-TP 仅作为后续 Linux 对比证据。
- `scripts/linux/run_socketcan_uds_lab.sh` 现在先执行独立 `probe-uds-backend`；probe blocked 时返回 `SOCKETCAN_UDS_PROBE_BLOCKED`，不再继续启动 lab。
- 新增 `tests/test_uds_runtime.py` 覆盖 virtual UDS probe available 和 SocketCAN 接口缺失 blocked。
- 验证：`probe-uds-backend --interface virtual --channel workbench-uds-probe` 返回 `status=available`，记录 `python-can 4.6.1`、`can-isotp 2.0.7`、`udsoncan 1.26.1`。
- 验证：`probe-uds-backend --interface socketcan --channel vcan0` 在当前 `vcan0_present=false` 环境返回 `status=blocked`、`reason=interface_missing`，同时记录 `kernel_isotp.module_file_present=true`。
- 验证：`bash scripts/linux/run_socketcan_uds_lab.sh --output output/socketcan-uds-smoke-r4f` 返回 `SOCKETCAN_UDS_PROBE_BLOCKED` 和退出码 3。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，32 项运行、2 项环境跳过。
- 状态：代码、文档与 blocked 路径验证完成；等待 `vcan0` 可用时实机运行。

### R4g：UDS malformed payload 证据扩展（2026-08-19）

- `uds-intent-0.1` schema 的 scenario expectation 新增 `malformed_payload`。
- `examples/window_control/uds_intent.json` 新增 `malformed_window_position_payload` 场景：请求 DID `0xF111`，responder 返回不完整 positive response `62F111`。
- `diag_intent.load_uds_intent()` 增加 malformed 场景校验：DID 必须已声明，`response_payload_hex` 必须是合法 hex。
- `run_uds_lab()` 的本地确定性 responder 支持按 DID 注入 malformed response；client 解码失败时场景判定为 `passed`，并输出 `UDS-MALFORMED-PAYLOAD` Finding。
- 新增/更新 `tests/test_diag_intent.py` 和 `tests/test_uds_runtime.py`，覆盖 malformed intent 校验、runtime 场景结果和 Finding。
- 验证：`PYTHONPATH=src .venv-linux/bin/python -m unittest tests.test_diag_intent tests.test_uds_runtime -v` 通过，8/8。
- 验证：`run-uds-lab examples/window_control/uds_intent.json --output output/uds-lab-r4g` 返回 `status=passed`、`scenario_count=4`、`passed_count=4`，并生成 `UDS-MALFORMED-PAYLOAD` Finding。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，33 项运行、2 项环境跳过。
- 状态：完成；下一步仍是在 `vcan0` 可用时运行 SocketCAN UDS 实机复验。

### R4h：SocketCAN UDS 实机复验（2026-08-19）

- 执行 `bash scripts/linux/probe_socketcan.sh`，初始结果为 `vcan0_present=false`，但 kernel CAN/RAW/BCM/ISO-TP/VCAN 配置和模块文件均存在。
- 执行 `bash scripts/linux/setup_vcan.sh --dry-run`，确认计划操作为加载 `can/can_raw/vcan`、缺失时创建 `vcan0`、拉起 `vcan0`。
- 执行 `bash scripts/linux/setup_vcan.sh --apply`，返回 `VCAN_READY`，`vcan0` 状态为 `UP,LOWER_UP`。
- 普通沙箱内仍无法可靠读取新建网络接口，因此实机复验在非沙箱权限下运行。
- 首次并行运行 `run_socketcan_lab.sh` 与 `run_socketcan_uds_lab.sh` 时，UDS lab 通过，但 CAN lab 被并行 UDS 帧污染，报告中出现 `actual_frame_id=0x708` 和 `replay_integrity=false`；分类为测试调度污染，不是 SocketCAN backend 不可用。
- 随后单独重跑 `bash scripts/linux/run_socketcan_lab.sh --output output/socketcan-smoke-r4h-retry`，返回 `SOCKETCAN_LAB_PASSED`。
- 执行 `bash scripts/linux/run_socketcan_uds_lab.sh --output output/socketcan-uds-smoke-r4h`，返回 `SOCKETCAN_UDS_LAB_PASSED`。
- UDS SocketCAN 报告路径：`output/socketcan-uds-smoke-r4h/workbench-uds-lab/uds-lab-report.json`。
- UDS SocketCAN 结果：`status=passed`、`scenario_count=4`、`passed_count=4`，覆盖 positive DID read、NRC、timeout 和 malformed payload；`backend_probe.status=available`，backend 为 `python-can socketcan`。
- 经验约束：共享 `vcan0` 上的自动化实验应串行运行，或者后续给实验增加 ID/filter 隔离，避免不同 lab 的 CAN frame 互相污染。
- 状态：完成。

### R4i：SocketCAN 实验隔离与报告稳健性（2026-08-20）

- `open_bus()` 支持显式 `can_filters`；CAN backend lab 的 receiver 仅接收 `0x100/0x101`，UDS client/server 分别仅接收 `0x708/0x700`，均使用 11-bit 精确 mask `0x7FF`。
- `run_socketcan_lab.sh` 和 `run_socketcan_uds_lab.sh` 在运行前获取同一个按 channel 命名的 `flock`；共享 `vcan0` 的 Workbench 实验会串行，等待 30 秒超时则返回 blocked 退出码 3。
- CAN backend 报告新增 capture integrity、filter/lock isolation evidence 和 `CAN-CHANNEL-CONTAMINATION` Finding；UDS 报告新增 client/server filter 与 lock evidence。
- 新增 virtual bus filter 回归，确认 `0x708` 不会进入只接收 `0x100` 的 receiver；新增脚本锁契约和结构化污染 Finding 测试。
- 恢复 `vcan0` 后同时启动两个 SocketCAN 入口；两者都返回 0，CAN 报告 `capture_integrity=true`、`replay_integrity=true`、`contamination_finding_count=0`，UDS 报告 `status=passed`、4/4 场景通过。
- 并发复验报告：`output/socketcan-smoke-r4i/workbench-lab/backend-lab-report.json` 和 `output/socketcan-uds-smoke-r4i/workbench-uds-lab/uds-lab-report.json`；两份报告记录同一锁路径 `socketcan-vcan0.lock`。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，35 项运行、2 项环境跳过。
- 状态：完成。

### R4j：最小 DTC/DEM 生命周期实验（2026-08-20）

- 新增 `schemas/dtc-intent.schema.json` 和 `examples/window_control/dtc_intent.json`，定义 vendor-neutral DTC code、failure/healing threshold、UDS 初始 status byte 和有序实验步骤。
- 公开样例 DTC 为 `WindowObstructionDetected` / `0xC00100`；该编号和策略只是 research intent，不是 OEM 分配。
- 新增 `dtc_intent.py` 严格 loader/summary，校验 code 唯一性、阈值、status availability mask、实验引用、read mask 和期望状态。
- 新增 `dtc_lifecycle.py` 和 CLI `run-dtc-lifecycle`，确定性覆盖 `absent -> pending -> confirmed -> healing -> healed -> cleared`，输出 JSON/Markdown trace 和 `DTC-LIFECYCLE-MISMATCH` Finding。
- 8 步生命周期实验通过；关键 status byte 为 pending `0x25`、confirmed `0x2D`、healing `0x2C`、healed `0x28`，清除后 `0x00`。
- `uds-intent-0.1` 新增对 `dtc_intent.json` 的相对引用，并新增 `ReadDTCInformation.reportDTCByStatusMask` 和 `ClearDiagnosticInformation` 场景契约。
- UDS responder/client 已通过 `udsoncan` 和 user-space ISO-TP 实际执行 `190208 -> 5902FFC0010028`、`14FFFFFF -> 54`、清除后 `190208 -> 5902FF`；验收同时比对 DTC code 与 status byte。
- virtual UDS lab 结果：`output/uds-lab-r4j/uds-lab-report.json` 中 `status=passed`、7/7 场景通过。
- SocketCAN UDS 实机结果：`output/socketcan-uds-smoke-r4j/workbench-uds-lab/uds-lab-report.json` 中 backend 为 `python-can socketcan`、`status=passed`、7/7 场景通过，且持有 `socketcan-vcan0.lock`。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，42 项运行、2 项环境跳过；JSON、Python 编译、shell 语法和 diff 检查通过。
- 边界：本阶段不实现量产 DEM operation cycle、aging、displacement、freeze frame、extended data 或 NVRAM。
- 状态：完成。

### R4k：operation-cycle、aging 与 snapshot 证据（2026-08-20）

- 新增 `docs/research/dtc-operation-cycle-aging-snapshot-research-2026-08-20.md`，基于 AUTOSAR CP Dem 公开规范和 `udsoncan 1.26.1` 源码确定实验边界。
- 方案：保留 R4j 的 threshold-only `experiments`，在同一 `dtc-intent-0.1` 中新增独立 `cycle_experiments`、`aging_threshold` 和 confirmed-trigger snapshot，不混合两个状态机。
- 新增 `dtc_aging.py` 和 CLI `run-dtc-aging-lab`；显式处理 `operation_cycle_start/end`，monitor 事件只允许在 active cycle 内上报，否则生成 `DTC-CYCLE-SEQUENCE` Finding。
- aging 只在 event 已 confirmed、本 cycle 已测试且结果为 pass 时于 cycle end 累加；未测试 cycle 不累加，failed cycle 将 counter 复位。
- 12 步确定性实验通过：`0x50 -> 0x27 -> 0x2F -> 0x6D -> 0x2C -> 0x28 -> 0x68 -> 0x28 -> 0x00`；第一个 tested-pass cycle 后 aging=1，第二个后 aging=2 并进入 `aged_out`。
- DTC 首次进入 confirmed 时归档 record `0x01`，包含 DID `0xF111` / value `42`；达到 aging threshold 时 snapshot 被删除。
- UDS lab 新增 `ReadDTCInformation.reportDTCSnapshotRecordByDTCNumber` (`0x19/0x04`)；清除前 `1904C0010001 -> 5904C00100280101F1112A`，清除后 `1904C0010001 -> 5904C0010000`。
- virtual 结果：`output/dtc-aging-r4k/dtc-aging-report.json` 12/12 通过；`output/uds-lab-r4k/uds-lab-report.json` 9/9 通过。
- SocketCAN 实机结果：`output/socketcan-uds-smoke-r4k/workbench-uds-lab/uds-lab-report.json` 中 backend 为 `python-can socketcan`、9/9 通过。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，45 项运行、2 项环境跳过；JSON、Python 编译、shell 语法和 diff 检查通过。
- 边界：不实现量产 Dem event memory、displacement、NVRAM、combined event、OBD 法规或 OEM snapshot policy。
- 状态：完成。

### R4l：extended data 与 DTC 负面场景（2026-08-20）

- 新增 `docs/research/dtc-extended-data-negative-scenarios-research-2026-08-20.md`，基于 AUTOSAR CP Dem R24-11 和本地 `udsoncan 1.26.1` 源码确定最小边界。
- DTC intent 新增 `extended_data.records`：record `0x01` 为 occurrence counter，record `0x02` 为 aging counter，均使用一字节实验值；aging trace 同步记录 occurrence 和 extended-data 存储状态。
- occurrence 仅在首次进入 confirmed 时增加；aged-out 与 clear 删除关联 snapshot/extended data。该策略只服务确定性实验，不代表 OEM Dem 配置。
- UDS lab 新增 `ReadDTCInformation.reportDTCExtendedDataRecordByDTCNumber` (`0x19/0x06`)；预期证据为 `1906C0010001 -> 5906C00100280101` 和 `1906C0010002 -> 5906C00100280201`。
- 负面场景覆盖未知 DTC、未知 extended-data record（均为 `7F1931`）、malformed snapshot（`5904C00100` 必须被客户端拒绝），并保留既有非法 operation-cycle 顺序测试。
- virtual UDS lab 扩展为 15 个场景，包含 clear 后 extended data 复读返回 `7F1931`；`output/uds-lab-r4l/uds-lab-report.json` 为 15/15 通过。
- SocketCAN 实机报告 `output/socketcan-uds-smoke-r4l/workbench-uds-lab/uds-lab-report.json` 使用 `python-can socketcan`，15/15 通过，关键应用 payload 与 virtual 完全一致。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，46 项运行、2 项环境跳过；JSON、Python 编译、shell 语法和 diff 检查通过。
- 边界：不实现量产 Dem event memory、NVRAM、displacement、OBD 法规、OEM record layout 或 UDS conformance。
- 状态：完成。

### R4m：ECU reset 与持久镜像边界（2026-08-20）

- 新增 `docs/research/dtc-reset-persistence-research-2026-08-20.md`，基于 AUTOSAR CP Dem、Mode Management Guide 和本地 `udsoncan 1.26.1` 源码确定 reset/NvM 边界。
- DTC intent 新增受限 persistence policy 和两个 `reset_experiments`；只支持 `status/snapshot/extended_data`、显式 flush 和 clear 同步更新持久镜像。
- 新增 `dtc_reset.py`、CLI `run-dtc-reset-lab` 和 JSON/Markdown 报告；12 步覆盖 confirmed 运行态、flush、hard reset 恢复、clear 后 reset，以及 confirmed 但未 flush 时 reset 丢失。
- UDS intent/runtime 新增 `ECUReset hardReset` (`0x11/0x01`)；responder 发出 `5101` 后从进程内持久镜像重载 DTC 状态。
- hard reset 后复读 DTC、snapshot、extended data；clear 后再次 hard reset，DTC 仍为空、snapshot 仍为空、extended data 仍返回 `7F1931`。
- 确定性 reset lab `output/dtc-reset-r4m/dtc-reset-report.json` 为 12/12 通过；virtual UDS `output/uds-lab-r4m/uds-lab-report.json` 为 20/20 通过。
- SocketCAN 报告 `output/socketcan-uds-smoke-r4m/workbench-uds-lab/uds-lab-report.json` 使用 `python-can socketcan`，20/20 通过，reset 与复读应用 payload 和 virtual 完全一致。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，50 项运行、2 项环境跳过；JSON、Python 编译、shell 语法和 diff 检查通过。
- 边界：持久镜像只存在于单次进程；不实现 AUTOSAR NvM、flash、断电原子性、真实启动/总线中断或 DCM/BswM/EcuM 集成。
- 状态：完成。

### R4n：持久镜像完整性与失败注入（2026-08-20）

- 新增 `docs/research/dtc-persistence-integrity-fault-research-2026-08-20.md`，基于 AUTOSAR CP NvM、NV Data Handling Guide 和 Dem 公开规范确定最小故障分类。
- DTC intent 新增两个 `persistence_fault_experiments`，只允许 flush failure、checksum corruption 和 restore failure 三类预期 Finding。
- 新增 `dtc_persistence_fault.py`、CLI `run-dtc-persistence-fault-lab` 和 JSON/Markdown 报告；持久镜像使用 canonical JSON payload 的 SHA-256 作为确定性完整性标记。
- flush failure 产生 `DTC-PERSISTENCE-FLUSH-FAILED`，旧镜像 checksum 与空状态保持有效；随后 hard reset 恢复 last-good 空镜像。
- corruption 场景在 confirmed 镜像 flush 后篡改 checksum，产生 `DTC-PERSISTENCE-MIRROR-CORRUPTED`；hard reset 拒绝该镜像并产生 `DTC-PERSISTENCE-RESTORE-FAILED`，运行态回退为 `0x00`，损坏镜像保留作证据。
- fault lab `output/dtc-persistence-fault-r4n/dtc-persistence-fault-report.json` 为 13/13 通过，包含 3 个预期 Finding；R4m reset lab 12/12 和 UDS 目标回归继续通过。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，53 项运行、2 项环境跳过；JSON、Python 编译、shell 语法和 diff 检查通过。
- 边界：SHA-256 与进程内镜像仅用于确定性实验；不实现 NvM CRC 配置、异步 job、write retry、redundant block、ROM default、flash 或安全认证。
- 状态：完成。

### R4o：冗余镜像与 generation 仲裁（2026-08-20）

- 新增 `docs/research/dtc-redundant-mirror-generation-research-2026-08-20.md`，基于 AUTOSAR CP NvM 和 NV Data Handling Guide 区分标准 loss-of-redundancy 语义与 Workbench generation 策略。
- DTC intent/schema 新增两个 `redundancy_experiments`；每个副本保存独立状态、generation 和覆盖二者的 SHA-256 checksum。
- 新增 `dtc_redundancy.py`、CLI `run-dtc-redundancy-lab` 和 JSON/Markdown 报告；flush 写入较旧副本并使用 `max(generation) + 1`。
- 两份有效副本 generation 不同时选择较新副本并产生 `DTC-REDUNDANCY-LOSS`；仅一份有效时恢复该副本并产生同类 Finding。
- 新副本 A 损坏后，hard reset 选择旧但有效的 B，运行态从 confirmed `0x2F` 回退为空 `0x00`；相同 generation 但内容分歧会产生 `DTC-REDUNDANCY-ARBITRATION-FAILED`，不猜测副本。
- redundancy lab `output/dtc-redundancy-r4o/dtc-redundancy-report.json` 为 13/13 通过，包含 3 个预期 Finding。
- 回归：`PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v` 通过，59 项运行、2 项环境跳过；仲裁边界覆盖双副本一致、同 generation 内容冲突和双副本均无效；JSON、Python 编译和 diff 检查通过。
- 边界：generation 和 SHA-256 是进程内确定性策略；不实现 NvM job、MemIf/Fee/Ea、configured redundant block、repair、flash atomicity、wraparound、断电时序或安全认证。
- 状态：完成。

### R4p：冗余修复与中断写入边界调研（2026-08-31）

- 新增 `docs/research/dtc-redundancy-repair-interrupted-write-research-2026-08-31.md`，核对 AUTOSAR NvM loss-of-redundancy、损坏副本恢复、CRC、写验证和 retry 边界。
- 明确 generation、scrub 时机和 commit marker 不是引用规范定义的算法，必须保持为 Workbench 确定性策略。
- 定义 committed/staged 副本选择规则、幂等 repair、无有效源时拒绝 repair，以及中断普通写入/修复不得破坏 last-good 源副本的约束。
- 定义 3 类最小验收场景：普通写入在 commit 前中断、降级恢复后成功 repair 且二次 reset 无冗余告警、repair 在 commit 前中断仍可从原始源副本恢复。
- 决策：进入最小实现；不模拟 MemIf/Fee/Ea job、flash 粒度、擦除、磨损、并发或真实断电。
- 状态：调研完成，实现待开始。

### E1：WSL2 与 SocketCAN 基线

已确认：

- WSL `2.7.11.0`，Ubuntu `24.04.1 LTS`，内核 `6.18.33.2-microsoft-standard-WSL2`；
- `CONFIG_CAN=m`、`CONFIG_CAN_RAW=m`、`CONFIG_CAN_ISOTP=m`、`CONFIG_CAN_VCAN=m`；
- 匹配的 CAN/RAW/ISO-TP/VCAN 模块文件存在，不需要自定义 WSL 内核；
- Git、GCC、G++、Make、Python、ip、modprobe、can-utils、CMake、Ninja 已存在；
- `vcan0` 已创建并可用；WSL shutdown 后该运行期接口可能消失，需要重新执行 `setup_vcan.sh --apply`。

环境故障与结论：

- `/mnt/d` 曾整体返回 `Input/output error`，不是全角目录 `ＬＬＭ` 单点问题；
- 执行 `wsl --shutdown` 后 DrvFS 挂载恢复；
- Windows 路径是 `D:\ＬＬＭ\automotive-workbench`，WSL 路径是 `/mnt/d/ＬＬＭ/automotive-workbench`；
- PowerShell 使用 Windows 路径，Ubuntu shell 使用 `/mnt/d/...`；
- `pagefile.sys` 等系统文件 Permission denied 不影响项目。

2026-08-17 探测摘要：

```text
can_config_present=true
module_dir_present=true
vcan_module_present=true
vcan0_present=false
can_utils_present=true
systemd_running=true
cmake_present=true
ninja_present=true
official_native_baseline=false
```

`official_native_baseline=false` 只表示 OpenBSW 官方原生说明不是以 Ubuntu 24.04 为基线，兼容性需要 spike 验证。

### E2：VS Code/WSL 接入

- 项目已能从 Ubuntu 正常进入并读取。
- Ubuntu 中 `code .` 尚不可用。
- 不在 WSL 内安装 Snap 版 VS Code；应使用 Windows VS Code 的 Microsoft WSL 扩展连接 Ubuntu。
- 状态：等待验证 VS Code 左下角显示 `WSL: Ubuntu-24.04`。

### E3：平台工程文档归仓（2026-08-17）

- 将平台升级账本、路线、Windows/WSL 决策、SocketCAN/OpenBSW/CAN 日志调研及环境学习记录迁入本仓 `docs/`；
- 建立 `docs/README.md` 作为统一文档入口；
- `D:\work\improve` 的原路径仅保留迁移提示，不再形成两份可编辑状态源；
- 明确仓库边界：Workbench 保存平台工程资产，improve 保存职业成长、Sprint、面试与证据索引；
- 状态：完成（文档迁移，无运行时代码变化，因此不触发代码测试）。

## 当前升级：R3 OpenBSW POSIX 限时 spike

目标：在不破坏 R2 已完成 SocketCAN 闭环的前提下，执行一次受限 OpenBSW POSIX spike，并形成可复现 build/run evidence 与源码入口索引。

执行与验收：

1. 先复核 Docker/工具链/vcan readiness；
2. clone OpenBSW 到 WSL Linux 文件系统，不在 `/mnt/d` 直接构建大型 C++ 仓库；
3. 记录 remote URL、commit SHA、`LICENSE`、`NOTICE.md`；
4. 优先尝试官方 Docker development service；若镜像下载或环境成本超预算，则分类记录并执行 Ubuntu 24.04 原生 POSIX configure/build；
5. 记录成功、失败类别和下一步，不超过预算继续修环境；
6. 只构建官方 POSIX reference/demo，不接入商业 AUTOSAR 工具链，不声称 OpenBSW 是完整 Classic BSW 替代品。

完成条件：

- clone commit SHA 和 license evidence 完成；
- POSIX configure/build 有可复现结果；
- CAN/POSIX 入口和 unit test 入口形成索引；
- 成功或失败都有分类报告；
- 不超过预算扩展 scope。

当前结果：R3a/R3b/R3c/R3d 已完成 readiness、native POSIX baseline、source index、`tests-posix-debug` 执行 baseline 和最小 CANFrame 测试候选；Docker development container 仍保持暂缓，不作为当前阻塞项。

## 下一步方向

### 最近一步：R4p 最小 repair/scrub 与 commit-marker 故障实验

按调研定义实现 staged/committed 选择、幂等 repair 和两类 commit 前中断证据；不直接实现 NvM redundant block、Fee/Ea 或 flash 管理。

### 已冻结的可选工作：OpenBSW 上游化与完整容器

- R3a-R3e 已完成 native POSIX baseline、源码索引、全量测试和 patch artifact，不再作为当前阻塞项。
- 是否开启 OpenBSW issue/PR 或继续完整 development 容器，等诊断闭环需要或有明确上游目标时再决定。

诊断链稳定后再进入带引用、可拒答的 AI 工程审查。

## 下次必须补录

- 是否整理 OpenBSW patch/PR，或仅保留本地学习证据；
- Docker development 镜像是否继续完整构建或保持暂缓。
