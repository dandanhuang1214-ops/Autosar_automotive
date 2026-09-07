# Automotive Software Engineering Workbench 路线v2

## 实施状态（2026-09-07）

- 已完成：统一 Artifact/Finding/Trace 骨架；Generate-Arxml report adapter；DBC→BSW intent→canonical contract 静态校验。
- 已完成：基线与五类配置故障注入，JSON/Markdown 证据报告，Windows/Linux CI 定义。
- 已完成：python-can virtual 双节点收发、DBC 编解码、错误 ID、越界值与接收超时。
- 已完成：周期发送观测、丢帧超时和 `RECEIVING → TIMEOUT → RECOVERED` 监督状态实验。
- 下一阶段：CAN 日志统一格式与 replay；随后实现 SocketCAN adapter，在环境可用时复用相同实验契约。
- R1 已完成（2026-08-14）：can-utils `.log` 录制、DBC 离线解码、原始时间/固定 gap 回放、BusConfig、日志/DBC SHA-256、Finding 和双层证据报告。
- 当前下一阶段调整为 R2：SocketCAN 环境探测与 backend adapter；不自动编译或替换 WSL 内核。
- R2a 已完成（2026-08-16）：backend capability probe、结构化 blocked reason/退出码、virtual/SocketCAN 共用实验契约、条件式 vcan0 测试。
- R2 环境工具已完成：只读 host probe、默认 dry-run 的幂等 vcan0 setup、显式 apply 与安全 rollback。
- R2b 已完成 Linux 侧闭环（2026-08-17）：`vcan0` 已创建，can-utils 原始帧收发通过，Workbench SocketCAN backend probe/lab 通过，backend lab 覆盖正常 capture/decode/replay、错误 arbitration ID 与接收超时；Linux 测试 22 项通过、1 项非 Linux 行为测试跳过。Windows 原生回归需在 PowerShell 或 CI 中复验。
- R2c 已完成 Linux 入口（2026-08-17）：新增 `scripts/linux/run_socketcan_lab.sh`，普通用户一条命令完成 host probe、can-utils smoke、Workbench SocketCAN probe/lab 和报告归档；sudo host 准备仍由 `setup_vcan.sh --dry-run/--apply` 显式完成；WSL shutdown 后 `vcan0` 恢复步骤已写入文档。
- Windows 原生回归已由用户在 PowerShell 复验通过；R2 阶段门槛完成。
- R3a readiness 已完成（2026-08-17）：Docker CLI/daemon 当前已可用；Ubuntu 24.04 原生工具链具备 Git/GCC/G++/Make/CMake/Ninja/Python，但不是官方 Ubuntu 22.04 native baseline。
- R3b baseline 已部分完成（2026-08-17）：OpenBSW 已克隆到 WSL Linux 文件系统，官方 Docker development 镜像因完整工具链下载过重暂缓；Ubuntu 24.04 原生 `posix-freertos` configure/build 通过，referenceApp 在恢复 `vcan0` 后完成 CAN 发送 smoke。
- R3c 已完成（2026-08-17）：固化 OpenBSW POSIX/CAN/DoCAN/unit-test 源码入口索引；`tests-posix-debug` configure/build 通过，CTest 1878/1878 通过。
- R3d 已完成（2026-08-17）：在 OpenBSW 本地 clone 新增 `CANFrameTest.ClassicCanFrameInvariants` 最小测试候选；`CANFrameTest` 7/7、`cpp2canTest` 34/34、全量 `tests-posix-debug` CTest 1879/1879 通过。
- R3e 已完成（2026-08-18）：将 OpenBSW 最小测试候选整理为 Workbench patch artifact，路径为 `patches/openbsw/0001-cpp2can-add-classic-canframe-invariant-test.patch`；上游化前应先按 OpenBSW 贡献流程开 issue/沟通，并满足 Eclipse ECA 要求。
- R4a 已完成（2026-08-18）：选定 UDS/ISO-TP 架构为 `udsoncan Client -> PythonIsoTpConnection -> can-isotp NotifierBasedCanStack -> python-can BusConfig`；virtual 作为 deterministic baseline，SocketCAN kernel ISO-TP 和 OpenBSW DoCAN 作为后续集成/比较路径。
- R4b 已完成（2026-08-18）：新增 `uds-intent-0.1` schema、公开车窗诊断 intent 示例、`diag_intent` loader/summary 和 inspect CLI 支持；下一步进入 virtual UDS lab。
- R4c 已完成（2026-08-18）：新增 `run_uds_lab()` 和 CLI，使用本地确定性 responder 在 `python-can virtual` 上跑通 ReadDataByIdentifier positive/NRC/timeout 三类诊断场景，并输出 JSON/Markdown 证据。
- R4d-R4g 已完成（2026-08-19）：诊断 lab 已集成 backend probe/blocked 证据、SocketCAN 复验入口、独立 UDS backend probe 和 malformed payload Finding，virtual baseline 扩展为 4 类场景。
- R4h 已完成（2026-08-19）：SocketCAN UDS 实机复验 4/4 通过；同时发现共享 `vcan0` 上并行 CAN/UDS lab 会产生帧污染。
- R4i 已完成（2026-08-20）：CAN/UDS receiver 使用精确 ID filters，SocketCAN 入口使用按 channel 命名的 `flock`，报告记录 isolation evidence 和 contamination Finding；并发实机复验两个 lab 均通过。
- R4j 已完成（2026-08-20）：新增 `dtc-intent-0.1`、absent/pending/confirmed/healing/healed/clear 确定性实验和 Finding；UDS `0x19` 读取、`0x14` 清除、清除后复读在 virtual 和 SocketCAN 上均通过。
- R4k 已完成（2026-08-20）：调研并实现显式 operation-cycle、tested-pass aging/aged-out 和 confirmed-trigger snapshot；UDS `0x19/0x04` snapshot 在 virtual 和 SocketCAN 上均通过，clear 后 snapshot 正确消失。
- R4l 已完成（2026-08-20）：增加 occurrence/aging extended data、UDS `0x19/0x06`，并覆盖未知 DTC、未知 record、非法 cycle 顺序和 malformed snapshot。
- R4m 已完成（2026-08-20）：增加运行态/持久镜像对照实验和 UDS `0x11/0x01` hard reset，验证 flush 后恢复、未 flush 丢失和 clear 后不复活。
- R4n 已完成（2026-08-20）：增加 SHA-256 镜像完整性封套和 flush/corruption 故障注入，验证 last-good 保留与恢复失败安全回退。
- R4o 已完成（2026-08-20）：增加双副本 generation 仲裁、loss-of-redundancy 分类和损坏新副本后的旧副本回退证据。
- R4p 已完成（2026-08-31）：实现 committed/staged 副本、幂等 repair、中断普通写入/修复的 last-good 保留和 25 步确定性证据。
- R5a 调研已完成（2026-08-31）：定义 retrieval-only ReviewRequest/EvidenceUnit/Citation/ReviewResult、基于调用方 checks 的 coverage 和稳定拒答原因。
- R5b 已完成（2026-08-31）：实现本地 JSON Pointer EvidenceUnit、词法检索、SHA-256 citation 验证、required-check coverage 和 answered/partial/refused 证据。
- R5c 调研已完成（2026-08-31）：定义显式 comparable assertion、跨 artifact 冲突优先级、Markdown one-based inclusive line-range locator 和十案例 gold evaluation 契约。
- R5d 已完成（2026-08-31）：实现 Markdown line-range、`equals/all-equal` 跨 artifact assertion、冲突双方 citation 和十案例三次运行 gold evaluator；全部 gate 通过。
- R5e 已完成（2026-08-31）：复用公开 canonical contract、BSW、UDS 和 DTC intent，将评测扩展为 14 案例、30 checks，并新增五域 check count/accuracy 证据。
- R5f 已完成（2026-08-31）：新增白名单 CAN/UDS/DTC producer、运行时报告请求物化与实际 SHA-256 绑定，并将 3 项 runtime checks 和独立 3 项 held-out negative checks 分开计量。
- R5g 已完成（2026-09-01）：新增两次独立 runner 输出配对、稳定字段 allowlist drift injection、动态字段比较拒绝，以及 CAN/UDS/DTC 跨运行一致性和 CAN drift 冲突评测。
- R5h 已完成（2026-09-01）：新增 `review-request-0.3` applicability profile，variant、software/calibration version、backend 任一不一致即阻断比较；cross-run catalog 扩展到 CAN/UDS/DTC 三域稳定与 drift，并增加 profile mismatch 拒答案例。
- R5i 已完成（2026-09-01）：新增 `review-request-0.4` applicability locator；CAN/UDS/DTC runner 将输入哈希、runner contract 和实际 backend 固化为报告内 profile，evaluation 将 profile 与报告 SHA-256 一并归档并从 artifact 解析比较资格。
- R5j 已完成（2026-09-01）：新增 `review-request-0.5` baseline/candidate cohort、逐 candidate drift catalog 和 evaluator 0.7 三运行 producer；CAN cohort 覆盖 stable+drift 与 stable+profile mismatch 两类组合。
- R5k 已完成（2026-09-01）：三运行 cohort 扩展到 UDS decoded VIN 与 DTC confirmed state；evaluator 0.8 输出全局及 CAN/UDS/DTC 分域 drift 状态计数，全部精确 gate 通过。
- R5l 已完成（2026-09-03）：新增 evaluator 0.9 `external_reports`，可对 1～3 份已存在的本地 CI/外部 runner JSON 报告逐字节验证 SHA-256 和 applicability profile 后执行 cohort evaluation；与现场 `producer` 互斥，首个 CAN stable+drift 固定报告案例全部 gate 通过。
- R5m 已完成（2026-09-04）：evaluator 1.0 将固定报告 cohort 扩展到 CAN/UDS/DTC 三域；每份报告必须携带 provider、repository、run、job、commit provenance，验证后以 `hash-bound` 状态归档，三域 stable+drift gate 全部通过。
- R5n 已完成（2026-09-04）：evaluator 1.1 要求每份固定报告由调用方独立声明 repository/job/commit expectation，逐字段匹配后记录 `matched`；缺失、非法或不符均在 materialization 前 fail closed，九份 CAN/UDS/DTC 报告全部覆盖。
- R5o 已完成（2026-09-04）：evaluator 1.2 新增 case 级 repository + allowed job IDs policy，在逐报告 expectation 之后、materialization 之前拦截跨仓库和越权 job；结果以 `enforced` 状态归档，1.0/1.1 保持兼容。
- R5p 已完成（2026-09-06）：evaluator 1.3 为外部报告 integrity、provenance、expectation 和 policy 预检失败生成闭合的最小 rejection artifact，保持非零退出且不物化 request；双平台 CI 已配置无论成败都上传评测输出。
- R5q 本地实现与验证已完成（2026-09-07）：新增跨平台可控 SHA-256 mismatch 演练，CI 直接观察 CLI failure 后校验 rejection artifact、无 request/result 物化，并独立上传拒绝证据；GitHub Actions Windows/Ubuntu 远端运行仍待凭据恢复后验收。
- OpenBSW 前置调研已完成：官方容器仍是隔离路线，但首次 spike 已证明 Ubuntu 24.04 原生 POSIX baseline 可用；后续不能把 OpenBSW 扩展为完整 AUTOSAR Classic 替代品。
- 当前下一阶段：完成 R5q GitHub Actions 正常与可控拒绝两条 artifact 上传路径的远端验收；验收前不放宽 materialization 门槛，也不引入远端 artifact 下载、签名/attestation、外部 LLM 或向量库。

## 平台目标

平台采用“统一体验、分离内核、开放适配器”：两个旧项目近期不搬迁代码，由新的orchestrator通过artifact协议连接；长期再根据边界稳定程度决定是否monorepo。

```text
Windows Engineering Plane
  DOCX/Excel | Generate-Arxml | DaVinci | Simulink
                 ↓ artifacts
Workbench Core
  Artifact | Trace | Finding | TestResult | Evidence
                 ↓ adapters
Linux Execution Plane
  SocketCAN | OpenBSW | CAN/UDS runners | future OpenSOVD/openDuT
```

## 本周：平台设计基线，不追求大而全运行

截至周末平台应达到`v0-design`，交付：

1. 平台上下文与模块边界图；
2. `Artifact/Trace/Finding/TestResult`四个最小schema草案；
3. 第一版BSW意图对象表：Message、Signal、ComSignal、IPdu、PduRRoute、CanIfPdu；
4. Generate-Arxml和Evidence Workbench的adapter输入/输出清单；
5. Windows + WSL2双平面ADR；
6. 公开车窗案例的文件清单和数据流图；
7. 本机WSL环境由用户PowerShell复核。

本周不创建完整平台代码、不下载openDuT/OpenSOVD、不重构旧项目。

### 本周知识储备（约5小时）

- 90分钟：COM/PduR/CanIf职责和通信对象层级，只学到能定义意图对象；
- 60分钟：追踪一条DBC Signal到SWC Port/DataElement；
- 45分钟：学习artifact、adapter、port、finding四个平台概念；
- 45分钟：学习SocketCAN/vcan和Windows/WSL边界；
- 60分钟：口述平台边界并人工审核第一版schema。

## 未来一个月：形成可运行CLI竖切

### 第3周：CAN运行底座

- python-can virtual作为保底；
- WSL可用则建立SocketCAN/vcan；
- 实现公开车窗报文发送、接收、日志和replay；
- 正常场景 + 端序错误 + 超时/丢帧。

平台产物：`experiment manifest + log + test result + finding`。

### 第4周：跨层映射

- 建立DBC Signal ↔ canonical signal ↔ SWC DataElement/Port映射；
- 增加长度、范围、端序、scale、方向和缺失引用检查；
- 暂以表格/JSON表达COM Signal、I-PDU、PduR route、CanIf PDU意图。

平台产物：`bsw-intent v0.1 + trace report`。

### 第5周：OpenBSW POSIX spike

- 只构建官方POSIX reference/demo；
- 找到CAN系统入口、收发调用链和测试入口；
- 做一个小修改并补一个测试；
- 构建成本超过预算或依赖长期不通则退出，继续Python virtual ECU。

平台产物：`runtime adapter spike report`。

### 第6周：月度闭环

- 提供一个轻量CLI入口，不做Web：

```text
workbench inspect <dbc-or-report>
workbench trace <signal>
workbench run window-rx
workbench report <run-id>
```

- CLI可以先是orchestrator脚本，不要求重构两个旧项目；
- 形成1个正常运行和至少6个累计故障测试。

### 一个月后的平台形态

```text
公开车窗DOCX/Excel + DBC
→ SWC ARXML与校验报告
→ BSW意图映射
→ virtual CAN/OpenBSW实验
→ 可重复日志、Findings和报告
```

此时AI前端仍不是关键验收项。

## 2～3个月：通信与诊断工程平台

- 完成COM/PduR/CanIf对象语义和Rx/Tx数据流；
- 形成10～15个通信故障；
- 进入ISO-TP、UDS、DCM、DEM和DTC生命周期；
- 使用can-isotp、udsoncan建立虚拟诊断链；
- 评估OpenSOVD架构但不强制纳入；
- vendor-neutral intent可导出为表格/JSON，商业工具由adapter验证。

阶段验收：通信链、诊断链、20+自动化测试、12+故障案例。

## 4～5个月：平台核心与AI审查

- 建立独立Workbench Core和artifact registry；
- 抽取Evidence Workbench的FTS、citation、coverage和evaluation；
- 默认retrieval-only，无LLM也能审查；
- 接入Generate-Arxml、DBC/CAN、UDS四类artifact analyzer；
- 建立30题汽车工程评测集；
- 只在指标通过后开启AI解释与分层诊断。

openDuT仅在出现多DUT、远程执行或多种runner需求时做adapter；否则不引入。

## 第6个月：商业桥接与求职交付

- DaVinci公开样例导入、回导和golden diff；
- 如能合法使用，编写最小Automation Interface脚本；
- 保留EB/ISOLAR bridge接口设计，不假装已验证；
- 10分钟Demo、英文README、架构图和两套简历；
- 提交OpenBSW、cantools、python-can、OpenSOVD或openDuT中的高质量Issue/PR之一。

## 长期平台边界

- 平台可以逐步成为个人可维护的Automotive DevTool平台；
- 不成为商业BSW包、MCAL、RTE/OS generator或完整ECUC工具的复制品；
- 供应商能力通过adapter调用，核心保存中立意图、追踪、测试和证据；
- 所有AI输出必须依赖确定性Finding或可引用资料。
