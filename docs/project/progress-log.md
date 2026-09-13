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

## 当前总览（2026-09-12）

当前阶段：`P16 — 实际 Generate-Arxml 导出桥接，本地验收完成`；P15 工作流已本地验收，P14 是远端已冻结基线。用户已明确要求以平台升级目标推进，学习周次不驱动本次里程碑。P15/P16 实测结果见文末，远端 CI 尚待验收。

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
| ISO-TP/UDS 诊断链 | 完成当前闭环 | R4a-R4i 已完成架构、virtual/SocketCAN 和 isolation 证据；R4j-R4p 已完成 DTC 生命周期到冗余 repair/中断写入证据 |
| AI 工程审查 | 完成当前闭环 | R5a-R5q 已完成基础契约、引用/冲突、五类评测、artifact-bound applicability、跨域 drift catalog、固定报告 provenance/policy、preflight rejection evidence 与 Windows/Ubuntu CI artifact 验收 |
| 完整通信证据链 | 完成当前闭环 | P4 完成静态/virtual 绑定；P6 以同一契约支持 virtual/SocketCAN、精确过滤、锁证据、结构化 blocked 和双平台 artifact 验收 |
| 本地 Artifact Registry | 完成当前闭环 | P5a manifest、P5b 事后验证与 P5c Windows/Ubuntu 正常/篡改拒绝证据均通过 |
| 通信证据交付 | 完成 | P7 一条 CLI 交付 bundle/manifest/verification/receipt，Windows/Ubuntu CI 均通过 |
| 自包含证据胶囊 | 完成 | P8 按 manifest 白名单复制外部依赖，移出原 base 后离线复验及双平台 CI 通过 |
| 胶囊级完整性验证 | 完成 | P9 完整库存/哈希/契约/P5 依赖图复验与 receipt 篡改拒绝，Windows/Ubuntu CI 均通过 |
| 契约一致性与运行时前沿 | 完成 | P10 schema/loader parity、Python 3.14、Ruff/mypy 与依赖 inventory 三 job 验收通过 |
| OpenBSW 版本漂移复验 | 完成 | P11 固定 `dbd6e118..00052043`，patch 重放及 7/7、44/44、2572/2572 CTest 通过 |
| CI 职责拆分 | 完成 | P12 四类职责、七个实际 job，topology guard、本地回归与远端 run `34486148658` 全部通过 |
| 安装后 CLI 发行物 | 完成 | P13 wheel 隔离安装、checkout import 排除、console entrypoint 与核心 trace 通过；run `34529188770` 双平台验收成功 |
| 安装后胶囊消费者 | 完成 | P14 用无依赖隔离 wheel 在仓库外复验迁移胶囊；16/16 文件、7/7 artifact、3/3 dependency 通过，run `34581882908` 七 job 全绿 |
| 项目配置到验收报告 | 本地验收完成，远端待验收 | P15 `run-project`、5 项声明验收、HTML/JSON、静态失败阻止运行、后端阻断、输入快照及迁移复验 |
| Generate-Arxml 实际导出桥接 | 本地验收完成，远端待验收 | P16 固定生产者提交、实际 DOCX 导出三例、generation 门控、源码/输入/输出哈希与重放 |

## 已完成升级历史

### P14：Installed Evidence Capsule Consumer（2026-09-11）

- 新增 `scripts/check_installed_capsule_consumer.py`，在开发环境生成 P7 delivery/P8 capsule，迁移后由无项目依赖的隔离 wheel 从仓库外调用 `verify-evidence-capsule`。
- 消费者环境清除 `PYTHONPATH/PYTHONHOME`、拒绝 checkout import，并要求 CLI stdout 与落盘 verification 一致且状态为 `passed`。
- 新增闭合 `installed-capsule-consumer-0.1` schema；摘要固定 wheel、capsule report、consumer verification 三份 SHA-256，以及 16/16 文件、7/7 artifact、3/3 dependency 完整计数和七项有序 checks。
- 临时 wheel、producer、迁移胶囊、venv 和明细 verification 均在验收后删除；只保留摘要，不改变 P13 的发行边界。
- `core-contracts` Windows/Ubuntu matrix 新增消费者检查和独立 artifact upload；P12 topology guard 固定步骤归属，scoped mypy 扩展为七个 source。
- 本地验收：P14 7/7 checks 通过；全量 161 项中 159 项通过、2 项环境跳过；27 份 schema、45 份 schema-bound example、topology guard、Ruff、7-source mypy、compileall、`pip check` 与 whitespace gate 全部通过。
- 远程验收：GitHub Actions run `34581882908` 的七个实际 job 全部成功；Windows/Ubuntu 均完成 wheel 隔离安装、迁移胶囊复验和 P14 摘要上传，runtime/rejection 与 Python 3.14 currency 同时保持绿色。
- 详细设计：`docs/research/p14-installed-capsule-consumer-2026-09-11.md`。
- 边界：不上传或发布 wheel/capsule，不增加 CD、签名、attestation、远程身份、新协议、硬件或运行时依赖。
- 状态：完成并冻结。

### P13：Installed Distribution Smoke（2026-09-11）

- 新增 `scripts/check_installed_distribution.py`：从 `pyproject.toml` 构建唯一临时 wheel，在全新 venv 中以 `--no-deps --no-index` 安装，并从仓库外工作目录调用真实 `workbench` console script。
- smoke 清除 `PYTHONPATH/PYTHONHOME`，用 Python isolated mode 检查已安装 distribution name/version 和 module path；若从 checkout 导入则 fail closed。
- 核心消费者场景在无 CAN/UDS 可选依赖的环境中完成 `WindowPosition` 8 节点 trace，同时确认安装后命令目录含 capsule verifier。
- 新增闭合 `installed-distribution-smoke-0.1` schema，报告固定 wheel 文件名、字节数、SHA-256、版本、运行时和六项 checks；非空输出目录被拒绝。
- 临时 wheel 在验收后删除；CI 只上传 JSON smoke evidence，不把此里程碑伪装成发布或供应链身份证明。
- `core-contracts` 的 Windows/Ubuntu matrix 新增显式 smoke 与 artifact upload；P12 topology guard 固定该步骤归属，scoped mypy 纳入新脚本。
- 本地验收：已安装 wheel consumer smoke 6/6 checks 通过；全量 158 项中 156 项通过、2 项环境跳过；26 份 schema、45 份 schema-bound example、topology guard、Ruff、6-source mypy、compileall、`pip check` 与 whitespace gate 全部通过。
- 远程验收：GitHub Actions run `34529188770` 的七个实际 job 全部成功；Windows/Ubuntu 均完成 wheel build、isolated install、console trace 及 smoke evidence upload，runtime/rejection 回归与 Python 3.14 currency 同时保持绿色。
- 详细设计：`docs/research/p13-installed-distribution-smoke-2026-09-11.md`。
- 边界：不上传 wheel，不发布到 package index，不新增 CD、签名、attestation、远程下载、新汽车协议或硬件依赖。
- 状态：完成并冻结。

### P12：CI 职责拆分与拓扑门禁（2026-09-10）

- 将原 Windows/Ubuntu 单体 `test` matrix 拆为 `core-contracts`、`runtime-evidence`、`controlled-rejections`；保留独立 `runtime-currency`，共形成七个实际 job。
- runtime/rejection 两组均依赖 core 契约通过；拒绝组独立重建 chain、manifest、delivery 和 capsule，不从 runtime job 下载或共享可变工作目录。
- 原有 artifact 名称、CLI、schema 和四类受控失败保持不变；`continue-on-error` 只允许出现在 rejection job，且每个失败后仍有强制 checker。
- 新增 `scripts/check_ci_topology.py`，冻结 job 身份、依赖边、关键步骤归属、四个预期失败和禁止跨 job mutable artifact 下载；新增三项正/负例测试并接入 core job。
- 本地验证：topology guard 通过（4 job definitions、3 matrices、4 controlled failures）；拓扑测试 3/3；全量 156 项运行，154 项通过、2 项环境跳过；25 份 schema、45 份 schema-bound examples、Ruff、scoped mypy 和 whitespace gate 通过。
- 详细设计：`docs/research/p12-ci-job-topology-2026-09-10.md`。
- 边界：只改变 CI 编排，不改变业务结果、证据契约或平台能力；不增加 CD、attestation、新协议、OpenBSW adapter 或硬件依赖。
- 远端验收：GitHub Actions run `34486148658` 的七个实际 job 全部成功；两组 core 完成后才释放 runtime/rejection，四类预期非零退出均由后续 checker 与 artifact upload 闭环。
- 状态：完成。

### P11：OpenBSW Drift Revalidation（2026-09-10）

- 将 R3 固定基线 `dbd6e118a9aaa2db36e4461ce76655e8f285598d` 与 2026-09-09 上游 `000520435cf5f3b287de7aea1a4b52bd005e48ce` 比较；在 `/tmp/openbsw-p11` 使用干净 clone，未修改 `/home/dev/work/openbsw` 的历史工作树。
- 目标范围内 `cpp2can` 增加 MaskFilter/CAN-FD 构建接线，DoCAN 增加多种 addressing 与集成测试，referenceApp 增加 UDS/SOME-IP 能力；这些更新不触发 Workbench 新协议或 adapter 扩张。
- `CanDemoListener` 的 `0x123 -> 0x124` 回送、`DemoSystem` 每秒发送 `0x558`、POSIX `vcan0` 入口均保留；POSIX CanSystem 新增 classic/CAN-FD 配置分支。
- 历史 patch `0001-cpp2can-add-classic-canframe-invariant-test.patch` 通过 `git apply --check` 并无冲突重放；configure、定向构建和全量 748-action 构建通过。
- CTest：`CANFrameTest` 7/7、`cpp2canTest` 44/44、全量 `tests-posix-debug` 2572/2572 通过；旧基线分别为 7/7、34/34、1879/1879。
- Workbench 回归：153 项运行，151 项通过、2 项按环境跳过；25 份 schema、45 份 schema-bound example、Ruff 和 whitespace gate 通过。
- P11 文档提交 `07371c8` 推送后，GitHub Actions run `34483850808` 的 Ubuntu/Python 3.11、Windows/Python 3.11 和 Ubuntu/Python 3.14 runtime-currency 三个 job 全部通过；受控篡改、backend blocked 与 review rejection 的预期非零步骤均被后续检查器验证。
- 适用性修正：八字节 payload 只属于 classic/non-FD 构建；定义 `CPP2CAN_USE_64_BYTE_FRAMES` 时 `CANFrame::MAX_FRAME_LENGTH=64`。历史 patch 不改写，上游化前必须更新 rationale 并先按贡献流程沟通。
- 详细证据：`docs/research/openbsw-p11-drift-revalidation-2026-09-10.md`。
- 边界：没有引入 OpenBSW runtime adapter、DoIP/SOME-IP/Bazel/Rust、S32K148 硬件依赖或商业 AUTOSAR 工具；没有自动创建 issue/PR。
- 状态：完成；是否上游化继续保持人工触发。

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

### P4a：跨层通信方向契约（2026-09-08）

- `bsw-intent` schema 与 loader 升级到 0.2，根级显式声明 `local_ecu=BODY_ECU`，message 和 signal 逐项声明 `direction=tx|rx`；loader 保留 0.1 兼容读取。
- `validate-map` 从 DBC message sender 和 signal receiver 推导本地 ECU 方向，并新增 `DBC-MESSAGE-DIRECTION-MISMATCH`、`INTENT-SIGNAL-DIRECTION-MISMATCH`、`DBC-SENDER-MISMATCH` 和 `DBC-SIGNAL-RECEIVER-MISMATCH`。
- 校验结果新增 `communication_paths`，公开样例输出 BODY_ECU 的 `WindowPosition tx` 与 `RequestedDirection rx` 两条 `DBC Signal → SWC → COM → I-PDU → PduR → CanIf` 路径。
- PduR/CanIf 名称中的 Tx/Rx 后缀不参与判定；它们仍是显式引用标识，不被当作量产 ECUC 语义来源。
- 更新两份引用 BSW intent 的 review evaluation SHA-256，保持 R5 artifact binding fail-closed。
- 定向验证：BSW intent、DBC adapter、canonical contract 和 experiment 共 13 项通过；CLI `validate-map` 实际运行通过并输出 2 条路径、0 Finding。
- 回归：全量 107 项运行、2 项环境跳过；development 14 case/30 check 与 held-out 3 case/3 check 评测均通过且各项 accuracy/gate 为 `1.0`；76 份 JSON 可解析、Python compileall 和 whitespace check 通过。
- 边界：当前只绑定静态 DBC/intent 事实，尚未把路径 identity 与 virtual/SocketCAN runtime frame report 关联，不验证 vendor BSWMD、RTE API、handle ID 或硬件对象。
- 状态：完成；下一步 P4b 绑定静态路径与既有 CAN runtime evidence。

### P4b：静态—运行时完整通信证据链（2026-09-08）

- CAN lab 升级到 `can-lab-0.2`：保留 `WindowStatus.WindowPosition` BODY_ECU Tx round trip，新增 `WindowCommand.RequestedDirection` BODY_ECU Rx 场景；运行证据显式保存 message、direction、frame ID、payload 和 decoded signals。
- 新增 `run-communication-chain <dbc> <intent>`，同次编排静态 `validate-map`、virtual CAN lab 和 identity binding，输出静态报告、原始 runtime JSON/Markdown、组合 JSON/Markdown。
- 组合报告使用 `DBC message + signal` identity，并同时核对 direction 与 frame ID；静态失败、runtime lab 失败、identity 缺失、frame ID 或方向漂移均 fail closed 并生成独立 Finding。
- `communication-evidence-0.1` 固定 DBC、BSW intent 和实际 runtime JSON 的 SHA-256，保留 runtime applicability profile，不用路径、场景数组位置或对象名后缀替代 identity。
- 新增闭合 JSON schema 和四类绑定测试：双向正向绑定、runtime identity 缺失、frame/direction drift、静态引用失败。
- Windows/Ubuntu CI 新增完整通信链 smoke 和独立 `communication-chain-{OS}` artifact upload，不与既有 CAN lab 或 review evidence 混用输出目录。
- 定向验证：P4 intent/DBC/CAN/binding 共 14 项通过；实际 `run-communication-chain` 返回 `status=passed`、`bound_count=2/2`、`finding_count=0`，Tx/Rx frame ID 分别为 `0x100/0x200`。
- 首轮全量回归 111 项中有 2 项 R5 applicability mismatch gold 失败：CAN runner 已升级为 0.2，而 fixture 仍将 candidate 变异成同一个 0.2，因此不再构成 mismatch；改为显式 `can-lab-incompatible-fixture` 后两项定向 gate 恢复。
- 最终回归：全量 111 项通过、2 项环境跳过；全部 checked-in JSON 可解析，Python compileall、CLI help、communication schema/report 闭合字段和 whitespace check 通过。
- 提交 `e549f19` 推送后，GitHub Actions run `34299638224` 的 Windows `102303615374` 与 Ubuntu `102303615611` job 均成功；两个 job 的完整通信链运行和上传步骤均为 success。
- 远端已上传 `communication-chain-Windows`（3914 bytes）与 `communication-chain-Linux`（3879 bytes），同时保留两平台 core test、正常 review cohort 和受控 rejection artifacts，共 8 份且均未过期。
- 边界：本阶段完成公开样例在 `python-can virtual` 上的确定性静态—运行闭环，不证明 SocketCAN/OpenBSW/目标 ECU、RTE/COM API、控制器、电气总线或量产 ECUC。
- 状态：完成，Windows/Ubuntu 双平台验收通过。

### P5a：本地 Evidence Bundle Manifest（2026-09-09）

- 新增 `index-evidence <bundle> --producer <producer> --base <base> --manifest <path>`，只读扫描用户指定 bundle，并将 manifest 写在 bundle 外部。
- `evidence-bundle-manifest-0.1` 逐 artifact 记录 POSIX 相对 ID/path、media type、artifact type、schema version、size 和 SHA-256；顶层记录 bundle ID、producer、总文件数和总字节数。
- 对 JSON 报告的 `source_artifacts` 建立显式 `artifact/external` 依赖：bundle 内引用 artifact ID，外部来源必须位于 portable base；两者均在生成时核对声明 SHA-256。
- 拒绝空目录、符号链接、特殊文件、非对象 JSON、manifest 自引用、非法依赖、哈希不符和 portable base 路径逃逸。
- 新增闭合 schema 与五类测试，CI 在完整通信链之后生成并独立上传 `evidence-bundle-manifest-{OS}`。
- 定向验证：P5a 5 项通过，覆盖 5-file 通信 bundle 正向索引、manifest 自引用、符号链接、依赖 SHA mismatch 和 portable base 逃逸。
- 实际 CLI：通信链先返回 `bound_count=2/2`；随后 `index-evidence` 生成 5 artifact、8385 bytes 的 manifest，组合报告依赖 1 个 bundle 内 runtime JSON 与 2 个 external DBC/intent，清单不含临时目录或工作区绝对路径。
- 回归：全量 116 项通过、2 项环境跳过；全部 checked-in JSON 可解析，Python compileall、manifest/schema 闭合字段、portable relative path 和 whitespace check 通过。
- 提交 `767849d` 推送后，GitHub Actions run `34310607466` 的 Windows `102336312885` 与 Ubuntu `102336313013` job 均成功；两平台 `Index communication evidence bundle` 和上传步骤均为 success。
- 远端已上传 `evidence-bundle-manifest-Windows`（960 bytes）与 `evidence-bundle-manifest-Linux`（957 bytes），连同 communication chain、core test、review cohort/rejection evidence 共 10 份且均未过期。
- 边界：P5a 不复制/移动 artifact，不重新验证已有 manifest，不检测生成后的篡改，不下载远端文件，也不提供签名或 attestation；这些验证能力留给 P5b。
- 状态：完成，Windows/Ubuntu 双平台验收通过；下一步 P5b。

### P5b/P5c：事后完整性验证与受控篡改演练（2026-09-09）

- 新增 closed manifest loader，验证顶层/artifact/dependency 字段、portable path、排序唯一性、汇总计数、内部依赖引用和哈希自洽；非法 manifest 走 CLI error/退出码 1。
- 新增 `verify-evidence <bundle> <manifest> --base <base> --output <output>`；合法 manifest 下的 missing、unexpected、size/SHA tamper、unsafe file 和 internal/external dependency failure 生成闭合 JSON/Markdown，状态 failed/退出码 2。
- verification result 固定 manifest SHA-256，分别记录 expected/actual/verified artifact 及 dependency count，不写文件内容或绝对 bundle root。
- 新增受控演练脚本：复制正常通信 bundle，只向固定 runtime JSON 追加换行；检查器要求真实 CLI step outcome=failure、closed failed verification 和固定 `EVIDENCE-SIZE-MISMATCH`。
- Windows/Ubuntu CI 新增正常验证、受控拒绝检查及独立 `evidence-verification-normal/rejection-{OS}` uploads；不修改原通信 bundle 或 checked-in fixture。
- 新增 verification schema、tamper exercise schema，以及 unchanged、missing/unexpected/same-size tamper、external dependency drift、unsafe manifest 和 CI exercise 测试。
- 定向验证：P5a/P5b/P5c 共 11 项通过；unchanged、missing/unexpected/same-size tamper、external dependency drift、unsafe manifest 和受控 CLI failure 均覆盖。
- 实际正常 CLI：5/5 artifacts、3/3 dependencies verified，`status=passed`、0 Finding。
- 实际受控演练：追加换行后 `verify-evidence` 返回退出码 2，4/5 artifacts、2/3 dependencies verified；产生 `EVIDENCE-SIZE-MISMATCH` 与 `EVIDENCE-DEPENDENCY-FAILED`，检查摘要为 passed。
- 回归：全量 122 项通过、2 项环境跳过；全部 checked-in JSON 可解析，Python compileall、verification/tamper schema 闭合字段、whitespace check 通过。
- 提交 `52dcb47` 推送后，GitHub Actions run `34322744055` 的 Windows `102372887629` 与 Ubuntu `102372887826` job 均成功；正常验证、受控 CLI failure、拒绝检查和上传步骤全部为 success。
- 两平台各上传 `evidence-verification-normal`（719 bytes）和 `evidence-verification-rejection`（1358 bytes）；加上 manifest、communication、core test 与 review evidence，共 14 份 artifact 且均未过期。
- Actions 中 exit 2 annotation 来自预期的 evidence tamper step，exit 1 来自既有 review rejection step；两个 step 都由后续检查器验证，未被静默吞掉，workflow 保持绿色。
- 边界：只验证本地字节和 manifest 声明，不认证 producer、CI identity 或 repository ownership，不下载远端 artifact，不提供签名/attestation。
- 状态：完成，Windows/Ubuntu 双平台验收通过；P5 契约冻结。

### P6：后端无关完整通信证据链（2026-09-09）

- 新增 `can-communication-runtime-0.1`，以 `BusConfig` 选择 virtual 或 SocketCAN；保留独立 `run-can-lab` 0.2 契约，避免改变 R5 既有 producer/profile。
- runtime 只执行完整通信链实际需要的两条路径：BODY_ECU 发送 `WindowStatus/0x100` 与接收 `WindowCommand/0x200`；两端使用精确 ID filters。
- `communication-evidence-0.2` 增加 backend probe、isolation、reason 和 `blocked` 状态；接口缺失时两条静态路径保留为 blocked binding，0 Finding，不伪造运行观测。
- CLI 增加 `run-communication-chain --interface/--channel`；virtual 未指定 channel 时使用唯一隔离通道，SocketCAN 默认 `vcan0`。
- 新增无宿主变更的 Linux 入口 `run_socketcan_communication_chain.sh`，复用按 channel 的 `flock`，并在 passed/blocked 后自动建立、验证 P5 bundle。
- Windows/Ubuntu CI 新增固定不存在的 SocketCAN channel 演练：要求 CLI failure、平台相应的 `unsupported_platform/interface_missing`、blocked probe/binding、精确 filters，再索引和验证 blocked bundle 并独立上传。
- 定向测试 24 项通过；全量 127 项通过、2 项环境跳过；全部 checked-in JSON、bash 语法和 whitespace check 通过。
- 实际 virtual CLI：`status=passed`、2/2 路径绑定、0 Finding；7/7 artifacts 与 3/3 dependencies 验证通过。
- 实际 missing-SocketCAN CLI：退出码 3、`reason=interface_missing`、2 条 blocked binding、0 Finding；加入演练摘要后 8/8 artifacts 与 3/3 dependencies 验证通过。
- Linux 一键入口在当前 sandbox 以 `XDG_RUNTIME_DIR=/tmp` 复验：返回 `SOCKETCAN_COMMUNICATION_CHAIN_BLOCKED`/3，报告记录 `held_by_entrypoint`，其 7/7 artifact bundle 验证通过；未执行 `setup_vcan --apply` 或其他 host mutation。
- 提交 `95c92e2` 推送后，GitHub Actions run `34339864977` 的 Windows `102427860760` 与 Ubuntu `102427861199` job 均成功；正常通信链、blocked 演练、blocked bundle 索引/验证/上传及既有 P5 正常/篡改回归步骤全部为 success。
- 远端共上传 16 份未过期 artifact；P6 新增 `communication-chain-blocked-Windows`（7518 bytes）与 `communication-chain-blocked-Linux`（7497 bytes），升级后的正常链分别为 5203/5225 bytes。
- 边界：P6 证明所选 python-can backend 上的过滤式应用层帧交换或可审计的环境阻断，不证明真实 ECU、RTE/COM API、CAN 控制器、电气总线、硬实时或量产 ECUC。
- 状态：完成，Windows/Ubuntu 双平台验收通过；P6 契约冻结。

### P7：一键通信证据交付（2026-09-09）

- 新增 `run-communication-delivery <dbc> <intent>`，在一次本地调用中顺序执行 P6 communication chain、P5 manifest index 和 P5 verification。
- 交付目录固定为 `bundle/`、`manifest.json`、`verification/` 和 `communication-evidence-delivery.{json,md}`；receipt 不写绝对工作区路径。
- 新增闭合 `communication-evidence-delivery-0.1` schema，receipt 同时记录 chain/integrity 状态、artifact/dependency 验证计数以及 manifest/verification SHA-256。
- 状态传播保留 `passed/failed/blocked`；SocketCAN 不可用时业务仍为 `blocked`，但可完整交付的阻断证据仍为 `integrity_status=passed`。
- 拒绝符号链接、非目录或非空输出，不自动删除用户文件，避免重跑时将 stale artifact 混入新 manifest。
- Linux SocketCAN 入口改为调用新交付命令，保留 host probe、channel `flock` 和无 host mutation 边界；CI 新增独立 `communication-delivery-{OS}` artifact。
- 定向验证：19 项通过，覆盖 virtual 7/7 artifact、3/3 dependency 正向交付、failed/blocked 状态传播、非空目录拒绝及 P5/P6 回归；全量 131 项通过、2 项环境跳过。
- 提交 `e5e4503` 推送后，GitHub Actions run `34365685454` 的 Ubuntu job `102513662936` 与 Windows job `102513663311` 均成功；两平台的一键交付和 `communication-delivery-{OS}` 上传步骤均为 success。
- 边界：receipt 是单次本地编排和字节绑定证据，不是签名、attestation、远程 provenance、producer 身份认证或目标 ECU 证明。
- 状态：完成，Windows/Ubuntu 双平台验收通过；P7 契约冻结。

### P8：自包含 Evidence Capsule（2026-09-09）

- 新增 `export-evidence-capsule <delivery> --base <base> --output <capsule>`，接受 P7 交付目录，不修改已冻结的 P5 manifest 或 P7 receipt 契约。
- 导出前交叉验证 receipt/manifest/source verification SHA-256、计数和 bundle 内 communication chain 状态，并用原 portable base 重跑一次 P5 verifier。
- 导出只复制 manifest 白名单中的 bundle artifact 和去重后 external dependency；拒绝路径逃逸、布局冲突、符号链接、哈希漂移、输出重叠和非空输出。
- capsule 内保存原 bundle、manifest、JSON receipt/source verification、外部输入及新的 offline verification；`evidence-capsule-0.1` report 固定四份核心文件哈希和外部依赖列表。
- capsule export 自身的 `status=passed` 与原交付 `passed/failed/blocked` 分开；已验证的 blocked 环境证据也可完整搬运，不被改写为业务成功。
- Linux SocketCAN 入口在 passed/blocked 后自动导出 capsule；Windows/Ubuntu CI 新增 export、目录迁移、以迁移后根目录为 base 离线复验和独立 artifact 上传。
- 定向验证：P8 专属 5 项及 P5/P7/Linux 入口回归通过；全量 136 项通过、2 项环境跳过；JSON、compileall、Bash 语法和 whitespace 检查通过。
- 实际 CLI：将 capsule 导出至原工作区外的 `/tmp` 目录后，只以 capsule 根目录为 base 复验，7/7 artifacts、3/3 dependencies、0 Finding。
- 提交 `f023bf3` 推送后，GitHub Actions run `34368118499` 的 Ubuntu job `102522024785` 与 Windows job `102522025084` 均成功；两平台 export、relocate、offline verify 及 `evidence-capsule-{OS}` 上传步骤全部通过。
- 边界：capsule 是目录结构和本地字节搬运契约，不是压缩归档、签名、attestation、producer 身份或供应链认证。
- 状态：完成，Windows/Ubuntu 双平台验收通过；P8 契约冻结。

### P9：Evidence Capsule 事后完整性验证（2026-09-10）

- 新增 `verify-evidence-capsule <capsule> --output <output>` 和闭合 `evidence-capsule-verification-0.1`，从 P8 report 重建完整预期文件库存。
- 胶囊级 verifier 验证 manifest、receipt、source/offline verification、可重建 Markdown、全部 bundle artifacts 和去重 external dependencies，并拒绝 missing、unexpected、SHA-256 drift、special file 和 symlink。
- 交叉检查 capsule report、P7 receipt、P5 manifest 的 bundle ID、业务状态、哈希和计数；再复用 P5 verifier 验证 bundle/dependency graph。
- 新增受控 receipt 篡改演练：仅向 capsule 顶层 `communication-evidence-delivery.json` 追加换行，要求 CLI 退出码 2、`status=failed` 且精确产生 `CAPSULE-SHA256-MISMATCH`。
- CI 在 P8 目录迁移后运行完整 capsule verifier，正常与受控拒绝证据分开上传；Linux SocketCAN 入口在导出后也自动执行 P9 verifier。
- 定向验证 7 项通过，覆盖 16/16 files 正向验证、external tamper、receipt missing + unexpected file、Markdown tamper、symlink 和受控 CLI failure；全量 143 项通过、2 项环境跳过。
- 实际受控演练：未改动 bundle 或 external dependency，P9 返回 15/16 files verified、7/7 artifacts、3/3 dependencies 和唯一 receipt hash Finding，证明胶囊级检查与 P5 内容检查职责分离。
- 提交 `974b1b5` 推送后，GitHub Actions run `34436609789` 的 Ubuntu job `102742875545` 与 Windows job `102742875415` 均成功；两平台完整库存验证、receipt 篡改拒绝检查及正常/拒绝 artifact 上传步骤全部通过。
- 边界：P9 验证胶囊内部字节一致性，不提供胶囊之外的信任根、签名、attestation、身份或供应链来源认证。
- 状态：完成，Windows/Ubuntu 双平台验收通过；P9 契约冻结。

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

### R4p：冗余修复与中断写入（2026-08-31）

- 新增 `docs/research/dtc-redundancy-repair-interrupted-write-research-2026-08-31.md`，核对 AUTOSAR NvM loss-of-redundancy、损坏副本恢复、CRC、写验证和 retry 边界。
- 明确 generation、scrub 时机和 commit marker 不是引用规范定义的算法，必须保持为 Workbench 确定性策略。
- 定义 committed/staged 副本选择规则、幂等 repair、无有效源时拒绝 repair，以及中断普通写入/修复不得破坏 last-good 源副本的约束。
- 定义 3 类最小验收场景：普通写入在 commit 前中断、降级恢复后成功 repair 且二次 reset 无冗余告警、repair 在 commit 前中断仍可从原始源副本恢复。
- 新增 `dtc_redundancy_repair.py`、CLI `run-dtc-redundancy-repair-lab` 和 JSON/Markdown 报告；未 committed 副本即使 checksum 有效也不参与仲裁。
- 中断普通写入后选择旧但 committed 的 B；成功 repair 使 A/B 状态和 generation 一致，重复 repair 为 no-op，二次 reset 不再报 loss-of-redundancy。
- repair 在 commit 前中断后，未 committed 的 B 被拒绝，原始 committed A 仍可恢复；无已选 committed 源时 repair 结构化拒绝。
- repair lab 25/25 通过，包含 6 个预期 Finding；全量回归 64 项运行、2 项环境跳过。
- 边界：不模拟 MemIf/Fee/Ea job、flash 粒度、擦除、磨损、并发或真实断电。
- 状态：完成。

### R5a：AI 工程审查契约调研（2026-08-31）

- 盘点现有 Artifact/Finding/Trace/TestResult 和各 lab 报告，确认 artifact envelope 未统一、Finding location 非结构化、TestResult findings schema 与实际内联对象不一致、缺少 citation/coverage/refusal 对象四类契约缺口。
- 新增 `docs/research/ai-engineering-review-contract-research-2026-08-31.md`，定义 ReviewRequest、EvidenceUnit、Citation 和 ReviewResult 的最小字段与验证规则。
- coverage 使用调用方显式定义的 required checks 计算，不允许依据模型自生成 claims 缩小分母。
- 定义 `answered/partial/refused` 状态和 missing artifact、hash mismatch、confidentiality denied、no evidence、invalid citation、evidence conflict、coverage below threshold 稳定拒答原因。
- 确定性 Finding 可以是问题的直接证据，但审查结果不得矛盾、降级或关闭 Finding；未知 Trace 节点和证据冲突必须显式呈现。
- 决策：R5b 先实现无第三方依赖的本地 JSON Pointer 归一化、词法检索、引用验证、coverage 和拒答，不先做自然语言生成、embedding、向量库或 UI。
- 状态：调研完成，R5b 已实现该最小竖切。

### R5b：本地 JSON retrieval-only 审查竖切（2026-08-31）

- 新增 `review.py` 和 CLI `run-review`；review request 显式声明 artifact registry/scope、confidentiality policy、required checks 和 minimum coverage。
- 新增 ReviewRequest、EvidenceUnit、Citation 和 ReviewResult 四份 schema；JSON 标量叶子转为绑定 artifact/source SHA-256、JSON Pointer 和 content SHA-256 的 EvidenceUnit，并归档到 `evidence-units.json`。
- 词法检索对调用方显式 terms 做确定性覆盖，使用稳定 tie-break 贪心选择 citation；不使用 LLM、embedding 或向量库。
- 公开样例对 DTC repair Finding 和成功修复状态达到 coverage `1.0`，产生 4 个可重新解析验证的 JSON Pointer citations。
- 覆盖 `answered/partial/refused`，missing artifact、confidentiality denied、expected hash mismatch、no evidence，以及源文件或 citation 元数据修改后校验失效。
- 审查结果原样保留 Finding code/severity/message/source/location/status，不降级或改写确定性结果。
- 回归：全量 70 项运行、2 项环境跳过；公开 CLI 样例为 `answered`，citation validation 4/4 通过。
- 边界：当前只支持本地 JSON 和调用方词法 terms；不宣称语义理解、自然语言答案质量、生产权限隔离或安全证明。
- 状态：完成。

### R5c：多 artifact 冲突、Markdown citation 与 evaluation 调研（2026-08-31）

- 新增 `docs/research/ai-engineering-review-conflict-markdown-evaluation-research-2026-08-31.md`，核对 W3C Web Annotation/PROV、CommonMark、GitHub line permalink、FEVER、TREC/BEIR 和 NIST relevance judgment 边界。
- 明确词法重叠只能召回候选，不能判定冲突；只有调用方通过同一 `claim_key`、适用范围、显式 locator 和 `equals/all-equal` operator 声明可比观测时才执行确定性比较。
- 定义 `blocked > conflicted > supported > unsupported` 优先级；required check 冲突必须 `refused` 并引用双方，不能被 coverage 平均或 Finding severity 覆盖。
- 定义 Markdown `line-range` 为一基闭区间；原始 source SHA-256 与 LF 规范化片段 SHA-256 双重绑定，保留缩进、尾随空格和 tab，修改后 fail closed。
- 定义至少十案例的本地 gold evaluation manifest，以及 status/check accuracy、conflict recall、false conflict、citation validity/precision/evidence-set recall、refusal/Finding exact match 和三次运行 repeatability gate。
- 决策：R5d 实现 Markdown、显式 assertion 和依赖无关 evaluator；继续不引入外部 LLM、embedding、向量库、模糊引用修复或 source-priority 猜测。
- 状态：调研完成，实现待开始。

### R5d：多 artifact 冲突、Markdown citation 与 gold evaluation（2026-08-31）

- `review.py` 保持 `review-request-0.1` JSON 词法路径兼容，并新增 `review-request-0.2` assertion；显式 `claim_key`、locator 与 `equals/all-equal` 是执行跨 artifact 比较的唯一入口。
- 新增本地 Markdown 非空物理行 EvidenceUnit 与一基闭区间 `line-range`；source 原始字节和 LF 规范化片段分别绑定 SHA-256，CR/LF/CRLF 可确定性解析。
- required observations 一致时 supported，不一致时 conflicted；冲突结果 `refused`，双方 citation 分别记录 `supports/contradicts`，citation validator 会重新计算 relation 并拒绝元数据篡改。
- 新增 `review_eval.py`、CLI `run-review-eval`、manifest/result schema，以及 10 个使用 expected SHA-256 固定 fixture 的 gold 案例；每个案例运行三次并剔除 `run_id/started_at` 后比较完整结果。
- 案例覆盖单 JSON、Markdown、双 artifact 一致/冲突、相似但不可比、partial、missing、denied、非法 line range 和 all-equal repeatability。
- 评测：10/10 case 通过；status/check/conflict recall/citation validity/citation precision/evidence-set recall/refusal/Finding/repeatability 全部 `1.0`，false conflict `0`。
- 回归：全量 76 项运行、2 项环境跳过；30 份 schema/example JSON 可解析，Python compileall 和 diff check 通过。
- 边界：当前 gold set 很小且以合成/repair 证据为主；不宣称自然语言语义理解、跨版本适用性推断、来源权威裁决或量产评审准确率。
- 状态：完成。

### R5e：30-check 汽车工程跨域评测（2026-08-31）

- 保留 R5d 的 10 个 core 案例与 11 个 checks，新增 4 个直接引用仓库公开工程 artifact 的案例，不复制输入文件。
- DBC 域通过 DBC-derived `canonical_contract.json` 验证 AUTOSAR 版本、信号方向/范围、枚举和公开样例状态 5 项；review 内核仍不直接解析 `.dbc`。
- CAN 域通过 `bsw_intent.json` 验证两个 CAN ID、DLC、byte order 和 bit length 5 项；UDS 域通过 `uds_intent.json` 验证 addressing、request/response ID、VIN 长度和 NRC 5 项。
- DTC 域通过 `dtc_intent.json` 验证 status mask、failure/aging threshold 和 clear persistence 4 项；新增 19 项后总计恰好 30 checks。
- evaluator 升级到 `review-evaluation-0.2`：manifest/case 新增 `domain`，result 新增 `check_count`、`domain_check_counts` 和 `domain_check_accuracy`；loader 继续接受 `0.1` 并默认 legacy case 为 `core`。
- 所有 17 个实际存在的 evaluation source reference 均携带并由测试复核 `expected_sha256`；缺失 artifact 案例保持未绑定源，用于拒答验证。
- 评测：14/14 case、30/30 check 通过；`core=11/dbc=5/can=5/uds=5/dtc=4`，五域准确率均 `1.0`；全部原有指标仍为 `1.0`，false conflict `0`。
- 回归：全量 78 项运行、2 项环境跳过；34 份 schema/example JSON 可解析，Python compileall、R5e whitespace 和 diff check 通过。
- 边界：新增 19 项使用调用方显式 assertion 和已知 JSON Pointer，只证明当前公开 artifact 的确定性回归，不证明未知问题检索、直接 DBC 审查或量产语义正确性。
- 状态：完成。

### R5f：运行时报告与 held-out negative evaluation（2026-08-31）

- evaluator 升级到 `review-evaluation-0.3`：case 新增 `split`，result 新增 `split_check_counts/accuracy`，同时保持 `0.1/0.2` manifest 兼容并默认归入 `development`。
- 新增仅允许 `can-lab`、`uds-lab`、`dtc-lifecycle` 的进程内 producer；不接受 shell 或任意命令。runner 报告生成后，evaluator 将报告绝对路径和实际 SHA-256 注入模板请求，再执行三次 review。
- runtime manifest 分别从真实生成的 `can-runtime-report.json`、`uds-lab-report.json` 和 `dtc-lifecycle-report.json` 验证 CAN round-trip、UDS VIN decode 与 DTC confirmed state，并精确检查 UDS Finding 保真。
- 独立 held-out negative manifest 不并入 30-check development baseline，覆盖错误 CAN ID、未知 UDS JSON Pointer 和错误 DTC threshold；三个案例均必须安全拒答。
- 评测：runtime 3/3 case、3/3 check 通过；held-out negative 3/3 case、3/3 check 通过；全部比例指标均为 `1.0`，false conflict `0`。
- 回归：全量 81 项运行、2 项环境跳过；47 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：producer 仍使用明确 runner/input 白名单，gold 仍是调用方给定 pointer；本阶段不推断动态时间字段、不自动发现 claim，也不宣称未知自然语言问题能力。
- 状态：完成。

### R5g：跨运行 drift/conflict evaluation（2026-09-01）

- evaluator 升级到 `review-evaluation-0.4`，新增 `cross-run` split；producer 可在同一 case 中生成两份独立报告，每份报告单独记录路径、状态和 SHA-256。
- CAN、UDS、DTC 各新增一项 `all-equal` 跨运行稳定字段检查。两份原始报告哈希均不同，但 round-trip status、decoded VIN 和 confirmed state 一致，因此不会产生 false conflict。
- 新增受控 CAN drift case：仅允许在 `can-lab` allowlist 中将第二份报告 `/scenarios/0/status` 改为 `failed`，review 必须判定 `conflicted`、拒答并引用双方。
- mutation 按 runner/pointer 白名单校验，不能修改 `run_id` 或其他任意字段；manifest 试图越权时在执行 runner 前失败。
- 配对请求若观察 `run_id`、`started_at`、`duration_ms` 或任意 `channel` 字段，会以 “dynamic field is not comparable” 在物化前失败，避免把正常运行差异计为工程冲突。
- 评测：cross-run 4/4 case、4/4 check 通过；conflict recall、citation validity/precision/evidence recall、Finding preservation 和 repeatability 均为 `1.0`，false conflict `0`。
- 回归：全量 84 项运行、2 项环境跳过；53 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：当前稳定字段和动态字段分类是显式 allowlist，不自动推断 variant、software/calibration version 或 backend 适用性，也不提供通用 JSON mutation。
- 状态：完成。

### R5h：跨运行 applicability profile 与三域 drift catalog（2026-09-01）

- 新增 `review-request-0.3` / `review-result-0.3`；每个 assertion observation 必须显式记录 `variant`、`software_version`、`calibration_version` 和 `backend`，四字段均为非空字符串。
- 多观测 profile 完全一致时才解析 locator 并执行 `equals/all-equal`；任一字段不同会将 check 标记为 `blocked`，返回 `REVIEW-APPLICABILITY-MISMATCH`，且不生成数值 citation。
- citation validator 同样拒绝 applicability 不一致 assertion 的伪造 citation，避免只在首次 review 路径设门禁。
- evaluator 升级到 `review-evaluation-0.5`，保留 0.1-0.4 manifest 兼容；cross-run 请求升级到 0.3，原有稳定/冲突行为保持不变。
- drift catalog 从 CAN 扩展到 CAN/UDS/DTC：分别对白名单稳定字段 round-trip status、decoded VIN 和 confirmed state 注入第二次运行 drift，三者均必须冲突、拒答并引用双方。
- 新增 software version 不一致的 applicability negative case；即使两份 CAN 报告值相同也必须阻断，不能产生 false agreement。
- 评测：cross-run 7/7 case、7/7 check 通过；conflict recall、citation validity/precision/evidence recall、Finding preservation 和 repeatability 均为 `1.0`，false conflict `0`。
- 回归：全量 86 项运行、2 项环境跳过；56 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：profile 当前由 request 调用方声明，尚未绑定 runner 报告或独立 manifest 的哈希证据；版本字符串也不做 SemVer 排序或兼容性推断。
- 状态：完成。

### R5i：artifact-bound applicability profile（2026-09-01）

- 新增 `applicability.py`，以有效输入文件名和内容 SHA-256 的规范化列表生成 calibration identity；绝对路径不参与哈希，因此同内容迁移目录不会产生假差异，内容变化必然改变 identity。
- CAN、UDS 和 DTC lifecycle runner 在报告内生成完整 `applicability_profile`；variant 来自 DBC 名或 intent ECU，software version 来自 runner contract，backend 来自实际执行路径。
- 新增 `review-request-0.4` / `review-result-0.4`；observation 使用 JSON Pointer `applicability_locator` 从各自 artifact 解析 profile，不再接受调用方内嵌 profile。
- profile locator 缺失、不是 JSON Pointer、目标不是完整四字段对象或 artifact 不是 JSON 时 fail closed，返回 `REVIEW-APPLICABILITY-INVALID`；完整 profile 不同仍返回 `REVIEW-APPLICABILITY-MISMATCH`。
- evaluator 升级到 `review-evaluation-0.6`；每份 producer report evidence 同时记录 source SHA-256 和实际 profile，并验证 runner 输出 profile 结构。
- applicability negative case 改为受控修改第二份 CAN 报告内 `/applicability_profile/software_version`，模拟真实跨 runner contract 比较；即使稳定字段相同也必须阻断且无 citation。
- 评测：cross-run 7/7 case、7/7 check 继续通过；三域稳定/drift、profile mismatch、Finding preservation、citation 和 repeatability gate 均保持通过。
- 回归：全量 88 项运行、2 项环境跳过；56 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：software version 当前是 runner contract 字符串，不从构建系统或 Git provenance 自动获取；calibration identity 表示有效输入内容集合，不推断 SemVer 兼容性或标定继承关系。
- 状态：完成。

### R5j：baseline/candidate cohort 与 drift catalog（2026-09-01）

- 新增 `review-request-0.5` / `review-result-0.5`；cohort assertion 只接受 `all-equal`，要求恰好一个 `baseline` 和至少一个 `candidate`，baseline 不依赖 observation 数组顺序。
- 每个 candidate 单独解析 artifact-bound applicability：一致时与 baseline 比较并标记 `stable/drifted`，profile 缺失或不同则标记 `not-comparable`，不会抹去其他 candidate 已验证的结果。
- ReviewResult 新增结构化 `drift_catalog`，记录 check/claim、baseline、candidate、状态和 citation IDs；Markdown 同步输出候选表。
- citation validator 新增 catalog 完整性门禁：每个 candidate 必须恰好出现一次，`not-comparable` 不得引用数值，stable/drifted 必须有 baseline/candidate 两个有效引用且 relation 与状态一致。
- evaluator 升级到 `review-evaluation-0.7`，producer 支持恰好三次运行并通用替换 `${producer_report_1..3}`；旧 schema 不允许三运行，双运行路径保持兼容。
- 新增独立 `cohort` split 和两项 CAN gold case：baseline + stable candidate + drift candidate，以及 baseline + stable candidate + software-version mismatch candidate。
- drift catalog evaluation 使用精确结构比对并新增 `drift_catalog_accuracy` gate；2/2 case、2/2 check、4/4 candidate judgment 全部通过。
- 回归：全量 92 项运行、2 项环境跳过；59 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：当前 cohort 固定最多三次运行且只覆盖 CAN；不进行趋势分析、统计显著性判断、版本兼容性推断或自动 baseline 选择。
- 状态：完成。

### R5k：CAN/UDS/DTC 跨域 cohort 汇总（2026-09-01）

- 保持 `review-request-0.5` 的唯一 baseline、逐 candidate 判断和三运行上限，将 cohort 从 CAN 扩展到 UDS decoded VIN 与 DTC confirmed state。
- 新增 UDS/DTC stable+drift gold case；第三次运行只修改各 producer 白名单稳定字段，必须逐候选得到 `stable`、`drifted`，拒答并引用 baseline 与对应 candidate。
- evaluator 升级到 `review-evaluation-0.8` / result 0.8，新增全局及按 domain 的 drift 状态计数，并在 Markdown 输出跨域摘要表。
- 评测：4/4 case、4/4 check、8/8 candidate judgment 通过；全局计数为 stable 4、drifted 3、not-comparable 1，CAN/UDS/DTC 分域计数与 gold 完全一致；Finding preservation 与全部既有 gate 均为 `1.0`。
- 回归：全量 92 项运行、2 项环境跳过；61 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：汇总是确定性样例覆盖计数，不进行趋势分析、统计显著性判断、版本兼容性推断或自动 baseline 选择；当前 evaluator 仍负责现场运行 producer。
- 状态：完成。

### R5l：固定哈希 CI/外部报告 cohort 导入（2026-09-03）

- evaluator 升级到 `review-evaluation-0.9` / result 0.9；case 可声明 1～3 个 `external_reports`，并通过 `${external_report_1..3}` 装配既有报告。
- `external_reports` 与 `producer` 明确互斥；外部路径只作为本地只读输入，不执行 shell、下载报告或调用 runner，也不允许 mutation。
- 每份报告在 review 前先验证 manifest 固定的 64 位小写 SHA-256、UTF-8 JSON 和完整四字段 `applicability_profile`；任一不符立即 fail closed。
- materialized request 使用解析后的绝对路径和实际 SHA-256；evaluation result 归档每份来源相对路径、已验证哈希、profile 和 `verified` 状态，且不会创建 `producer/` 输出目录。
- 新增 CAN CI baseline + stable candidate + drift candidate 固定 fixture；1/1 case、1/1 check、2/2 candidate judgment 通过，drift catalog 为 stable 1、drifted 1、not-comparable 0。
- 回归：全量 96 项通过、2 项环境跳过；66 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：首个固定报告案例只覆盖 CAN；SHA-256 证明本地字节未偏离 manifest，不证明报告由指定 CI 身份产生，也不是签名、远端下载或供应链证明。
- 状态：完成。

### R5m：固定报告跨域与 CI provenance（2026-09-04）

- evaluator 升级到 `review-evaluation-1.0` / result 1.0；外部固定报告 cohort 从 CAN 扩展到 CAN、UDS decoded VIN 和 DTC confirmed state 三域。
- 新增 6 份 UDS/DTC baseline、stable candidate、drift candidate fixture，与已有 CAN fixture 共同形成 3 case、9 report 的本地固定 cohort。
- 1.0 报告必须携带非空 provider、repository、run ID、job ID，以及 40/64 位小写十六进制 commit SHA；缺失、字段越界或非法 SHA 均 fail closed。
- evaluation result 在已验证 source SHA-256 和 applicability profile 旁归档 `ci_provenance.status=hash-bound`；该状态表示声明存在于被固定的报告字节中，不表示 provider 身份已认证。
- 三域各得到 stable 1、drifted 1、not-comparable 0，引用、冲突、drift catalog 与 repeatability gate 全部通过，且不创建 `producer/` 目录。
- 回归：全量 97 项通过、2 项环境跳过；74 份 schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：fixture provenance 是公开合成审计数据；当前不下载 CI artifact、不查询 provider API、不校验 workflow identity、签名或透明日志，也不将声明相等视为供应链证明。
- 状态：完成。

### R5n：显式 provenance expectation（2026-09-04）

- evaluator 升级到 `review-evaluation-1.1` / result 1.1；每个 external report 必须由 manifest 独立声明 repository、job ID 和 commit SHA expectation。
- 先验证固定报告 SHA-256 与报告内 `ci_provenance`，再逐字段匹配调用方 expectation；缺失、非法或任一字段不符均在生成 materialized request 和执行 review 前 fail closed。
- result 分别记录 `ci_provenance.status=hash-bound` 与 `provenance_expectation.status=matched`，不把报告字节绑定和调用方意图匹配混为同一种信任结论。
- CAN/UDS/DTC 三域共 9 份固定报告均显式声明 expectation；正向 cohort 维持 stable 3、drifted 3、not-comparable 0，repository/job/commit 三类负例均确认不会生成 materialized request。
- 定向回归：`tests.test_review_eval` 19 项通过；全量 100 项通过、2 项环境跳过；schema/example JSON 可解析，Python compileall、whitespace 和 diff check 通过。
- 边界：仍不认证 provider 身份、不查询 CI API、不下载远端 artifact、不验证签名、attestation、透明日志或 repository ownership；`matched` 只代表本地 manifest 声明与已哈希固定报告中的声明相等。
- 状态：完成。

### R5o：cohort provenance policy（2026-09-04）

- evaluator 升级到 `review-evaluation-1.2` / result 1.2；external cohort case 必须声明唯一非空 repository 与 `allowed_job_ids` 白名单。
- 在报告 SHA-256、报告内 provenance 和逐报告 expectation 全部通过后执行 cohort policy；跨 repository 或 job 不在白名单时，在 artifact substitution、materialized request 和 review 运行前 fail closed。
- result 在逐报告 `hash-bound`、`matched` 证据之外，以 `provenance_policy.status=enforced` 归档实际生效的 repository 和 job allowlist。
- CAN/UDS/DTC 三域 policy 分别覆盖各自 baseline、stable candidate 和 drift candidate job；正向 cohort 仍为 stable 3、drifted 3、not-comparable 0。
- 负例覆盖 policy 缺失、空 job list、重复 job、跨仓库和越权 job；1.0 无 expectation/policy 与 1.1 有 expectation/无 policy 两种旧 manifest 均可继续加载。
- 定向回归：`tests.test_review_eval` 21 项通过；全量 102 项通过、2 项环境跳过；74 份 schema/example JSON 可解析，Python compileall、CLI 实际 cohort、whitespace 和 diff check 通过。
- 边界：policy 仅做精确本地 allowlist，不支持 wildcard、repository alias、branch/workflow/provider policy、commit ancestry、签名或 attestation，不声称供应链身份认证。
- 状态：完成。

### R5p：preflight rejection evidence（2026-09-06）

- evaluator 升级到 `review-evaluation-1.3` / result 1.3；外部报告预检失败仍抛出异常并保持 CLI 非零退出，同时在评测根目录生成 `review-evaluation-rejection.json`。
- rejection artifact 使用独立闭合 schema，仅记录 evaluation/case ID、时间、固定 phase、报告序号、stage、稳定 reason code 和可选字段名。
- 拒绝件不写报告路径、期望/实际哈希、provenance/policy 值、request/report 内容或 artifact registry，也不生成 `materialized-request.json` 或将拒绝计入评测分数。
- 负例覆盖 SHA-256 integrity、报告 provenance shape、调用方 expectation 和 cohort policy 四类拒绝；1.0、1.1、1.2 manifest 继续可加载。
- GitHub Actions 在 Windows/Ubuntu 双平台运行固定报告 cohort，并通过 `always()` 上传输出目录，因此正常评测或 preflight rejection 都可留存。
- 定向回归：`tests.test_review_eval` 21 项通过；全量 102 项通过、2 项环境跳过；75 份 schema/example JSON 可解析，Python compileall、CLI 实际 cohort、whitespace 和 diff check 通过。
- 边界：rejection artifact 只是本地失败可观测性证据，不是部分 review result，不认证被拒报告；manifest 结构错误及外部报告预检之外的失败仍只走原异常路径。
- 状态：完成。

### R5q：CI rejection contract 演练（2026-09-07）

- 新增 `scripts/review_rejection_exercise.py`，`prepare` 将固定 cohort 的路径解析为绝对路径并只把首份报告 SHA-256 改为全零，形成确定、可移植且不修改 checked-in fixture 的拒绝输入。
- `check` 要求 GitHub Actions 记录的 CLI step outcome 必须为 `failure`，并校验 rejection artifact 的闭合字段、`sha256-mismatch/integrity/report 1` 原因、无敏感 provenance/policy 字段、无 materialized request 和正式 evaluation result。
- 校验通过后生成独立 `review-rejection-exercise.json`，明确记录 CLI failure 已被观察和两类旁路产物均不存在；该摘要不改变 evaluator 的 rejection schema。
- GitHub Actions Windows/Ubuntu matrix 新增 prepare、`continue-on-error` 的真实 CLI 拒绝、强制 check 和 `always()` artifact upload；正常 cohort 与拒绝演练使用独立 artifact 名称和目录。
- 新增 `tests/test_review_rejection_exercise.py`，覆盖 staged manifest、真实 evaluator preflight failure、拒绝证据检查和“CLI 意外成功必须使检查失败”。
- 本地定向验证：`tests.test_review_rejection_exercise tests.test_review_eval` 共 23 项通过。
- 本地命令链验证：受控 CLI 返回退出码 1，检查摘要为 `status=passed`、`cli_outcome=failure`、`reason_code=sha256-mismatch`，且 request/result 均未物化。
- 首次远端 run `34074617940` 在 Ubuntu `Run core tests` 提前失败；原因是历史 CI 只安装 `.[can]`，而全量测试已经包含需要 `can-isotp`/`udsoncan` 的诊断运行用例。matrix 默认 fail-fast 同时取消了 Windows，拒绝演练没有获得执行机会。
- CI 基线随即修正为安装 `.[diag]`（包含 CAN 与诊断依赖）并设置 `fail-fast: false`；拒绝检查只在受控 CLI step 实际执行后运行，避免更早的无关失败被二次伪装为 rejection contract failure。
- 第二次远端 run `34079650707` 中 Ubuntu 全链通过并上传正常/rejection 两类 artifact；Windows 依赖安装成功但 core tests 仍有一个平台差异失败。为避免公开仓库匿名 API 只能看到退出码而看不到 test ID，新增 CI test summary artifact 和 GitHub error annotation，下一次运行将直接暴露失败用例并保留结构化摘要。
- CI test runner 显式把仓库根加入 `sys.path`，保持与原 `python -m unittest` 的模块发现语义一致；否则从 `scripts/` 直接启动时会使测试无法导入同目录包。
- 第三次远端 run `34089594966` 的 annotations 定位出两类 Windows 基线差异：checkout 的 CRLF 转换破坏按字节固定的 JSON/Markdown SHA-256；两个 SocketCAN blocked 测试把 Linux `interface_missing` 错当成所有平台的唯一结果。
- 新增 `.gitattributes` 固定文本 checkout 为 LF，保持跨平台 artifact hash；UDS 测试现在在非 Linux 明确期待 `unsupported_platform`。同时把 checkout/setup-python 升级到 Node 24 major；run #10 确认 `upload-artifact@v5` 仍为 Node 20 后继续升级至官方 v7。
- 最终业务验收 run `34093452072`（#10）整体成功，Ubuntu/Windows 两个 job 均完成；六个 artifact 均上传：`core-test-results-{Linux,Windows}`、`review-external-cohort-{Linux,Windows}`、`review-external-rejection-{Linux,Windows}`。
- run #10 的两个受控拒绝 step 各自按预期产生退出码 1，后续 verify step 通过，因此 job 与 workflow 保持绿色；这同时证明失败没有被静默吞掉，且 rejection evidence 在两个平台均可上传。
- 边界：脚本只在 CI 工作目录生成临时 manifest，不修改或伪造 checked-in 报告；`continue-on-error` 仅用于让后续检查与上传执行，若 CLI 意外成功或 rejection 不合约，验证步骤仍使 job 失败。
- 状态：完成。

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

### L1：第四周通信证据链学习计划（2026-08-31）

- 第三周 Day 6 已补充系统描述、ECU Extract、ECUC 及跨模块 PDU identity 的教练参考答案；
- 第四周只围绕一条 `DataElement → Signal/I-PDU/Frame → COM/PduR/CanIf → SocketCAN` 通信证据链学习；
- 复用 Workbench 已有 trace、validate、fault suite、supervision 和 SocketCAN lab，不因平台已进入 R5 就跳过个人通信基础验收；
- 学习计划保存在 `D:\work\improve\learning\week-04\week-plan.md`，平台仓只记录与现有工程资产的对应关系；
- 状态：计划已发布，等待学习者执行和逐日验收；无平台运行时代码变化。

### L2：第四周 Day 1 终端语法修正（2026-09-02）

- 学习者在 WSL/Bash 中执行 PowerShell 语法 `$env:PYTHONPATH='src'`，出现 `:PYTHONPATH=src: command not found`；
- 根因是 shell 语法混用，不是 Workbench、Python 或依赖故障；
- 第四周计划已拆分 PowerShell 与 WSL/Bash 两套启动命令；
- WSL 已实际验证 `.venv-linux/bin/python -m automotive_workbench.cli --help` 可成功加载当前 CLI；
- Day 1 后续统一使用 `.venv-linux/bin/python`，避免误用 Windows Python 或 `improve\.venv`；
- 状态：文档修正完成，等待 Day 1 三条追踪/校验命令的学习输出。

### P3：BSW intent 跨层 PDU 引用一致性修复（2026-09-02）

- 学习者发现 `WindowStatus` message 层错误写为 `WindowStatus_CanIfRxPdu`，而同一 Signal 的 PduR route 和 CanIf PDU 均为 Tx；
- 依据公开 DBC 中 `BODY_ECU` 为 `WindowStatus` sender、样例端口为 `PpWindowStatus`，确认本 intent 的该路径采用 BODY_ECU 发送视角；
- message 层已修正为 `WindowStatus_CanIfTxPdu`；
- `validate-map` 新增 message/signal 层 `i_pdu`、`canif_pdu` 引用一致性检查，错误码为 `INTENT-CROSS-LEVEL-REFERENCE-MISMATCH`；
- 新增回归测试，防止仅核对 DBC 属性却遗漏 intent 内部 Rx/Tx 自相矛盾；
- 同步更新两个引用该公开 intent 的 AI reviewer 评测清单 SHA-256；旧 hash 被测试拒绝，证明来源变更固定机制按设计生效；
- 边界：校验确认同一 intent 内显式引用一致性，不通过对象名后缀推断量产 ECUC 方向。

### L3：第四周 Day 1 概念验收（2026-09-03）

- 学习者已能区分 DBC 的网络传输定义、canonical contract 的 ASW 交付语义及 BSW intent 的连接作用；
- 已正确识别 factor 不一致会造成 raw-to-physical 语义冲突；
- 初答对确定性比较项覆盖不足，已补充 CAN ID、DLC、位布局、端序、符号以及 research intent/量产 ECUC 边界；
- Day 1 状态：基本理解，补充后通过；仍建议不看文档复述一次修正版。

### L4：第四周 Day 4 运行时故障任务校正（2026-09-04）

- 原学习计划把 `run-suite` 与“运行时错误 CAN ID”混在一起；实际 `run-suite` 覆盖 DLC/start bit/scale/unit/range 等静态 artifact 漂移；
- Day 4 主命令修正为 `run-can-lab` 和 `run-can-supervision`；
- 前者覆盖正常收发、错误 ID、接收超时和越界物理值，后者覆盖周期观测及 `RECEIVING → TIMEOUT → RECOVERED`；
- 增加 WSL 命令、报告路径和“故障场景 passed 表示故障被检出”的解释；
- 状态：任务说明修正完成，无运行时代码变化。

### L5：第四周 Day 5 OpenBSW 学习任务降维（2026-09-10）

- 原任务“查找 main/CanSystem/DemoSystem/测试入口”缺少可观察主线，对初次阅读大型 C++ 仓库不够友好；
- 已确认 `/home/dev/work/openbsw` 的四个目标源码文件及 POSIX Release 可执行文件存在；
- 学习任务改为追踪 `0x123 → CanDemoListener → 0x124` 回送链，并观察 `DemoSystem` 每秒发送 `0x558`；
- 增加四段限定行号的源码命令、三终端运行实验、预期现象和四行职责表；
- 明确不要求本日理解 lifecycle/async/C++ 模板，也不把 OpenBSW 实现等同于 AUTOSAR 标准调用链；
- 状态：任务说明完成，等待学习者运行观察和口述验收。

### L5：第四周 Day 4 验收参考答案（2026-09-10）

- 已回答错误 CAN ID 与 factor 的分层区别：前者属于 Frame/PDU identity，后者属于 Signal 数值转换；
- 已明确 timeout 是结果证据，不能脱离 CanIf/PduR/COM 等观察点直接判定 PduR 根因；
- 已解释 `RECEIVING → TIMEOUT → RECOVERED` 同时验证正常、故障检测、新数据恢复及旧缓存退出；
- 状态：参考答案已发布，等待学习者结合实际报告复述并填写两个故障案例。

### L4：第四周 Day 2 分层图参考答案（2026-09-04）

- 使用学习者提供的 ASW/System/ECU Extract/ECUC/Runtime 分层图回答 Day 2 三题；
- 明确 ECU Extract 是目标 ECU 相关系统事实的裁剪与配置输入，不是 COM ECUC 的同义词；
- 梳理必须在 ECUC、供应商 BSWMD、硬件和集成决策层确定的 COM/PduR/CanIf/Driver 参数；
- 给出系统描述正确但 ECU 仍收不到或上层读不到数据时，从总线到 Runnable 的证据优先定位顺序；
- 修正教学图边界：不把 RTE 直接画到 I-PDU 当作严格引用，也不把 Extract 到 ECUC 理解成无条件自动生成；
- 状态：教练参考答案已发布，等待学习者不看答案复述后完成个人验收。

## 历史升级：R3 OpenBSW POSIX 限时 spike

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

### 已冻结基线：P14 Installed Evidence Capsule Consumer

P14 将 P8/P9 的迁移胶囊与 P13 的安装后 CLI 连接：源码侧生成胶囊，随后由无项目依赖的隔离 wheel 在仓库外完成 16 文件、7 artifact、3 dependency 复验。GitHub Actions run `34581882908` 的七个实际 job 全部成功，P14 已冻结；下一里程碑仍需由明确 consumer 或学习目标触发，不自动进入发布、attestation、OpenBSW adapter 或新协议。

### 已冻结：P16 实际导出桥接；下一里程碑 P17

依据用户本次纠正，重新审核平台目标并调研 ASAM XIL、openDuT、StrictDoc 与 OpenBSW。当前优先补齐项目入口、声明验收矩阵和可阅读结果，复用既有校验/运行/证据能力；CF01 保留为之前未提交的独立工作，先前将其认定为平台下一目标的判断已撤回。详见 P15 调研与路线顶部的当前升级顺序。

P15 已本地验收；本轮 P16 接入固定 Generate-Arxml 提交的三组实际导出，验证上游生成门与跨工具映射门相互独立。2026-09-13 已完成远端七 job 验收并冻结 P15/P16，下一里程碑按实际报告需求进入 P17。

### 已冻结的可选工作：OpenBSW 上游化与完整容器

- R3a-R3e 已完成 native POSIX baseline、源码索引、全量测试和 patch artifact，不再作为当前阻塞项。
- P11 已完成当前上游漂移复验；是否开启 OpenBSW issue/PR 或继续完整 development 容器，等有明确上游目标时再决定。

诊断链当前闭环已稳定，AI 工程审查已完成 development/runtime/held-out/cross-run/cohort 五类确定性评测；CAN/UDS/DTC 的现场 producer 与固定报告 cohort 均能逐 candidate 区分 stable、drifted 与 not-comparable，固定报告同时归档哈希绑定 provenance、已匹配的调用方 expectation 和已执行的 cohort repository/job policy；preflight 失败现可在不物化请求的前提下留存最小拒绝证据。

## 2026-09-10 全局审计与契约加固

- 完成全局目标、前沿性与代码质量审计。结论为技术目标保持对齐、路线叙事轻度漂移、工程门禁中度滞后；调研覆盖 AUTOSAR R25-11、OpenBSW 2026 活动、Python 3.14、CAN/UDS 依赖、SLSA/in-toto、GitHub artifact attestations、SARIF 与 SOVD。
- 修复 evidence manifest、delivery receipt 与 capsule report 中 Python `bool` 被当作 JSON integer 接受的闭合契约缺陷，新增三组负例回归；本地全量 146 项测试中 144 项通过、2 项按环境跳过，evidence 定向测试 22/22 通过。原记录将跳过项重复计入总数，已在 P10 复核时更正。
- CI 官方 actions 更新到当前 major/minor 并固定完整 commit SHA，默认 `GITHUB_TOKEN` 权限收敛为 `contents: read`。
- 远端验收完成：GitHub Actions run `34441821082` 的 Windows/Ubuntu job 均通过；固定 SHA、只读 token、146 项核心回归、正常证据链与 controlled rejection 全部按契约运行。
- 下一窄里程碑确定为 P10 Contract Conformance 与 Runtime Currency，不增加新的汽车协议功能。

## P10：Contract Conformance 与 Runtime Currency（2026-09-10）

- 新增基于 `jsonschema` Draft 2020-12 的 schema meta-validation、`format` 检查和按 `schema_version` 自动绑定的实例校验；25 份 schema、45 份自描述样例本地通过，16 份外部或非自描述 fixture 明确保持 syntax-only。
- evidence manifest、delivery receipt、capsule report 的 boolean/integer 负例现同时验证 JSON Schema 与 loader 均拒绝，避免只测一侧产生虚假一致性。
- 新增 `resolved-dependency-inventory-0.1` 及生成脚本，记录 Python implementation/version、平台和 Workbench/CAN/UDS/质量工具的解析版本。
- 新增最小 Ruff `E4/E7/E9/F` 全仓门禁，以及 evidence bundle/capsule 和新脚本的范围化 mypy 门禁；本地均通过。
- CI 保留 Windows/Ubuntu Python 3.11 主矩阵，并增加 Ubuntu/Python 3.14 runtime-currency 全量测试 job；run `34445964343` 的三个 job 全部通过。
- 冻结复核新增 manifest、delivery receipt、capsule report 的 RFC 3339 时间戳 schema-loader 同拒绝，并让 manifest/capsule portable path schema 显式拒绝反斜杠。
- 本地全量 153 项测试中 151 项通过、2 项按环境跳过；契约/evidence 定向 29/29，compileall、schema/example、Ruff、mypy、Bash 语法和 `pip check` 均通过。
- P10 最终远端验收完成：run `34446441635` 的 Windows/Python 3.11、Ubuntu/Python 3.11 和 Ubuntu/Python 3.14 三个 job 全部通过；P10 契约冻结。

## L7：第五周 UDS / ISO-TP 最小诊断竖切计划（2026-09-11）

- 学习主题从第四周 CAN 通信闭环推进到 UDS `0x22 ReadDataByIdentifier` 最小诊断链；
- 固定使用 OpenBSW 示例 DID `0xCF01`，覆盖 UDS、ISO-TP SF/FF/FC/CF、SocketCAN/`vcan0` 和 OpenBSW 响应路径；
- 计划包含 Workbench virtual backend 实验以及 OpenBSW + `vcan0` 实验，明确二者的验证边界；
- 故障验收至少覆盖缺少 Flow Control、不支持 DID、错误 CAN ID、畸形长度中的两项；
- 本周冻结完整 DCM、DEM/DTC、刷写、安全访问和 DoIP，避免诊断范围过早扩张；
- 第六周决策门：链路不稳定则补 `can-isotp + udsoncan` 自动化客户端；稳定后再进入 DCM/DID 配置语义；
- 学习计划：`D:/work/improve/learning/week-05/week-plan.md`；
- 状态：计划已发布，等待 Day 1 学习与答题。

## 第五周 CF01 独立客户端与依赖升级（2026-09-12）

- 接续未提交实现：新增 `read-uds-did` CLI、`uds-did-profile-0.1` 和 `uds-did-read-0.1`，只向独立 ECU 发送一次 `0x22`；支持 classic CAN virtual/SocketCAN，不启动 responder。
- 固定 OpenBSW DID `0xCF01`、请求 `0x02A`、响应 `0x0F0` 和 24 字节预期值；生成 JSON/Markdown、SF/FF/FC/CF 帧证据及原始日志，并绑定 profile/log SHA-256。
- 已有现场证据 `output/upgrade-20260912/openbsw-live/` 显示读取通过；本次复核 report schema 及 profile/capture 哈希均通过。当前环境 `vcan0` 不可用，未将历史证据写成本次重新实测。
- 独立 virtual ISO-TP peer 覆盖多帧成功、数据不符、NRC、短响应、错误 DID、无响应、错误响应 CAN ID；另覆盖 blocked CLI 退出码、非法 profile 在 probe 前拒绝以及非空输出目录保护。
- 依赖约束更新为 cantools `>=44.0,<45`、python-can `>=4.6.1,<5`、can-isotp `>=2.0.7,<3`、udsoncan `>=1.26.1,<2`；本次回归实际使用 cantools 44.0.0、Python 3.12.3。
- 本地全量 165 项测试：163 通过、2 项环境跳过；29 schema、46 schema-bound examples、16 syntax-only examples、Ruff 与既有 7 文件 mypy 门禁均通过。测试摘要为 `output/upgrade-20260912/resume-tests/ci-test-summary.json`。
- 安装后 wheel smoke 和隔离 capsule consumer 均通过，后者复验 16 文件、7 artifact、3 dependency；证据位于 `output/upgrade-20260912/resume-distribution/` 和 `resume-capsule/`。`pip check` 通过，实际依赖清单为 `output/upgrade-20260912/resume-dependencies.json`。
- 使用说明已补至 `examples/openbsw/README.md` 并从主 README 链接；明确数据匹配不认证 ECU 身份，入口不自动取得通道锁。
- 状态：本地功能与回归通过；远端 Windows/Ubuntu/Python 3.14 CI 尚未执行，此里程碑尚未远端冻结。

## P15：平台目标复核与项目工作流（2026-09-12）

- 目标：补齐统一工程入口，将既有 canonical/DBC/BSW intent 校验、通信实验和证据消费连接到项目声明的验收条件。此前将 CF01 学习任务作为平台下一目标的判断已撤回。
- 调研 ASAM XIL、openDuT、StrictDoc 和 OpenBSW 官方资料，判断现阶段优先整合工作流，随后接真实导出产物，再推进项目级审查；详细依据见 `docs/research/p15-platform-workflow-reassessment-2026-09-12.md`。
- 新增 `workbench-project-0.1`、`project-acceptance-0.1`、`run-project`、公开车窗项目文件与静态 HTML/JSON 报告；每次运行先固化输入，再执行静态阶段与受门控的通信阶段。
- 验收项显式声明 ID、文本、阶段、JSON Pointer 和期望值；报告绑定证据哈希，不把声明条件通过率视为完整需求覆盖。阶段失败不能被少量通过的验收项掩盖。
- 复用 P5 manifest/verifier；证据依赖全部指向 bundle 内输入快照及本次报告，移动完整输出并移除原输入后仍可复验，篡改输入快照被拒绝。JSON evidence metadata 增加 UTF-8 BOM 读取兼容，哈希仍基于原始字节。
- 已运行公开样例：5/5 声明验收通过；报告 `output/p15-project-baseline/bundle/index.html`。真实改动复制件 scale 的演练返回 failed 并跳过通信；缺失 SocketCAN 演练返回 blocked，两者 evidence integrity 均 passed，分别归档于 `output/p15-validation/configuration-failure/` 和 `backend-blocked/`。
- 新增 6 项工作流测试通过；全量 171 项中 169 通过、2 项环境跳过。31 schema、47 schema-bound examples、16 syntax-only examples、Ruff、原 7 文件加新工作流模块 mypy、CI topology、pip check 与 diff whitespace 均通过。全量摘要：`output/p15-validation/tests/ci-test-summary.json`。
- 安装后核心 CLI smoke、隔离 capsule consumer 均通过，16 文件/7 artifact/3 dependency 基线保持；证据在 `output/p15-validation/distribution/` 和 `capsule/`。
- CI 已在 runtime-evidence 增加项目工作流及报告上传，并将新模块纳入既有 mypy 门禁；仍为四类职责、七个实际 job。远端尚未执行，不能标记跨平台冻结。
- 边界：首个项目执行契约为公开车窗通信；不自动调用 Generate-Arxml 生成器、不新增 ECU 协议、不启用任意命令执行、不自动创建 vcan/取得通道锁。
- 回退：停用新增入口即可继续原有命令；旧输入、运行内核和既有报告契约保持兼容。本次状态为本地验收完成、远端待验收，改动尚未提交或推送。
- 后续平台方向：P16 明确导出产物桥接，P17 实际项目报告驱动的工程审查；详见路线顶部，不按学习周次推进。

## P16：实际 Generate-Arxml 导出桥接（2026-09-12）

- 目标：将 P15 手写 canonical fixture 推进为真实工具导出消费，并保留上游问题作为运行门控；输入仍为公开合成车窗 DOCX，不是客户或量产数据。
- 从 `/mnt/d/work/SOA/code` 固定提交 `e912e404d52e671c7561d518d9989af3382fce51` 导出隔离源码，运行真实 `scripts/docx_to_contract.py`，未使用或修改原仓库未提交工作；生成器依赖安装于独立 `/tmp/p16-generator-env`。
- 新增 project/report 0.2，兼容 0.1；generation 声明绑定 DOCX、contract、issue report 的 SHA-256 和本地 producer revision/退出码。哈希错误在创建输出前拒绝；完整上游 findings 原样进入 generation 报告。
- 上游退出 1、未闭合问题、模型错误或 CORE ERROR 使 generation failed；所有阶段共同门控通信，不能用 canonical passed 掩盖 upstream failed。
- 三组真实导出重放通过：baseline 生产者退出 0、项目 6/6 通过；Resolution 1→2 生产者退出 0、canonical failed、通信 skipped；删除 InitValue 生产者退出 1、generation failed、canonical passed、通信 skipped。
- 上游警告保留：baseline/missing-init 各 2 条未连接端口 WARNING；scale-change 额外保留 `CORE-010-PHYS-RANGE-CONSISTENCY`。Workbench 独立产生 `MAP-NUMERIC-MISMATCH`，不修改上游严重度。
- 新增确定性公开 DOCX 生成脚本、隔离 producer 重放脚本和三组完整样例；重放记录 archive/script hash、实际依赖版本与运行结果，路径 `output/p16-replay/bridge-replay.json`，各案例报告位于同目录下 `<case>/acceptance/bundle/index.html`。
- 新增 6 项集成测试；全量 177 项中 175 通过、2 项环境跳过。31 schema、53 schema-bound examples、22 syntax-only examples、Ruff、11 文件 mypy、CI topology 通过；测试摘要 `output/p16-validation/tests/ci-test-summary.json`。后续非法 schema_version 类型补充用例随 P15 定向 6 项复验通过。
- 安装后 CLI smoke、隔离 capsule consumer 及 pip check 通过，16 文件/7 artifact/3 dependency 的 P14 基线保持；证据位于 `output/p16-validation/distribution/` 和 `capsule/`。
- CI 增加固定导出正常项目执行和 artifact 上传，负例由核心测试覆盖，保持七个实际 job；CI 不安装外部生成器，生产者实跑和导出 consumer 回归分别记录。
- 状态：本地验收完成；P15/P16 及更早 CF01 改动仍未提交/推送，远端 Windows/Ubuntu/Python 3.14 验收未运行，不标记远端冻结。
- 边界与回退：不申请最终 ARXML、不声称 DaVinci/真实 ECU 已验证；首个 runtime 仍固定公开车窗通信。可继续使用 project 0.1，核心依赖无需安装 DOCX/Excel 库。详见 `examples/generate_arxml/bridge/README.md` 和 P16 实施记录。

## P15/P16：Windows 跨平台验收修复（2026-09-13）

- 复核发现上一轮已提交并推送为 `53f1a56`；上文“未提交/推送、远端未运行”是当时状态，由本条更新。远端 run `34682217101` 的 Ubuntu/Python 3.11 与 3.14 通过，Windows 核心测试失败，运行与拒绝验收因依赖失败而跳过。
- Windows 注释确认两类原因：四项测试以默认 cp1252 解码含中文的 UTF-8 项目声明；DOCX 重放因 ZIP `create_system` 的 Windows/Unix 默认值不同而产生字节差异。
- P15/P16 测试显式使用 UTF-8；DOCX 生成器固定 ZIP creator 和权限元数据，保持既有三组 DOCX 内容与 SHA-256 不变。新增模拟 Windows ZIP 默认值的三案例字节一致性回归。
- 本地全量 178 项测试：176 通过、2 项环境跳过；31 schema、53 schema-bound examples、22 syntax-only examples、Ruff、生成脚本 mypy、CI topology 和 diff whitespace 均通过。摘要：`output/p16-cross-platform-fix/tests/ci-test-summary.json`。
- 固定导出 baseline 项目及证据完整性复验通过，可读报告：`output/p16-cross-platform-fix/baseline/bundle/index.html`。
- 远端验收：修复提交 `af699c1` 的 [GitHub Actions run `34734838719`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/34734838719) 七个实际 job 全部成功，覆盖 Windows/Ubuntu 核心、运行证据、受控拒绝以及 Python 3.14；项目报告和导出消费证据均成功上传。
- 状态：P15/P16 已冻结，CF01 客户端既有回归也随本次跨平台门通过；未重新进行 OpenBSW/vcan 实测。下一里程碑为 P17 实际失败报告驱动的项目级审查。

## 下次必须补录

- 新 schema/loader 版本的正例、负例与 parity 回归结果；
- OpenBSW 上游 HEAD 再次变化后，仅在出现明确 adapter 或上游化需求时补录下一次 drift revalidation。
