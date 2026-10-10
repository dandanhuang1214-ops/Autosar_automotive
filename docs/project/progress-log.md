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

## 当前总览（2026-10-10）

当前主阶段 P30 implementing。提示 0.6–0.12 均已通过各自远端七 job；0.12 实现 `656098b8b8dca8373ba3974ced45a317f25d05ec` / run `38012423168` 已 remote-accepted。0.11 的 v6 两条 qwen3-vl 简单状态回答已由用户确认文字准确且可用，只覆盖该窄任务。qwen3.5 无正文的根因已由原始响应确认：默认 thinking 两题均用满 4096 token、正文为空；0.12 仅在服务身份 family=`qwen35` 时关闭 thinking，保留 0.1–0.11 重放。相同两题现场复验均正常 stop、引用 2/2 并通过，适配总耗时 32.3/19.8 秒。全量 424 tests（422 passed、2 环境跳过）、隔离 wheel、合成协议、静态检查及远端双平台证据链通过。一般工程解释、资料适用性和跨项目模型用途仍未验收；下一步冻结未参与本轮修复的更广问题，分别计量 qwen3.5 与 qwen3-vl。P25 人工演示/真实反馈及物理 ECU 仍待验收。

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
| 项目配置到验收报告 | 已冻结（run `34734838719`） | P15 `run-project`、5 项声明验收、HTML/JSON、静态失败阻止运行、后端阻断、输入快照及迁移复验 |
| Generate-Arxml 实际导出桥接 | 已冻结（run `34734838719`） | P16 固定生产者提交、实际 DOCX 导出三例、generation 门控、源码/输入/输出哈希与重放 |

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

## P17：实际项目报告驱动的工程审查（2026-09-13）

- 新增 `run-project-review`，直接读取 P15/P16 `project-report.json` 及其中声明的阶段报告；为项目/阶段状态、非通过验收项和 finding severity/code/message 生成精确 JSON Pointer 断言。
- 复用 R5 的 retrieval-only 审查、SHA-256 artifact registry、citation identity 与复验机制；同时输出 `review-result.json`、`evidence-units.json` 和面向工程人员的 `project-review.md`，不接入 LLM、embedding 或外部服务。
- 阶段路径只允许报告目录内相对路径；缺失阶段文件使整次审查 `refused`，不根据项目总状态猜测根因。审查 registry 使用相对路径，完整场景归档移动后 citation validation 仍通过；非空输出目录在写入前拒绝。
- `--claim` 支持检查一条调用方声明；证据完全不覆盖时返回 `REVIEW-NO-EVIDENCE`。公开验收固定验证“物理 ECU flash timing 已测量并认证”不能由合成 DOCX 与 virtual CAN 报告证明。
- 新增 `scripts/run_project_review_scenarios.py`，重跑 P16 baseline、scale-change、missing-init 三例并分别审查；两份失败报告准确保留 `MAP-NUMERIC-MISMATCH`、`CONTRACT-OPEN-ISSUE`、上游 WARNING 及 communication skipped 证据。
- 本地全量 185 项测试中 183 项通过、2 项按环境跳过；P17/既有 review 定向 22 项通过，覆盖正常/两类实际失败、引用复验、越界声明拒答、阶段文件缺失、路径逃逸与输出保护。31 schema、53 schema-bound examples、22 syntax-only examples、Ruff、13 文件 mypy、CI topology、pip check 和 diff whitespace 均通过。
- 本地可迁移场景证据位于 `output/p17-portable/`，全量测试摘要位于 `output/p17-validation/tests-final/`；三份项目审查均 answered、coverage 1.0、citation validation passed，越界声明 refused。
- 远端验收：提交 `5b3103e` 的 [GitHub Actions run `34764974287`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/34764974287) 七个实际 job 全部成功；Windows/Ubuntu 均重跑 P17 三场景并上传 `project-review` artifact，Python 3.14 全量回归、既有安装/capsule、runtime 和 controlled rejection 门保持通过。
- 状态：P17 已冻结。当前失败定位不需要 LLM 即可给出完整、可复验答案；不因里程碑完成自动引入模型依赖。下一升级由真实项目报告、用户对解释质量的明确反馈或新 consumer 触发。

## P18：项目验收基线与候选比较（2026-09-14）

- 新增 `compare-projects`，以两份 P15/P16 `project-report.json` 为 baseline/candidate，逐稳定 ID 比较阶段状态和验收项状态/理由，并将阶段 finding 归一后计算新增与移除。
- 输出 `project-comparison.json` 与 `project-comparison.md`；每项阶段及验收变化绑定两侧报告的 SHA-256 和精确 JSON Pointer，finding 变化绑定实际阶段报告。来源使用相对路径，完整 P18 目录迁移后仍可复验。
- 分类固定为 `stable`、`regressed`、`improved`、`changed`、`not-comparable`。schema version、阶段集合或验收项 ID 集合不一致时不比较；阶段文件缺失、哈希声明不唯一或字节被修改时同样 fail closed。回归、其他变化及不可比较的 CLI 均返回非零。
- finding 指纹忽略随归档根目录变化的 `source`/`source_artifact`，其余内容和所属阶段参与比较；报告只陈述 artifact 差异，不声称确定根因或物理 ECU 行为。
- 新增 `scripts/run_project_comparison_scenarios.py`，重跑 baseline、scale-change、missing-init，并生成稳定、两类回归和反向改善四份比较。分辨率回归检出 2 个阶段、3 个验收项和 2 个新增 finding；缺初值回归检出 2 个阶段、3 个验收项和 1 个新增 finding；所有 evidence validation 通过。
- 新增 10 项 P18 测试；本地全量 195 项中 193 项通过、2 项按环境跳过。32 schema、53 schema-bound examples、22 syntax-only examples、CI topology、Ruff、15 文件 mypy、compileall、`pip check` 和 diff whitespace 均通过。场景证据及测试摘要位于 `output/p18-final/`。
- CI 在 Windows/Ubuntu `runtime-evidence` 中重跑并上传 `project-comparison` artifact，Python 3.11/3.14 的范围化 mypy 纳入新模块和脚本；仍维持四类职责、七个实际 job。
- 远端验收：提交 `a000a50` 的 [GitHub Actions run `34817437909`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/34817437909) 七个实际 job 全部成功，覆盖 Windows/Ubuntu 核心、项目比较运行证据、受控拒绝及 Python 3.14；P18 已冻结。

## P18 补强：比较结论独立复验（2026-09-22）

- 复核发现原 `validate_project_comparison` 只检查来源和已有引用，改写顶层结论、统计或删除差异仍可能通过；没有 finding 差异的阶段文件也未在消费时重新检查。
- 抽取无写入的比较构建函数，生成与复验共享确定性计算；复验重新读取两侧项目及阶段来源，逐项比对结论、basis、阶段、验收项、finding、统计和引用，嵌套值严格区分 boolean/integer。
- 新增 `verify-project-comparison <report>` CLI，只读执行并输出 JSON。真实回归报告可返回完整性 passed/退出 0；篡改、缺失来源或非法输入返回 failed/退出 2。内嵌 evidence_validation 保留为历史记录，消费时以重新计算结果为准；不提供来源身份认证。
- 保持 project-comparison-0.1 与原比较分类语义；README 增加迁移复验说明，Windows/Ubuntu runtime-evidence 增加保存后 CLI 复验步骤。
- 新增 4 项测试，覆盖八类结论/统计/引用修改、无差异阶段篡改、只读 CLI 与非法输入；P18 定向 14/14 通过。全量 199 项中 197 通过、2 项环境跳过，含既有安装后 wheel/capsule consumer 回归。
- 32 schema、53 schema-bound examples、22 syntax-only examples、Ruff、修改模块 mypy、CI topology、diff whitespace 检查通过。四个公开场景重放通过，scale-regression 独立 CLI 复验 34/34 引用通过。
- 本地证据：`output/p18-verification-upgrade/tests/ci-test-summary.json`、`output/p18-verification-upgrade/scenarios/`。状态：本地验收完成，尚未提交/推送，远端跨平台 CI 待执行，不标记本次补强已远端冻结。


## P19：项目回归可读报告与公开演示（2026-09-22）

- 依据：读取个人成长仓库的 README 与能力矩阵，沿用“工具链/配置自动化主线、BSW 集成与定位并行”的定位及每两周 20～30 小时预算。能力矩阵是历史学习基线，不把平台代码完成等同于个人能力掌握。本次 consumer 是个人日常配置回归排查与公开作品演示。
- `compare-projects` 新增离线 `index.html`，展示结论、阶段/验收变化、finding 及可展开的两侧来源、SHA-256、JSON Pointer；保留 JSON/Markdown 与现有比较契约、退出码。
- 四场景脚本增加统一 HTML 入口，串联稳定、分辨率回归、缺初值回归、反向改善。无需网页服务或前端依赖，现有 CI 场景目录上传自动包含页面。
- 页面明确标注生成时静态快照，提供 P18 独立复验命令；完整性通过不代表项目通过。正文转义，来源链接限定相对本地路径，避免将报告文本解释为网页代码或 URL scheme。
- 同步校正账本首页停留 P16 的旧状态；保留本轮开始前已有的 P18 独立复验改动。
- 验收：P18/P19 定向 16/16 通过；全量 201 项中 199 通过、2 项环境跳过，含既有安装后 wheel/capsule 回归。32 schema、53 schema-bound examples、22 syntax-only examples、Ruff、15 文件 mypy、CI topology 与 diff whitespace 通过。新增测试覆盖 HTML 文本/链接安全、缺失来源拒绝展示；迁移测试同时检查首页及四份报告的全部链接。
- 实际重放：四场景结果为 stable/regressed/regressed/improved，证据均 passed；scale-regression 的独立 CLI 复验 34/34 引用通过。演示入口 `output/p19-demo/index.html`，测试摘要 `output/p19-validation/tests/ci-test-summary.json`。
- 状态：本地验收完成，工作区未提交/推送；本轮 P18 补强/P19 尚未运行远端跨平台 CI，不标记远端冻结。未执行浏览器视觉验收，HTML 内容与本地链接由自动化检查。
- 边界：公开合成 DOCX、保存的真实生成器导出与 virtual CAN；未新增物理 ECU、商业工具验证或 LLM。回退可继续消费原 JSON/Markdown。下一步为本轮改动的远端跨平台验收及实际报告使用反馈。

## 长期路线 v3 与升级连续性纠正（2026-09-22）

- 用户明确要求按长期目标持续升级；上一轮将任务缩减为 P19 HTML 并停在本地验收，属于执行范围与验收闭环不足。
- 重新读取个人成长 README、24 周路线、目标岗位画像、能力矩阵和第六周 UDS 计划，审查实际代码限制，并核对 AUTOSAR、Vector CLI、OpenBSW 官方资料。
- 重写当前路线为六阶段：P20 多项目通信 → P21 BSW 对象图/变更影响 → P22 ARXML/商业工具桥接 → P23 独立 ECU 项目集成 → P24 工程审查 → P25 平台交付。包含每阶段用户结果、验收门、个人时间预算、依赖与阻塞替代任务；旧路线单独归档。
- 新增 `p20-multi-project-plan.md`，明确纯预检、通用运行、项目集成、第二项目与跨平台交付四个实施包；P20 状态为 planned，尚未实现，不因计划完成而计入平台功能。
- 新增根目录 `AGENTS.md`，约定以后“继续升级”直接推进当前未完成阶段，再进入已排定下一阶段；不能以独立小补丁替代长期能力，也不能将本地通过等同远端通过。
- P18 补强/P19 实现提交 `88c24e2` 已推送，远端 run `35748563878` 七 job 全部 success；原“尚未提交/远端待验收”记录为当时状态，由本条更新。
- 当前工作不修改个人学习仓库，不把平台自动化结果视为个人已经掌握 BSW/诊断；后续能力掌握仍按个人学习任务独立验收。

## P18 补强/P19：远端冻结（2026-09-22）

- 实现提交：`88c24e27b175a6348f48e84adc570f4bd98e3fc8`。
- [GitHub Actions run `35748563878`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/35748563878) 已 completed/success，七个实际 job 全部 success：Windows/Ubuntu core-contracts、runtime-evidence、controlled-rejections，以及 Python 3.14 runtime-currency。
- runtime-evidence 包含四场景比较重放、保存后比较独立 CLI 复验与报告 artifact 上传；本轮 P18 补强/P19 完成远端验收。此结论不包含未执行的物理 ECU/本机 SocketCAN 现场实验。
- 路线 v3、P20 计划与执行规则另作后续文档提交；实现验收以以上固定提交为准。文档本地链接和 diff whitespace 检查通过。
- 下一步明确为 P20a 运行声明与开总线前预检，随后 P20b 通用运行、P20c 项目集成、P20d 第二项目与跨平台交付。P20 未实现，不提前标记完成。

## 下次必须补录

- 新 schema/loader 版本的正例、负例与 parity 回归结果；
- OpenBSW 上游 HEAD 再次变化后，仅在出现明确 adapter 或上游化需求时补录下一次 drift revalidation。

## P20a：运行声明与开总线前预检（2026-09-23）

- 新增闭合 communication-vectors-0.1 / communication-plan-0.1、纯编译函数及只读 `plan-communication` CLI；先检查静态映射，再验证全部向量，输入无效时不打开总线或写运行输出。
- 新增车窗完整信号向量与 ThermalControl 三报文样例（两 Tx/一 Rx、801/817/833、4/2/3 字节、缩放/偏移）；计划保存输入 SHA-256、声明值、payload、原始整数及量化结果。
- 覆盖结构/schema parity、未知/缺值/重复身份/方向/不可编码值、bool/非有限数、超时、FD/multiplex/浮点线编码、CLI 无副作用、BOM/重复 JSON 成员。schema 与语义检查边界见 `p20-communication-declarations.md`。
- Windows/Ubuntu runtime-evidence 新增真实 CLI 双样例预检、未知信号拒绝和 artifact 上传；仍维持七 job 拓扑。旧 runtime/project/report 契约不变。
- 本地验收：209 项测试中 207 通过、2 项按环境跳过；34 schema、56 schema-bound examples、22 syntax-only examples、Ruff、16 文件 mypy、CI topology、pip check 与 whitespace 通过。真实 CLI 双计划及未知信号拒绝归档于 `output/p20a-validation/scenarios/`，全量摘要 `output/p20a-validation/tests-final/ci-test-summary.json`。首轮失败为 schema 总数断言仍固定 32，更新为 34 后全量通过。
- 远端验收：实现提交 `102590780b4d9cfcc81a2aa19a5a16242b8b67fb`；[run `35809063044`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/35809063044) completed/success，Windows/Ubuntu core-contracts、runtime-evidence、controlled-rejections 及 Python 3.14 runtime-currency 七 job 全部 success。两平台的预检场景与 `communication-preflight` artifact 上传均 success。
- 状态回填仅修改文档，随后使用 `[skip ci]` 文档提交推送；不把该文档提交当成新的实现验收，以上固定实现提交与 run 是本次验收依据。
- 状态：P20 implementing，P20a remote-accepted。P20a 不证明通用收发；P20b/P20c/P20d 和 SocketCAN 现场门尚未完成。下一步为 P20b：从通过预检的声明导出 filters 并执行 Tx/Rx，保留 probe、blocked、超时和清理证据。

## P20b：声明驱动的通用消息执行（2026-09-23）

- 新增 `run-declared-communication` 与 `declared-communication-runtime-0.1`：开总线前完成全部向量/BusConfig/输出保护预检及输入哈希复核；按消息身份、方向和信号值执行车窗与 ThermalControl，不在新内核中硬编码业务名称或 ID。
- 每向量创建 local/peer 两端，Tx 为 local→peer，Rx 为 peer→local；从计划生成标准 11 位/扩展 29 位精确 filters，每向量重建端点防止上一向量队列残留。send/recv 共用有界 timeout；资源获取失败、发送/接收/解码异常和单端 shutdown 失败均保留报告并独立清理已开端点。
- 报告保留计划/源哈希、量化原始整数、实际帧/解码、方向、原因及清理结果；结果以稳定 vector ID 建索引。后端不可用为 blocked/退出 3、无实际帧；运行失败退出 2；非法输入/输出退出 1。旧 communication runtime、project 0.1/0.2 与 CAN lab 保持兼容。
- 新增 12 组测试，覆盖双项目、重复 Rx、标准/扩展 ID、实际 virtual 错 ID 过滤/抑制发送超时、错误 flags/DLC/payload、partial open/异常清理、probe 异常、非有限解码、timeout 预算、无副作用拒绝、输入漂移、输出保护与 CLI 退出码。
- 场景脚本通过两个真实 CLI 正例，真实 virtual transport 的 wrong-ID/no-send 注入均按预期 failed/receive_timeout，缺失接口为 blocked。注入方式与实际 send 记录另存 `injection.json`，不声称物理故障。归档于 `output/p20b-validation/scenarios/`；CI runtime-evidence 两平台新增执行/上传步骤，topology guard 固定职责，仍为七 job。
- SocketCAN 现场：初查 `vcan0` 不存在，经已有 `setup_vcan.sh --apply` 恢复；新 Linux 入口复用既有通道锁命名并保存 host probe。ThermalControl 3/3、车窗 2/2 passed，均记录 `held_by_entrypoint`。报告位于 `output/p20b-validation/socketcan-thermal-final/`、`socketcan-window-final/`。首轮历史 `.venv-linux` 使用 cantools 41.4.3，最终显式 `--python .venv/bin/python` 使用 python-can 4.6.1/cantools 44.0.0 复跑；这是本机 Linux vcan 与同进程两个端点收发，不能当作物理 CAN 或独立 ECU。
- 本地验收：最终 221 项测试中 219 通过、2 项按环境跳过；35 schema、56 schema-bound examples、22 syntax-only examples、Ruff、18 文件 mypy、CI topology、pip check、shell syntax 和 whitespace gate 通过。摘要 `output/p20b-validation/tests-final/ci-test-summary.json`。
- 远端验收：实现提交 `ef2e89e0e5b84bd552ab36a00db293aff98b1d62`；[run `35875029401`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/35875029401) completed/success，Windows/Ubuntu core-contracts、runtime-evidence、controlled-rejections 及 Python 3.14 runtime-currency 七 job 全部 success。两平台 Run declared communication scenarios 均 success；上传日志确认 `declared-communication-Linux`（artifact `10756762315`，11262 bytes）和 `declared-communication-Windows`（artifact `10756372543`，11300 bytes）均 successfully finalized/uploaded。
- 后续仅文档状态回填使用 `[skip ci]` 提交推送；该状态提交不算新的实现验证，验收依据为以上固定实现提交和 run。
- 状态：P20 implementing；P20b remote-accepted，双项目 SocketCAN 现场路径已通过。下一步 P20c：声明进入版本化项目与输入快照、静态门控、路径绑定、稳定验收 locator、review/compare 与迁移复验；尚未标记完整 P20 交付。

## P20c/P20d：完整多项目工作流与阶段交付（2026-09-24）

- 本轮按用户要求完成一个完整大阶段，覆盖 P20 剩余项目接入与交付门，不再停在单个实施包。
- 新增 project/report 0.3，输入快照包含 vectors，可选复用 generation；纯预检检查全部声明及映射路径覆盖。静态失败保存报告并跳过通信，合法输入执行通用 runner；新绑定报告逐向量/消息/信号/方向/frame ID/原始值核对。默认 virtual CLI 使用唯一通道。
- ThermalControl 增加 canonical contract 和 project，车窗增加独立 project-declared.json；旧 project.json 保留 0.1。同一内核运行结构不同的两项目；升级新报告时需把旧 `/runtime_status` locator 改为 `/status` 或向量 ID 路径，文档已明确。
- 新报告保存可迁移来源库存与比较依据；review 验证快照/运行来源哈希及定义后生成引用。comparison 0.2 对新报告强制同比较标识、本地 ECU、完整向量与完整验收条件，定义漂移及不同项目为 not-comparable；旧 comparison 0.1 语义保持。
- 公开脚本归档六案例：window/thermal passed、canonical 静态回归 failed+communication skipped、合法输入下实际 virtual 发送抑制超时 failed、验收条件变化 failed、后端 blocked。五份比较分别 stable/regressed/regressed/not-comparable/not-comparable，完整目录移动后 manifest、citations、重新审查与 comparison 均可复验。
- 新增 11 组测试涵盖闭环、兼容、非法输入无副作用、schema/loader parity、静态回归门控、不同验收定义/向量拒绝比较、来源篡改、绑定身份漂移、迁移和 0.3 generation。已有隔离 wheel/胶囊 consumer 保持通过；最终全量 232 项中 230 通过、2 项按环境跳过；36 schema、58 schema-bound examples、23 syntax-only examples、Ruff、20 文件 mypy、CI topology、pip check、shell syntax 与 whitespace 全部通过。摘要 `output/p20-final-validation/tests-final/ci-test-summary.json`。
- SocketCAN：`scripts/linux/run_socketcan_projects.sh` 在已存在 vcan0 上复用通道锁，两项目均通过项目验收、审查、稳定比较和独立复验；向量分别 2/2、3/3，现场报告及 hash 见 [P20 验收表](p20-acceptance.md)。不声称物理 ECU 或独立进程 ECU 已验证。
- 已接入 Windows/Ubuntu runtime-evidence 的完整场景及 `multi-project-release` artifact，保持七 job。公开教程 [多项目指南](p20-multi-project-guide.md) 包含写项目、运行、迁移、比较语义及边界。
- 状态：P20 local-accepted，尚未提交/推送，整阶段远端验收待执行。验收后下一主阶段为 P21 通信对象图与变更影响；平台实现证据不代表个人 BSW 学习已经掌握。

## P20：整阶段远端冻结并进入 P21（2026-09-24）

- 实现提交 `31ca4ef80ee9ff9c7147d964d805d73a5026798c`；[run `35979820300`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/35979820300) completed/success，Windows/Ubuntu core-contracts、runtime-evidence、controlled-rejections 以及 Python 3.14 runtime-currency 七 job 全部 success。
- 两平台完整多项目场景与 `multi-project-release` 上传均 completed/success，覆盖六项目案例、五种比较、原目录移除后的 manifest/citations/重新审查及比较复验。不是仅凭单元测试冻结。
- 本地最终全量 232 项中 230 passed、2 environment skips；两项目 SocketCAN 验收/审查/比较/独立复验成功，现场与 virtual CI 分开计量。完整 gate 表和现场报告哈希见 [P20 验收记录](p20-acceptance.md)。
- 状态：P20a–d 全部收口，P20 remote-accepted。随后纯文档状态回填使用 `[skip ci]`；实现验收只引用上述固定提交和 run，不把文档提交当新实现验证。
- 已推进下一主阶段 P21（planned）：对象图稳定身份/有类型关系/来源，随后六类规则与两版变更影响。当前没有声称 P21 已实现，也不将 P20 的结果比较冒充配置影响分析。路线、首页、概览和下一任务已同步。

## P21：通信对象图、规则与配置影响（2026-09-24）

- 依据当前路线进入完整 P21 主阶段。新增纯构图核心、闭合 `communication-graph-0.1` / `communication-impact-0.1`，CLI `build-communication-graph`、`compare-communication-config`、`verify-communication-graph`。旧 intent/project/runtime/review/compare 消费路径不变。
- 对象身份包含项目 comparison_key、本地 ECU、类型和名称；车窗 8 对象、ThermalControl 14 对象，覆盖 Tx/Rx 与多信号共享 route。类型依赖边和对象均带来源 locator，五来源原始快照以 Base64/SHA-256 保留，可离线迁移复算。
- 配置规则覆盖断引用、重复身份、方向、长度/布局、路由端点；FD/multiplex/float 线编码拒绝。规则依据与正负例明确为平台 intent/DBC 约束，不冒充厂商 ECUC 或 AUTOSAR release 验证。
- 第六类能力为配置影响：按稳定身份比较语义、新旧依赖图并集传播，保存对象变更、来源字节/locator 差异、影响路径及向量/验收 ID。不同项目/本地 ECU 或无效图不可比较；contract、generation 和无向量覆盖的未知边界保留。重命名按删除/新增处理，不预测运行结果。
- 本地公开 CLI 10 场景全通过：两项目正常、稳定比较、跨项目拒绝、ThermalStatus 比例变化及五类真实配置失败；各场景独立 replay 通过，删除生成的候选源目录后迁移复验通过。比例变化要求重跑 thermal-status 及整体门，排除另外两条报文的向量级验收。证据 `output/p21-validation/scenarios-final/`。
- 最终回归 245 项：243 passed、2 environment skips；新增 13 组测试覆盖规则、实际 DBC 重叠/越界（含未映射信号）、不支持语义、变化传播、重排、范围隔离、definition/contract 漂移、迁移篡改、CLI 输出保护和非法输入。摘要 `output/p21-validation/tests-final/ci-test-summary.json`。首轮两处测试注入未实际改变数据，修正 fixture 变更值后通过；随后补充来源准确性和不支持语义回归。
- 38 schema、58 schema-bound examples、23 syntax-only examples、Ruff、22 文件 mypy、CI topology、pip check 与 whitespace 通过。Windows/Ubuntu runtime-evidence 已接入独立场景和 artifact，保持七 job。
- 状态：P21 local-accepted，当前实现尚未提交/推送，远端待执行；本地成功不等同远端验收。下一任务为本实现七 job 验收，通过后推进 P22 受限 ARXML 桥接。指南、验收表、首页与路线同步；个人 BSW 学习掌握不由本次自动化结果代替。


## P21：整阶段远端冻结并进入 P22（2026-09-24）

- 实现提交 `79d1f3bba43fa7f9dbf85e5965741d50e10e4bdd`；[run `36022099415`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36022099415) completed/success。七个 job 均 success：Windows/Ubuntu core-contracts、runtime-evidence、controlled-rejections，以及 Python 3.14 runtime-currency。
- 两平台 `Run communication graph scenarios` 与 `Upload communication graph evidence` 均 completed/success；产物为 `communication-graph-Windows`、`communication-graph-Linux`。公开 CLI 正例、故障、变化影响及迁移独立复验通过，既有 P20 场景与审查比较兼容路径同时通过。
- 本地最终 245 tests（243 passed、2 environment skips）和全部质量门通过。范围与规则依据见 [P21 指南](p21-communication-graph-guide.md)，完整门表见 [验收记录](p21-acceptance.md)。未执行或声称新增物理 ECU/商业工具现场验证。
- 状态：P21 remote-accepted，冻结。上一条 local-accepted/远端待执行是提交前状态，本条据实际 CI 更新。随后纯文档状态回填使用 `[skip ci]` 提交推送；不把文档提交算作新的实现验收。
- 下一主阶段 P22 planned，已整理 [具体入口](p22-arxml-bridge-plan.md)：先核查真实生产者 ARXML XML、受限元素与版本；当前 DOCX/contract/issues 桥接不冒充 ARXML 导入。商业工具许可/环境与公开离线路径分别验收。

## P22：真实 XML 导出与受限离线桥接（2026-09-26）

- 继续当前主阶段，新增固定生产者 `e912e404d52e671c7561d518d9989af3382fce51` 的真实 `--arxml` 重放脚本；只消费公开车窗 DOCX，未读取其他工程 XML。实际退出 0，原始 XML、输入/脚本/archive hash、命令参数与依赖版本已归档，基准产物和 provenance 纳入仓库。
- 审计确认 r4.0 namespace / `AUTOSAR_4-3-0.xsd` 声明、36 SHORT-NAME 对象、25 引用。新增无第三方 XML 运行依赖的 `import-arxml`、`compare-arxml`、`verify-arxml` 及两份闭合 schema；保存完整 XML/Base64/SHA-256、结构 locator、对象字段、REF/TREF/DEST、unsupported 和明确未知边界。验证是已审计结构语义与引用完整性，不是完整 AUTOSAR XSD 或 ECUC 验证。
- 保留实际抽象 APPLICATION-DATA-TYPE DEST 到 primitive 类型的关系；重复身份、悬空引用、DEST 冲突失败；未支持元素/属性覆盖为 partial，禁止稳定比较。UTF-8/版本/DTD/entity/大小/深度边界在创建输出前检查。UUID 与格式变化不算语义变化；两次真实工具导出虽字节不同，比较 stable/0 changes，证据 `output/p22-validation/real-producer-repeat/`。
- 三组 golden 以真实 XML 为基准，唯一锚点构造悬空 TYPE-TREF 与 PERIOD 0.01→0.02；后者只改变 timing event 对象。五个真实 CLI 场景、原输入删除后的五份迁移快照复验均通过，证据 `output/p22-validation/scenarios-final/`。变体是显式注入，不冒充生产者错误导出。
- 新增 11 组测试覆盖真实 XML/闭合报告、精确变化、UUID/重排、引用/身份失败、未知语义、非法 XML/版本/资源边界、篡改/畸形报告、来源 hash、输出保护与 CLI 无副作用。最终全量 256 项中 254 passed、2 environment skips，摘要 `output/p22-validation/tests-final/ci-test-summary.json`；40 schema、58 schema-bound examples、25 syntax-only examples、Ruff、25 文件 mypy、CI topology、pip check、compileall 和 whitespace 通过。
- Windows/Ubuntu runtime-evidence 新增独立 ARXML 场景及 artifact 上传，保留七 job；CI 消费冻结公开导出，真实生产者运行独立记录。指南、首页、路线、总览与下一任务同步。
- 状态：本轮离线路径 local-accepted，实现尚未提交/推送，远端待执行。P22 主阶段 implementing；下一任务为版本化项目输入快照、静态门控和审查/比较接入，再完成完整公开路径冻结。没有映射缺失的 COM/IPdu/PduR/CanIf，没有声称个人学习掌握或商业工具往返通过。默认 Vector 路径未发现匹配，只作为有限安装探测；商业许可/实际安装与真实导入仍未验证。


## P22：离线路径远端验收（2026-09-26）

- 实现提交 `6166b8043c7f55238f9fbcd3999266829c8ef7fe`；[run `36235450078`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36235450078) completed/success，已核对 head SHA 与七个 job。
- 七 job 均 success：core-contracts Windows `108386269592` / Ubuntu `108386269670`；runtime-evidence Windows `108386554672` / Ubuntu `108386554710`；controlled-rejections Windows `108386554712` / Ubuntu `108386554725`；Python 3.14 runtime-currency `108386269508`。
- 两平台 `Run ARXML bridge scenarios` 和 `Upload ARXML bridge evidence` 均 completed/success，对应 `arxml-bridge-Windows` / `arxml-bridge-Linux`。正常、悬空引用、周期变化、拒绝比较及移除输入后的迁移复验获得双平台执行证据；既有 P20/P21 回归保持通过。实际 job/step 明细另存 `output/p22-validation/remote-ci.json`。
- 状态：本轮离线导入/比较/复验 remote-accepted；P22 主阶段仍 implementing，未标记整阶段完成。下一项仍为版本化项目快照/静态门控和审查接入；商业工具往返仍未验证。平台执行证据不替代个人学习验收。
- 这条记录及首页/路线为后续纯文档状态回填，使用 `[skip ci]` 提交推送，不把文档提交当新实现验收。上条 local-accepted/尚未推送是实现提交前记录，本条由实际远端结论更新。


## P22：版本化项目集成与完整公开路径（2026-09-27）

- 新增 project/report 0.4，强制 ARXML 与 provenance 输入快照，保留旧 0.1–0.3；独立 `arxml-project-gate-0.1` 内嵌原导入报告。非法 XML/版本/hash 在输出前拒绝；悬空引用与 partial 覆盖生成失败报告并跳过通信，不受验收条件是否声明 ARXML 影响。
- 审查从快照重算 ARXML 阶段，引用 ERROR、覆盖和未知边界；篡改报告并更新库存 hash 仍会被重算拒绝。比较沿用 0.2，在 0.4 basis 绑定受限语义摘要，语义变化/无效输入与正常基线 not-comparable；具体对象变化由独立 ARXML diff 提供，格式变化仍 stable。不推断 XML 到 COM/PduR/CanIf 的未知映射。
- 公开脚本四个真实 CLI 场景：normal passed、dangling failed、period-change passed、unsupported failed；两个失败均 communication skipped。周期仅改变 timing event；变体标注 synthetic-mutation。移除生成的输入并移动完整目录后，4/4 manifest、原引用、重审、comparison 和 XML 内嵌快照复验通过。证据 `output/p22-project-validation/release-scenarios/`。
- 新增六组专项测试，最终全量 262 tests：260 passed、2 environment skips；41 schema、59 schema-bound examples、25 syntax-only examples、Ruff、27 文件 mypy、CI topology、pip check 和 whitespace gate 通过。首轮发现新增版本集合判断对非法 list 值抛 TypeError，已补字符串预检并完成回归；schema 冻结数量同步更新。最终摘要 `output/p22-project-validation/tests-final/ci-test-summary.json`。
- Windows/Ubuntu runtime-evidence 接入公开脚本与 `arxml-project-{OS}` 上传，仍为七 job。指南提供项目运行/审查/比较入口；[验收表](p22-acceptance.md)记录边界和商业恢复路径。
- 有限商业环境探测：PATH 三个候选命令无匹配，两个 Program Files 下无 Vector/DaVinci 一级目录，`C:/Vector` 不存在；未检查全盘、注册表或实际许可，不声称本机绝无安装。商业往返 blocked，需实际工具路径、版本、合法许可和公开工程后执行真实导入/回导。
- 状态：本轮公开路径 local-accepted，实现尚未提交/推送，远端待执行；当前主阶段 P22 implementing。下一任务为本实现七 job 远端验收；通过后公开路径冻结，商业 blocked 单列并推进既定 P23。平台实现不代替个人学习掌握。


## P22：公开路径远端冻结并推进 P23（2026-09-27）

- 实现提交 `0e002459b07bd4c5e71bbfd8602eb0acd9136c23`；[run `36257173567`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36257173567) completed/success，已核对 head SHA。
- 七 job 全部 success：core-contracts Windows `108446048332` / Ubuntu `108446048550`；runtime-evidence Windows `108446389755` / Ubuntu `108446389743`；controlled-rejections Windows `108446389719` / Ubuntu `108446389709`；Python 3.14 runtime-currency `108446048545`。
- Windows/Ubuntu 的 `Run ARXML project scenarios` 与 `Upload ARXML project evidence` 均 completed/success；正常、悬空、周期变化、未知语义与迁移复验已通过双平台场景。原始 job/step 明细存于 `output/p22-project-validation/remote-ci.json`。
- 状态：P22 公开路径 remote-accepted 并冻结；商业往返仍 blocked，按路线推进 P23 planned。本次为纯文档状态回填与下一阶段接入计划，使用 `[skip ci]` 提交；不把文档提交算作新的实现验收，也不声称 P23 已实现。
- P23 只读入口核查：现有 `read_uds_did` 可复用；本机 OpenBSW HEAD 为 `dbd6e118a9aaa2db36e4461ce76655e8f285598d`，存在既有 CANFrameTest 修改，未改动；Release ELF 存在，但历史构建不能单凭存在视为本轮可复现构建。源码显示 vcan0、请求 0x02A、响应 0x0F0、CF01。沙箱内 netlink 查询被拒，提升权限后实际返回 `Device "vcan0" does not exist.`；这是通道缺失，不是诊断失败。
- 下一任务：实现 P23 外部 ECU 声明与构建/寻址绑定、预检和进程生命周期，再纳入项目快照/验收；完整成功、无响应、错误 DID/ID、blocked、清理和隔离门见接入计划。现场恢复使用既有 `setup_vcan.sh --apply`，固定干净构建后执行，不能用历史 live 报告代替。

## P23：固定构建与独立 ECU 执行底座（2026-09-27）

- 按既定阶段新增 `external-ecu-build/execution/run-0.1` 三份闭合契约，CLI `run-external-ecu` 与 `verify-external-ecu`。输入先校验构建文件 hash、角色唯一性、时限、通道/请求响应 ID/DID/期望数据绑定；未声明的漂移在输出和进程创建之前拒绝。保留旧项目 0.1–0.4、virtual 和手动 DID 客户端。
- `build_openbsw_execution.py` 要求固定干净 OpenBSW `dbd6e118a9aaa2db36e4461ce76655e8f285598d`，真实执行 configure/clean-first Release build，保存命令/工具、ELF、cache 与三份关键源码 hash。本次在独立 `/tmp/workbench-p23-openbsw` 完成 379-action 构建，未改动旧工作树及其 CANFrameTest 修改。
- 执行器持同通道共享锁，先 probe，再启动独立 ECU 和独立诊断客户端；客户端复用既有只读 CF01 请求。启动等待、客户端总期限、进程组 TERM/KILL 和父进程 reap 均有界，清理限于自己创建的进程。报告保存 PID/退出码、日志、输入来源快照及可迁移库存；二进制仅存 hash，离线复验不执行它、不认证 ECU 身份。
- vcan0 经已有幂等脚本恢复。实际场景 normal passed，完整 SF/FF/FC/CF 与 24 字节一致；no-response timeout、wrong-did negative_response、wrong-response-id timeout、lock-busy blocked 且无 ECU 启动。五份报告删除生成变体输入并移动目录后全部复验通过，报告 hash 见 [P23 验收表](p23-acceptance.md)，本机证据 `output/p23-validation/live-scenarios/`。错误 DID/ID 是明确的客户端故障变体，不冒充生产者缺陷。
- 最终全量 274 tests：272 passed、2 environment skips；12 组专项包含实际 SIGTERM、早退、部分启动、客户端 deadline、KILL 升级、通道锁、schema、来源篡改及无副作用拒绝。首轮发现测试共用宿主锁目录受到沙箱限制，改为每测试独立临时锁目录；中断用例揭示 InterruptedError 被一般 OSError 分支归类，已修复并定向复验。摘要 `output/p23-validation/tests-final/ci-test-summary.json`。
- 44 schema、60 schema-bound examples、25 syntax-only examples、Ruff、30 文件 mypy、CI topology、pip check 和 whitespace gate 通过。Windows/Ubuntu runtime-evidence 新增离线 blocked/漂移拒绝/迁移场景及独立上传；该合成证据不替代本机 OpenBSW。Linux 核心回归执行真实进程生命周期替身测试；Windows 对 Linux 专有进程测试显式跳过。
- 状态：执行底座 local-accepted，实现尚未提交/推送，远端待执行；P23 主阶段仍 implementing。下一任务为版本化项目快照、验收 locator、静态门控与审查引用接入，以及剩余通道/整阶段门。首页、路线、概览、指南、学习练习与下一项任务同步；不以本轮执行底座冒充整阶段完成或个人学习掌握。

### P23 本轮 CI 平台类型修正

- 首个实现 `2cff77a` 已推送；run `36323201947` 实际结论 failure。Ubuntu core-contracts 和 Python 3.14 runtime-currency success；Windows core tests 通过，但 scoped mypy 对 Linux 专有 `fcntl.flock/LOCK_*`、`os.killpg`、`signal.SIGKILL` 报八项 attr-defined，Windows core job failure，runtime-evidence/controlled-rejections 因依赖未通过而 skipped。
- 在锁与进程组清理入口增加显式 Windows 拒绝分支，使平台边界同时对运行时与类型检查可见；不关闭类型检查，也不放宽七 job 验收。修复后进行 Linux/Windows-target mypy 与 P23 专项复验，后续实现须独立远端验收。该失败 run 不计作 acceptance。


## P23：执行底座远端验收（2026-09-27）

- 最终实现提交 `320defd6b23d22800520b7434bd0ae739164e6ce`；[run `36323420799`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36323420799) completed/success，已核对完整 head SHA。原始明细保存于 `output/p23-validation/remote-ci.json`。
- 七 job 全部 success：core-contracts Windows `108631515656` / Ubuntu `108631515699`；runtime-evidence Windows `108631852777` / Ubuntu `108631852718`；controlled-rejections Windows `108631852765` / Ubuntu `108631852783`；Python 3.14 runtime-currency `108631515576`。
- 两平台 `Run external ECU offline scenarios` 与 `Upload external ECU offline evidence` 均 completed/success，对应 `external-ecu-Windows` / `external-ecu-Linux`。这证明离线 blocked/拒绝/迁移及回归通过；真实 OpenBSW 构建与 SocketCAN 五场景仍独立记录为本机现场证据。
- 本轮执行底座 remote-accepted；P23 主阶段仍 implementing，未冻结整阶段。下一任务为统一版本化项目快照、静态门控、诊断验收 locator 和审查引用，并完成剩余通道与整阶段门。个人学习验收不由这些自动化结论代替。
- 本条及首页/路线/验收表为后续纯文档状态回填，使用 `[skip ci]` 提交推送；不把文档提交当作新的实现验证。首轮失败及修复过程保留，上述固定实现与成功 run 才是本轮远端验收依据。

## P23：独立 ECU 纳入统一项目（2026-09-27）

- 新增 project/report 0.5，在 ARXML 项目输入基础上声明 `inputs.execution`；保存原始 execution/build/profile、关键构建来源和实际 runner 输入快照。启动前强制 SocketCAN/channel 与构建一致，未声明 ID 漂移和通道漂移在输出前拒绝；旧项目 0.1–0.4 和独立执行契约保持兼容。
- 静态 canonical/mapping/ARXML/可选 generation 门失败时，两类运行阶段均 skipped；通过后分别执行声明式通信与独立 `external_ecu`。后者保存可声明的诊断 locator、执行报告 hash、源码 commit、失败原因和明确范围；两阶段不推断 DBC/SWC 到 OpenBSW 内部映射。
- 审查从完整快照/库存重算静态门、外部执行摘要、通信绑定和验收结果；改变阶段结果并重算其来源 hash 仍拒绝，布尔/整数混淆也拒绝。比较沿用 0.2，绑定构建内容、诊断 profile 和执行条件；不同 fault/launch_ecu/验收定义为 not-comparable。manifest 与引用保留可迁移路径，不在迁移审查中执行 ECU。
- 本机实际 OpenBSW 项目八案例完成：正常 passed、静态失败 skipped 两阶段、条件变更 failed、无响应/错误 DID/ID failed、未声明 ID/通道漂移拒绝。六份报告移除生成输入并移动目录后，manifest、原引用、重审和比较复验全部通过；物理 ECU 越界声明拒答。证据 `output/p23-project-validation/live/`，hash 见 [P23 验收表](p23-acceptance.md)。上一轮真实锁冲突、启动/期限/信号/清理证据保持。
- 双平台离线脚本五案例及三份迁移报告通过，明确标记 offline-blocked-only；已接入 runtime-evidence 的独立场景/上传，七 job 拓扑不变。固定构建仍限 vcan0；通道漂移提前拒绝，不以不同锁名单测声称另一通道 ECU 已执行。外部阶段持锁，不声称项目整体事务持锁。
- 最终全量 283 tests：281 passed、2 environment skips；九组专项覆盖门控、schema/loader parity、来源篡改、布尔类型、原输入变化、可选 generation、比较与迁移。45 schema、61 schema-bound examples、25 syntax-only examples、Ruff、32 文件 mypy、Windows-target 新入口类型检查、topology、pip check、compileall 与 whitespace 通过。摘要 `output/p23-project-validation/tests-final/ci-test-summary.json`。
- 实施中修复迁移时静态报告残留绝对路径、场景脚本引用复验 API 参数和脚本模块别名导致的 mypy 重复模块；最终专项和现场迁移复算通过。未修改原 OpenBSW 工作树，未发送外部贡献。
- 状态：P23 整条固定 POSIX/vcan0 路径 local-accepted，本轮实现尚未提交/推送，远端待执行；不继承上一执行底座实现的 CI 结论。通过本轮七 job 后冻结 P23，推进 [P24 工程问题审查](p24-engineering-review-plan.md)。首页、路线、总览、指南和学习练习同步；平台证据与个人学习分别验收。


## P23：项目集成远端冻结并推进 P24（2026-09-28）

- 实现 `3e4c29aba190f74cf0e17641af649892a37f415a` / [run `36331506323`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36331506323) 七 job 全部 success，Windows/Ubuntu 项目场景与上传均 success。P23 固定 POSIX/vcan0 范围 remote-accepted；现场证据沿用已记录的真实构建与诊断，不把远端离线验收当现场运行。
- 实际 job：runtime-currency `108654216823` success；core-contracts (windows-latest) `108654216899` success；core-contracts (ubuntu-22.04) `108654216949` success；controlled-rejections (ubuntu-22.04) `108654627129` success；runtime-evidence (windows-latest) `108654627169` success；runtime-evidence (ubuntu-22.04) `108654627175` success；controlled-rejections (windows-latest) `108654627183` success。两平台 `Run external ECU project scenarios` 和 `Upload external ECU project evidence` 均 success，原始明细保存于 `output/p23-project-validation/remote-ci.json`。
- 上一条“尚未提交/远端待执行”是实现提交前记录。本条核对既有实现和实际运行后冻结，不把本轮 P24 提交算作 P23 实现验收。下一主阶段 P24 已按路线启动。


## P24：固定工程问题消费者与开发基线（2026-09-28）

- P23 七 job 已核对并冻结后进入既定 P24 主阶段。新增 `list-engineering-questions`、`review-engineering`、`verify-engineering-review`，支持 P21 图/影响、P22 XML 导入/比较、P23 项目 0.5 和独立执行报告。复用已有领域来源复验与 JSON Pointer；不执行 ECU，不改变旧审查契约。
- 首批固定六类 30 题，开发 gold 独立记录状态/值及禁止推断范围。`engineering-review-0.1` 保存问题目录 hash、源版本/相对路径/hash、完整结构化引用和筛选结果；保留 null/空集合与实际类型，无证据的内部映射、唯一根因、商业 ECUC、物理 ECU 和身份声明明确拒答。目录策略改变须版本化，不能静默使历史答案适配新问题。
- 来源复验补强：图/ARXML 原先使用 Python 对象相等，可能接受 true 与 1（false 与 0）替换；现在使用严格 JSON 比较。新增 12 组测试覆盖真实源重算、类型替换、伪造版本/答案/引用/目录 hash、完整字段拒绝、迁移及无副作用输出保护。首轮两条测试误以为 is_signed 是顶层属性、ARXML finding 有 severity，按真实嵌套结构修正；缺失 severity 保留缺失，不人为增加等级。
- 全量 295 tests：293 passed、2 environment skips。46 schema、61 schema-bound examples、25 syntax-only examples、Ruff、34 文件 mypy、Windows-target 新入口检查、CI topology、pip check 和 whitespace 通过。摘要 `output/p24-validation/tests-final/ci-test-summary.json`。
- 开发基线 30/30 题、30/30 引用复算、5/5 拒答通过；来源包括两个公开通信项目、公开 XML 的合成故障、合成缺失构建的离线项目。删除原位置后 30/30 答案随整个目录迁移复验通过，最终场景证据记录于 `output/p24-validation/release/`。开发集 SHA-256 `0eb5ce7db782d76678a60df28609128a514103da9a9a247299e584552843b0bc`，问题目录 SHA-256 `428427a19e16d60bf613ae51a3b1718cce553401ab4cfeee47d3fd90a2351fde`。本轮没有新增现场 ECU/商业工具成功声明。
- Windows/Ubuntu runtime-evidence 接入独立开发场景和上传，七 job 拓扑不变；Python 3.14 currency 保留。官方资料核对 AUTOSAR R25-11 与 NIST AI 600-1，具体选择和边界见 [P24 指南](p24-engineering-review-guide.md)，个人练习见 [学习记录](../learning/p24-evidence-review.md)。公开新版本不自动扩大现有 XML 4.3.0 子集支持。
- 状态：P24 implementing，本轮开发基线 local-accepted，待提交推送和独立远端验收。30 题参与开发，不是独立 held-out；固定指针不算自然语言检索，模型未运行。下一项为冻结开发基线后形成未参与规则调优的负例、加强对象级 gold 与严重度/检索分项计量并评估解释缺口；不标记 P24 整阶段完成，不提前切换 P25。首页、路线、总览和验收表同步。


### P24：中文 JSON 输出的兼容性补强

- 首次实现 `7d42b1b` 已推送，run `36414801501` 已触发。随后本机用 `PYTHONIOENCODING=ascii` 实际复现 `list-engineering-questions` 的 UnicodeEncodeError；这是补查发现，不归因于尚在执行的远端 CI。
- CLI 在输出流不能编码原文时改用 JSON Unicode 转义，保留数据内容、文件 UTF-8 和退出码；覆盖正常目录查询及拒答输出。新增专项后 13 组消费者测试通过，后续修复提交须自己的远端验收，不能继承首次实现运行结论。
- 修复后最终全量 296 tests：294 passed、2 environment skips，摘要 `output/p24-validation/tests-encoding-final/ci-test-summary.json`；13 组专项、Ruff 和 whitespace 通过。问题目录和开发 gold 未改变，最终远端仍重跑完整 30 题及迁移场景。
- 首轮 run `36414801501` 随后实际结论 failure；已读取日志，Windows runtime-evidence 在 `impact-acceptance` 的 CLI JSON 输出触发 cp1252 UnicodeEncodeError，和本机补查一致。该失败 run 不计 acceptance；修复提交 `92bf90a` 已推送，run `36415173355` 正在独立验收。


## P24：首批开发基线远端验收（2026-09-28）

- 实现 `92bf90ae777bc7fad83ea929e2c245a1bacae4cc` / [run `36415173355`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36415173355) 七 job 全部 success，两平台 30 题场景与上传均 success。已核对完整 head SHA 和每个 job/step，原始明细存于 `output/p24-validation/remote-ci.json`。
- 实际 job：core-contracts (windows-latest) `108904484624` success；runtime-currency `108904484894` success；core-contracts (ubuntu-22.04) `108904484973` success；runtime-evidence (windows-latest) `108905321693` success；runtime-evidence (ubuntu-22.04) `108905321722` success；controlled-rejections (ubuntu-22.04) `108905321749` success；controlled-rejections (windows-latest) `108905321898` success。
- Windows/Ubuntu 的 `Run engineering review development scenarios`、`Upload engineering review development evidence` 均 completed/success，产物 `engineering-review-Windows`、`engineering-review-Linux`；完整开发问题、来源重算和移除原目录后的 30 份迁移复验通过。首次 Windows cp1252 失败由最终实现修复，不使用失败 run 作为验收依据。
- 本轮消费者与开发基线 remote-accepted；P24 整阶段仍 implementing。下一项为在固定开发策略之后形成独立未参与调优负例、加强对象级 gold 与严重度/检索分项计量，再依据实际解释缺口决定可选模型。当前固定查询与拒答不声称自然语言推理能力；平台结果不替代个人学习验收。
- 本条与首页/路线/验收表是后续纯文档状态回填，使用 `[skip ci]` 提交推送；实现验收只引用上面的固定提交和 run，不把文档提交作为新实现验证。开发问题目录与 gold hash 保持上一条记录。


## P24：分项评测与策略冻结前验证（2026-09-29）

- 新增中英文词法问题目录检索 `search-engineering-questions`，只导航固定题，不自动回答自由文本断言。保留原 30 题目录 hash、`engineering-review-0.1` 与旧审查接口。
- 原开发基线另增增强 gold：影响对象/传播路径、精确规则位置、XML 周期前后值、完整未通过验收项及来源清单；检索、确定性、引用、严重度、条件比较与可选模型分别计量。
- 实际复现严重度漏洞：保留原引用、只将 Finding 摘要从 ERROR 改成 WARNING，旧 `validate_citations` 仍返回 passed。已增加所有许可范围来源 Finding 的严格复算比较，降级、遗漏、伪造摘要均拒绝；原正常/拒答契约保持兼容，不凭无等级 XML 发明 severity。
- 开发分项通过：目录 top-1/hit@3 17/17、无匹配 1/1；确定性 gold 30/30、引用 30/30；ERROR/缺失等级保真 2/2、摘要篡改拒绝 3/3；合成缺失构建项目的源码提交变化和 timeout 变化比较 2/2 not-comparable。证据 `output/p24-assessment-validation/development-final/`。首轮评分器错误读取顶层 reasons，已按既有 comparison basis 契约修正并复跑；这发生在负例形成之前。
- 全量 303 tests：301 passed、2 environment skips；定向审查/检索检查、47 schema、61 schema-bound examples、25 syntax-only examples、Ruff、36 文件 mypy、topology、pip check 与 whitespace 通过。全量摘要 `output/p24-assessment-validation/tests-freeze/ci-test-summary.json`。
- 当前阶段 P24 implementing，本轮开发部分 local-accepted。下一步立即冻结实际提交，再形成并预登记未参与调优的负例清单，按冻结 hash 执行；此时尚未声称独立负例或整阶段通过。形成规则和限定见 [评测制度](p24-evaluation-protocol.md)。个人学习仍单列。


## P24：冻结后负例首次验收（2026-09-29）

- 开发策略冻结提交 `249a7307ef7b0db96c09c65a5187d5bd40f6e3f9`，该中间提交 `[skip ci]`，没有声称远端验收。随后形成并在首次执行前登记负例：提交 `6117b09e7ab80e7fdebca5a4654cdc4159f29a46`，清单 SHA-256 `5c880470f931e0f103c9648b1cd34e0242f50574a4e386b6f893e1947f53df24`，绑定 154 个运行源码、评测/生成脚本、开发 gold 和公开输入文件。
- 首轮结果：9/9 完整性拒绝、3/3 范围拒答、12/12 迁移复验；三个新目录查询 top-1/hit@3 3/3、两个无匹配查询 2/2。每例原输入 hash、实际退出码、结果和分类保存在 `output/p24-assessment-validation/held-out-first/`，同级 `held-out-first-summary.json` 保存完整冻结记录。消费者、排序、评分器、gold 和阈值均未据结果调整。
- 独立性范围：在冻结后形成且未参与调优，复用公开项目家族、同一维护过程编写，不称第三方盲测/客户样本/物理 ECU。案例具体变化见[评测制度](p24-evaluation-protocol.md)；不把原开发负例改名成新负例。
- 已推送，独立七 job run `36451604309` 正在执行；本轮尚未 remote-accepted。正在从全新目录复跑开发 + 分项 + 冻结负例的完整命令，P24 仍 implementing；通过后整阶段按受限范围冻结，并进入[既定 P25 交付计划](p25-reproducible-delivery-plan.md)，下一项为安装后两项目及故障竖切。


### P24：整阶段远端验收与 P25 交接（2026-09-29）

- 实现 `6117b09e7ab80e7fdebca5a4654cdc4159f29a46` / [run `36451604309`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36451604309) 七 job 全部 success；Windows/Ubuntu 开发场景、分项评测及证据上传均 success。
- 实际 job：runtime-currency `109027461487` success；core-contracts (ubuntu-22.04) `109027461885` success；core-contracts (windows-latest) `109027461986` success；controlled-rejections (ubuntu-22.04) `109028565371` success；runtime-evidence (ubuntu-22.04) `109028565462` success；runtime-evidence (windows-latest) `109028565486` success；controlled-rejections (windows-latest) `109028565536` success。
- 两平台 `Assess engineering review components` 与 `Upload engineering review assessment` 均 success；实际记录 `output/p24-assessment-validation/remote-ci.json`。
- 从头生成来源后的完整本地重放 `output/p24-assessment-release/assessment/summary.json` passed。开发确定性/引用各 30/30，严重度 2/2、摘要篡改拒绝 3/3、条件比较 2/2；冻结后完整性拒绝 9/9、越界拒答 3/3、迁移 12/12。未在首次负例执行后调优代码或 gold。
- 全量 303 tests：301 passed、2 环境跳过；完整检查口径见 P24 验收表。负例同维护者、共享公开来源家族，不宣称第三方盲测；模型未运行。
- P24 在固定问题与词法目录导航范围完成，当前主阶段切换 P25 planned；下一项为 wheel 隔离安装后在仓库外运行车窗、ThermalControl 与配置故障/影响/审查复验。
- 本次后续文档状态提交使用 `[skip ci]`；实现验收仍绑定 `6117b09`，不把文档提交当作另一次实现验收。


### P25：安装后完整项目交付验证（2026-09-29）

- 新增 `scripts/check_installed_projects.py`：构建 wheel 和平台适配 CAN 依赖 wheelhouse，在仓库外创建干净 venv；清除 PYTHONPATH/PYTHONHOME，验证 installed module 与解释器 prefix，offline 安装并执行 pip check。
- 全部工程步骤使用安装后的 workbench；仅旧审查引用重放使用该解释器调用已有验证接口。车窗/ThermalControl 正常通过，真实 DBC 缩放变更引发静态失败并阻止通信；影响只命中 thermal-status，比较为 regressed。原目录移走后复验三组项目库存、三组审查引用及影响/比较/工程答案。
- 保留 wheelhouse、输入、85 个迁移证据文件、commands/stdout/stderr/退出码与耗时、运行环境和 SHA-256；本地首次成功 `output/p25-installed-network/summary.json`，自动流程 40.799 秒，不计成人工十分钟演示。最初 sandbox 下载被代理网络限制拒绝，批准联网重跑后成功；不伪称首次环境运行成功。
- 新增四项保护测试：隔离来源拒绝、样例包完整性及单文件变更、故障注入位置不存在拒绝、保留已有输出；CI topology 同步两个新步骤，双平台 runtime-evidence 上传完整交付归档。
- 增加 Windows/Linux 安装与复跑指南及英文 README；P24 已冻结源代码和 gold 不变。当前 P25 implementing，本轮 local-accepted；远端、离线复用与全量最终计数待下条验收回填。人工演示、能力映射和真实外部反馈未验收。


### P25：安装后双平台远端验收（2026-09-29）

- 实现 `911abc0e4e59d76fc72265fc73a75aea5b09c28a` / [run `36586481411`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36586481411) 七 job 全部 success；Windows/Ubuntu 的安装后双项目验证及完整归档上传均 success。
- 实际 job：runtime-currency `109468069349` success；core-contracts (windows-latest) `109468069706` success；core-contracts (ubuntu-22.04) `109468069735` success；runtime-evidence (ubuntu-22.04) `109469142697` success；runtime-evidence (windows-latest) `109469142705` success；controlled-rejections (ubuntu-22.04) `109469143026` success；controlled-rejections (windows-latest) `109469143214` success。
- 两平台 `Verify installed multi-project delivery` 和 `Upload installed multi-project delivery` 均 success；实际记录 `output/p25-validation/remote-ci.json`，CI artifact 为 `installed-projects-Linux` 与 `installed-projects-Windows`，保留 wheelhouse/完整命令/输入/工程证据。
- 本地从归档依赖再次离线安装并完整复跑通过：`output/p25-installed-offline/summary.json`，24.905 秒，85 个 portable 文件；首次联网准备成功运行 40.799 秒。均不是人工演示时长。
- 全量 307 tests：305 passed、2 环境跳过；47 schema、61 schema-bound examples、25 syntax-only examples、Ruff、新脚本默认/Windows-target mypy、topology 与 whitespace 通过。远端 scoped type gate 与 Python 3.14 回归亦通过。
- 完成 Windows/Linux 交付指南、英文入口、能力证据对应、待实测演示脚本和安装交付学习练习。平台实现和个人独立掌握分别记录。
- 当前主阶段仍 P25 implementing；安装后交付门 remote-accepted。下一项为真实操作者人工演示实测与外部使用/投递反馈，模板已提供，未取得前不以代理自测替代或标记整阶段完成。不自动联系他人或发布外部贡献。
- 本条及验收/首页/路线回填为后续纯文档 `[skip ci]` 提交；实现验收始终绑定 `911abc0` / `36586481411`，不把文档提交算作实现 CI。


### P26：真实 ECUC 项目体检首轮实现（2026-09-30）

- 用户授权基于本地工程分析继续升级，新增 P26 用户能力阶段；P25 人工门保留未完成，当前唯一代码主线为 P26。本地工程及分析/快照只存忽略目录，未上传。
- 新增 `inspect-ecuc-project` / `verify-ecuc-inspection`，按 DPA 文件与 collection 模块选择读取配置，输出来源 hash、XML/对象定位、容器/引用计数与五类结构发现；独立版本 0.1 不扩大原 SWC ARXML 契约声明。
- 快照支持原路径移除后重算，结论/来源/额外库存篡改拒绝。外部定义与实例引用明确 unassessed，不把结构检查当厂商 XSD、生成或硬件验收。
- 合成正常/未绑定/缺引用/歧义四场景及迁移、篡改拒绝已本地通过；真实本地输入的模块识别和未绑定任务发现已复核，细节保持本地。
- 源码变化后 P24 冻结不重写：新增明确 `--historical-regression`、报告 0.2 与当前源码 hash，原 strict held-out 仍要求原冻结；原负例清单不改，当前结果不冒充独立测试。
- 全量/历史回归及本实现远端 CI 待完成；通过后下一项为真实引用驱动的通信跨层链。指南与学习练习同步新增。


### P26：首轮体检验收补全（2026-10-01）

- 延续工作区已有首轮实现，补齐引用定位的 REFERENCE-VALUES 序号和损坏报告的受控输入错误；严格 P24 0.1 输出字段保持，历史回归另用 0.2。
- 最终本地全量 316 tests：314 passed、2 环境跳过；定向 ECUC 9/9、公开四场景、原输入删除后的四份迁移复验和篡改拒绝全部通过。证据 `output/p26-validation-20261001/`；第一次场景命令因旧输出非空而按设计拒绝，改用新目录复跑，未覆盖旧证据。
- 48 schema、61 schema-bound examples、25 syntax-only examples、Ruff、39-source scoped mypy、CI topology、pip check 和 whitespace 通过。完整 P24 开发/历史负例正在从头重建来源；当前无新增独立负例声明。
- 本轮实现准备提交推送，七 job 远端待执行；未标记 remote-accepted。下一项仍为首轮验收完成后连接真实 VALUE-REF 通信跨层链。P26 整阶段 implementing；P25 人工门保留。

- 首轮实现 `84b5469372ca48da1549716211daab06af2bfef4` / run `36742954252`：Ubuntu core 与 Python 3.14 success，Windows core 失败、下游 skipped。实际原因为新增测试读取含中文负例清单时未显式指定 UTF-8，Windows cp1252 解码失败；已修正新增测试与场景脚本的文本读取，等待修复提交自己的 CI，不以失败 run 验收。
- 完整本地 P24 重放已通过：30/30 开发 gold/引用/迁移，历史完整性拒绝 9/9、范围拒答 3/3、迁移 12/12，目录检索与严重度分项全部通过；`assessment/summary.json` 明确版本 0.2、`freeze_verified: false`。


### P26：项目感知体检首轮远端验收（2026-10-01）

- 最终实现 `c6320d503d3d704bdce5d64e294dc84811444e0c` / [run `36813404620`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36813404620) 七 job 全部 success；已核对完整 head SHA。首轮失败记录保留，修复后的验收不引用失败 run。
- 实际 job：runtime-currency `110213164930` success；core-contracts (windows-latest) `110213165047` success；core-contracts (ubuntu-22.04) `110213165203` success；controlled-rejections (windows-latest) `110213917490` success；runtime-evidence (windows-latest) `110213917561` success；runtime-evidence (ubuntu-22.04) `110213917610` success；controlled-rejections (ubuntu-22.04) `110213917630` success。
- Windows/Ubuntu 的 `Run ECUC project inspection scenarios`、`Upload ECUC project inspection evidence` 与 `Assess engineering review components` 均 success；归档 `ecuc-inspection-Windows`、`ecuc-inspection-Linux`，完整 job/step 记录 `output/p26-validation-20261001/remote-ci.json`。
- 本轮仅项目感知体检门 remote-accepted，P26 整阶段 implementing。下一项为真实 VALUE-REF 驱动的 Com → EcuC/PduR → CanIf → Can 通信跨层定位；P25 人工门及商业/物理 ECU 限制保持。详见 [P26 验收表](p26-acceptance.md)。
- 修复推送曾遇 TLS 连接中断，重试成功，无待恢复环境阻断。本条及首页/路线为后续纯文档状态提交，使用 `[skip ci]`；实现验收固定引用 `c6320d5` / `36813404620`，文档提交不算新实现 CI。


### P26：通信跨层引用链实现（2026-10-01）

- 新增 `trace-ecuc-communication` / `verify-ecuc-communication` 与闭合 `ecuc-communication-0.1`。从模块定义上下文、实际 VALUE-REF 和子容器关系连接 Com、EcuC Pdu、PduR 路由两端、CanIf Tx/Rx、Buffer/HTH/HRH、Can 硬件对象及控制器；不以对象名/后缀推断连接或方向。
- ComIPduDirection 与 CanObjectType 校验方向；支持普通信号和组信号成员、多目标分支。重复身份、缺引用、错误类型、必需引用数量、条件配置及多 CanIf 配置选择歧义均保留 partial；零支持路径为 no-paths。未知字段/实例引用和未解释容器显式列出。
- 共用项目解析器，旧体检 0.1 输出契约保持；已有旧快照实际复验通过。新报告从源快照重算全部结论，移除原输入后九场景复验及三类篡改拒绝通过。
- 公开输入均为独立合成 fixture；本地工程真实导出已完成链路解析，细节和报告只存忽略目录。本次不运行厂商工具/生成器，不声称商业或物理 ECU 验收。
- 定向 ECUC 20/20、九场景和迁移/篡改通过；49 schemas、61 bound examples、25 syntax-only examples、Ruff 与 topology 通过。本地全量 327 tests：325 passed、2 环境跳过；41-source mypy 与 pip check 通过。真实本地快照由最终实现重算复验 passed。证据 `output/p26-chain-validation/`；本轮 local-accepted，远端待本实现 CI，尚未标记 remote-accepted。新增指南、字段官方来源和独立学习练习。
- 下一项先完成本轮七 job，再推进应用/OS/RTE 调度集成缺口解释；P26 整阶段 implementing，P25 人工门保持。


### P26：通信跨层定位远端验收（2026-10-01）

- 实现 `b6718640364104153490adbbd2d876f3172887c2` / [run `36817127099`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36817127099) 七 job 全部 success；已核对完整 head SHA 与每个 job/step。
- 实际 job：core-contracts (ubuntu-22.04) `110224525142` success；runtime-currency `110224525348` success；core-contracts (windows-latest) `110224525358` success；runtime-evidence (windows-latest) `110225127147` success；runtime-evidence (ubuntu-22.04) `110225127156` success；controlled-rejections (windows-latest) `110225127231` success；controlled-rejections (ubuntu-22.04) `110225127233` success。
- Windows/Ubuntu 的 `Run ECUC communication chain scenarios`、`Upload ECUC communication chain evidence`、`Assess engineering review components` 均 success，新增 artifact 为 `ecuc-communication-Windows`、`ecuc-communication-Linux`。完整明细 `output/p26-chain-validation/remote-ci.json`。
- 本地全量 327 tests：325 passed、2 环境跳过；九场景、9/9 删除原输入后的迁移复验、3/3 篡改拒绝；49 schema、61 bound/25 syntax-only examples、41-source mypy、Ruff、topology、pip check 通过。旧 0.1 报告及本地真实快照由最终实现复验通过；真实工程内容没有提交或进入 CI。
- 本轮通信结构链门 remote-accepted。下一项为应用/OS/RTE 调度集成缺口解释，随后两版 ECUC 配置影响；P26 整阶段仍 implementing，P25 人工门、商业生成与物理 ECU 证据边界保持。
- 本条及首页/路线/验收表为后续纯文档状态回填，使用 `[skip ci]` 提交；实现验收固定引用 `b671864` / `36817127099`，文档提交不算新实现 CI。


### P26：工程审查与配置影响整阶段实现（2026-10-01）

- 按用户“做大阶段”要求合并完成既定第 3、4 项：`review-ecuc-project`/`verify-ecuc-review` 与 `compare-ecuc-reviews`/`verify-ecuc-impact`。应用输入显式声明；检查组件实例/类型、ASW/BSW 事件到任务、BswM 引用及环；日志只保存历史未绑定观察和精确对象关联。
- 两版快照按完整对象身份比较，保留参数/引用/增删及不透明变化，经两侧真实依赖边追踪通信路径、任务映射和模式规则；重复身份 not-comparable，未知语义/读取范围改变 partial。JSON/HTML 和 before/after 原字节均可搬移后重算。
- 复用项目解析器和通信内核，原 0.1 体检/通信契约保持。新增两份独立闭合 schema；P24 继续历史回归，不重写原冻结声明。
- 十组公开 CLI 审查/比较、10/10 删除原输入后复验、4/4 篡改拒绝通过；专项 17/17。全量 344 tests：342 passed、2 环境跳过；51 schemas、47-source mypy、Ruff、topology 和 pip check 通过。
- 新增仓库外隔离 wheel 完整流程验收；初次脚本因 resolve 解释器 symlink 使用基础 Python 而失败，已改为保留 venv 启动路径并成功复跑，最终产物已归档 `output/p26-stage-validation/installed-final-code/`。未连接网络安装运行依赖，不把源码运行当安装验收。
- 本地真实工程执行审查与快照复验，未知应用/模式和未绑定任务保持缺口；输入和细节均未提交。为大工程缩减 HTML 原始库存重复展示，完整 JSON 保留全部证据。
- 本轮 local-accepted，七 job 远端待本实现提交；P26 尚未整阶段 remote-accepted。通过后按公开受限结构范围冻结 P26，主阶段进入已规划 P27；P25 人工/外部反馈及商业生成/物理 ECU 门仍未验收。

### P26：整阶段远端验收与 P27 交接（2026-10-01）

- 实现 `6433e1cdf360e07d4d09e9294922380f68730018` / [run `36864006903`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36864006903) 七 job 全部 success。
- `core-contracts (ubuntu-22.04)`：job `110374883543`，success。
- `runtime-currency`：job `110374883950`，success。
- `core-contracts (windows-latest)`：job `110374884005`，success。
- `controlled-rejections (ubuntu-22.04)`：job `110375922633`，success。
- `runtime-evidence (windows-latest)`：job `110375922719`，success。
- `runtime-evidence (ubuntu-22.04)`：job `110375922734`，success。
- `controlled-rejections (windows-latest)`：job `110375922772`，success。
- Windows/Ubuntu 的 ECUC engineering scenarios、installed workflow、evidence upload 三步骤均 success；实际记录 `output/p26-stage-validation/remote-ci.json`，归档 `ecuc-engineering-Windows` / `ecuc-engineering-Linux`。既有工程审查历史回归也随本实现通过。
- 最终本地 344 tests：342 passed、2 环境跳过；17/17 专项、51 schema、47-source mypy、Ruff、topology、pip check 通过。隔离 wheel 的十场景、10/10 迁移、4/4 拒绝及最终副本复验通过。真实本地工程 15,694 对象、621 通信路径、99 任务映射，复验 passed；应用/模式输入缺口保持 unassessed。HTML 595,018 字节，完整对象证据保留于 JSON；私有输入未提交。
- P26 四项静态能力按公开受限范围 remote-accepted；厂商生成、可调度性、商业往返及物理 ECU 未验收，P25 人工演示/外部反馈保留。当前主阶段切换 P27 planned；下一项冻结声明式 ECUC 项目契约并贯通正常/缺口两路径。
- 本条及总览/路线为后续纯文档 `[skip ci]` 状态提交，不作为新的实现验收；固定引用 `6433e1c` / `36864006903`。

### P27：声明式 ECUC 配置变更验收整阶段实现（2026-10-02）

- 新 workbench-project/project-acceptance 0.6 接入 `run-project`，复用 P26 捕获/审查/影响内核；一次冻结基线和候选原字节，不开 CAN、不执行生成。旧 0.1–0.5 保持，新增比较 0.3 容纳 unassessed。
- 通信/应用/任务/模式/影响五个显式检查；通过条件固定为 passed，不允许将 unknown 设为接受目标。只聚合声明项；失败/阻塞/未评估均阻止接受。没有应用输入时任务关联保留 unassessed；历史日志独立，不当当前故障。
- 完整集成与精简单 Tx 两工程无需内核分支；八场景覆盖正常、任务/通信缺口、未知字段、应用缺失、重复身份及历史日志。项目/阶段/来源/策略均可重算，来源移除和整树二次搬移后的审查/比较复验；四类 CLI 篡改拒绝。
- 新 `verify-ecuc-project`、来源检查接入项目审查/比较；每项保留来源指针和影响对象。重算拒绝只修改结论并重新计算哈希的伪造；不提供签名或外部来源身份认证。
- 开发中初次场景和安装检查因旧审查契约要求标量断言而失败，改为逐条对象和证据路径引用，完整数组留在阶段 JSON；一次源码场景跨越规则修改导致复验不一致，最终固定代码后全流程重跑。最终测试/安装与远端结果待下条回填。
- 指南、独立练习、验收表和下一阶段 P28 对象级策略计划同步。当前 P27 implementing，不沿用 P26 的 CI 结论，也不代替 P25 人工或商业/物理门。

- 最终本地验收：359 tests（357 passed、2 环境跳过），15 项专项；52 schemas、63 bound examples、25 syntax-only examples、49-source mypy、Ruff、topology、pip check 全通过。最终隔离 wheel 八场景、8/8 项目迁移复验与审查、4/4 篡改拒绝、项目回归比较和第二次搬移复验通过，证据 `output/p27-validation/installed-release/summary.json`。本轮 local-accepted，待固定实现的七 job。

### P27：整阶段远端验收与 P28 交接（2026-10-02）

- 实现 `55e208fffe6d51c233ff30d3604bafd992dfb080` / [run `36901660485`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36901660485) 七 job 全部 success。
- `runtime-currency`：job `110502049757`，success。
- `core-contracts (ubuntu-22.04)`：job `110502050094`，success。
- `core-contracts (windows-latest)`：job `110502050316`，success。
- `controlled-rejections (ubuntu-22.04)`：job `110503465830`，success。
- `runtime-evidence (windows-latest)`：job `110503465846`，success。
- `runtime-evidence (ubuntu-22.04)`：job `110503465924`，success。
- `controlled-rejections (windows-latest)`：job `110503466190`，success。
- Windows/Ubuntu 的 declarative ECUC project scenarios、installed ECUC project acceptance、evidence upload 三步骤均 success；原始记录 `output/p27-validation/remote-ci.json`，artifact 为 `ecuc-projects-Windows` / `ecuc-projects-Linux`。旧项目/ECUC 场景、安装流程和工程审查历史回归也随本实现通过。
- 最终源码八场景、8/8 原输入删除与迁移复验、8/8 审查、回归比较、4/4 拒绝及整树二次搬移通过，见 `output/p27-validation/scenarios-release/summary.json`；安装证据 `installed-release/summary.json`，完整回归 359 tests（357 passed、2 环境跳过）。
- P27 按声明式静态验收范围 remote-accepted；当前下一主阶段 P28 planned，先冻结精确对象选择与不可变条件，连接具体信号参数/任务引用变更与接受策略。商业工具生成、实时调度、物理 ECU 和 P25 人工门未验收。
- 本条及总览/路线为后续纯文档 `[skip ci]` 状态提交，固定引用实现 `55e208f` 与 run `36901660485`；文档提交不计作新的实现验收。


### P28：对象级配置保护策略实现（2026-10-02）

- 新项目/报告 0.7 与阶段 0.2，旧 0.1–0.6 保持。完整身份选择对象和字段，前后结构存在/完整及参数或引用不可变；每条策略强制参与接受。
- 两侧实际值、对象/字段/依赖见证进入可重算阶段报告和审查断言；策略哈希纳入比较基础，策略变更不得伪装同策略回归。未知范围采用保守阻断，不能从未出现在影响列表推断安全。
- 两套合成工程复用同一内核；16 CLI 场景包含信号位宽/有效任务改绑拒绝、两工程允许变化、缺对象、未知字段、重复身份及策略漂移。安装/迁移/审查/比较沿用既有消费者。
- 开发验证发现前后影响对象重复列出，已去重；歧义场景同时存在其他失败时聚合沿用 failed 优先，改为独立验证歧义保护项的 blocked 状态。最终结果待后续回填。
- 当前 implementing，下一步完成全量检查、最终场景、仓库外安装及本实现远端七 job。P25 人工门、商业生成/物理 ECU 保持未验收。

- 最终本地：374 tests（372 passed、2 环境跳过），15 项对象策略专项；52 schema/65 bound/25 syntax-only、50-source mypy、Ruff、topology、compileall、pip check 通过。源码与隔离 wheel 各 16 场景、16/16 迁移复验与审查、4/4 篡改拒绝，通信/信号/任务回归及策略漂移比较和再次搬移均通过。最终证据 `output/p28-validation/scenarios-final/`、`installed-final/`，源码复制归档后的项目与比较复验通过（38/38 引用）。
- 全量回归发现非法版本列表触发 TypeError，已恢复受控拒绝；场景脚本修正既有 not-comparable 退出码为 2；大小写不同策略的审查断言增加稳定区分，专项通过。最终固定代码重跑，不使用开发中旧快照代替验收。
- 本轮 local-accepted；下一步推送固定实现并记录真实七 job。通过后按当前受限静态保护范围冻结 P28，进入已规划[P29 配置验收与运行证据关联](p29-configuration-runtime-plan.md)。


### P28：整阶段远端验收与 P29 交接（2026-10-02）

- 实现 `2269714e6895f6e1d3c2b7276e034b61262ea33b` / [run `37025748404`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37025748404) 七 job 全部 success。
- `core-contracts (windows-latest)`：job `110899801407`，success。
- `core-contracts (ubuntu-22.04)`：job `110899801439`，success。
- `runtime-currency`：job `110899801460`，success。
- `controlled-rejections (ubuntu-22.04)`：job `110901007087`，success。
- `runtime-evidence (ubuntu-22.04)`：job `110901007261`，success。
- `controlled-rejections (windows-latest)`：job `110901007278`，success。
- `runtime-evidence (windows-latest)`：job `110901007366`，success。
- Windows/Ubuntu 的 `Run object policy acceptance scenarios`、`Verify installed object policy acceptance`、`Upload object policy acceptance evidence` 三步骤均 success；已核对完整 head SHA 与每项结论。原始记录 `output/p28-validation/remote-ci.json`，归档 `ecuc-policies-Windows` / `ecuc-policies-Linux`。
- 最终本地 374 tests（372 passed、2 环境跳过），15 项对象策略专项；源码和隔离安装各 16 场景、16 迁移复验/审查、4 篡改拒绝、通信/信号/任务回归与策略漂移比较及再次搬移通过。52 schema、65 bound/25 syntax-only、50-source mypy、Ruff、topology、compileall、pip check 通过。
- P28 按精确对象存在/受限结构及字段不可变范围 remote-accepted。下一主阶段 P29 planned，先冻结已有通信/诊断路径与配置策略的显式身份绑定。P25 人工反馈、商业生成、可调度性及物理 ECU 门仍待真实证据，不等同本人能力已掌握。
- 本条及首页/路线/验收表为后续纯文档 `[skip ci]` 回填，固定引用实现 `2269714` / run `37025748404`，文档提交不作为新实现 CI。


### P29：配置接受与同次 CAN 证据关联实现（2026-10-03）

- 新项目/报告 0.8、ECUC 阶段 0.3、带上下文的 P20 运行报告 0.2；旧 0.1–0.7 保留。复用既有 CAN 执行内核，显式绑定保护策略、精确信号、通信路径三元组、向量、方向及候选 CanIf 地址。
- 静态失败或任一映射无法判断时整份运行计划不打开总线；保留失败/blocked/unassessed 原因。候选、策略、三个运行输入与运行标识绑定，记录执行条件及工具版本；重放重新核对计划、原始帧、解码、清理与汇总，不重跑总线。
- 完整 Tx/Rx 与单 Tx 两工程；八类场景加同配置第二次执行，9 份迁移复验与审查，通信失败回归及映射漂移不可比较，五类篡改拒绝、删除原输入与再次搬移。隔离 wheel 使用 CAN 依赖；依赖准备与 --no-index 安装分开记录。
- 验证中纠正比较既有结果名 stable、增加 schema 固定计数 53，并补强执行计划漂移不能被覆盖、JSON bool/int 严格区分。最终结果待下条回填。
- 本机 vcan0 原先不存在，已用现有 setup_vcan.sh --apply 幂等恢复；带通道锁双工程 SocketCAN 运行/审查/比较通过，最终复验及远端门待回填。公开输入仅合成 fixture；现场是 vcan0 本地两端，不是独立 OpenBSW 或物理 ECU。
- P29 保持 implementing；CAN 门通过后继续同阶段独立 ECU 诊断绑定。P25 人工门、商业生成与物理 ECU 证据不由本轮替代。

- 最终本地：385 tests（383 passed、2 环境跳过），11 项新增运行关联测试；53 schema、71 bound/25 syntax-only、52-source mypy、Ruff、topology、compileall、pip check 全通过。最终源码与隔离 wheel 各 9 份运行/迁移复验/审查、5 类篡改拒绝、失败回归/映射漂移/重复运行比较及再次搬移通过；证据 `output/p29-validation/scenarios-release/`、`installed-release/`。
- SocketCAN vcan0：完整工程 Tx/Rx 2/2、单 Tx 1/1，持有现有通道锁；两工程审查通过，最终代码离线复验通过，比较引用分别 50/50、22/22；`socketcan/summary.json` 与 host probe/全部报告已归档。源码临时目录移除后的最终归档复验 50/50 通过。
- CAN 关联门 local-accepted；等待本实现提交与七 job。P29 整阶段仍 implementing，下一门为独立 ECU 诊断身份/配置策略关联，未用本轮本地端点替代。


### P29：CAN 关联门远端验收（2026-10-03）

- 实现 `b2da1472f82a6aceebe43efdfb477ceb4e1896fa` / [run `37091771686`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37091771686) 七 job 全部 success；已核对完整 head SHA 与各 job 最终结论。
- `runtime-currency`：job `111113435766`，success。
- `core-contracts (ubuntu-22.04)`：job `111113436033`，success。
- `core-contracts (windows-latest)`：job `111113436055`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111113984160`，success。
- `controlled-rejections (windows-latest)`：job `111113984206`，success。
- `runtime-evidence (windows-latest)`：job `111113984218`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111113984223`，success。
- Windows/Ubuntu 的 `Run configuration runtime link scenarios`、`Verify installed configuration runtime links`、`Upload configuration runtime link evidence` 全部 success；归档 `ecuc-runtime-links-Linux` / `ecuc-runtime-links-Windows`，原始记录 `output/p29-validation/remote-ci.json`。
- 最终本地 385 tests（383 passed、2 环境跳过）；源码与隔离安装各 9 份结果和 5 类篡改拒绝；vcan0 完整工程 Tx/Rx 2/2、单 Tx 1/1，审查/比较及搬移复验通过。CAN 门按显式声明映射范围 remote-accepted，P29 整阶段仍 implementing。
- 下一项为独立 ECU 诊断关联：复用 P23 生命周期，将静态保护策略与同次只读诊断验收建立显式依赖；没有 Dcm/CanTp 或生成来源的配置到代码语义不得推断为通过。检查现有 P23 构建清单发现原执行文件、cache 及三个源码角色路径已不存在，两个构建日志仍在且哈希一致。现场恢复需重建固定提交并生成新的构建清单，不能复用历史 CF01 成功充作本轮执行。
- 本条及首页/路线/验收表为后续纯文档 `[skip ci]` 状态提交，固定引用 `b2da147` / `37091771686`，不作为新实现 CI。P25 人工验收、商业工具生成和物理 ECU 仍未验收。


### P29：独立 ECU 诊断依赖实现（2026-10-04）

- 新项目/报告 0.9、ECUC 阶段 0.4；旧 0.1–0.8 保持。已有对象保护策略作为只读诊断验收的显式依赖；不推断 Dcm/CanTp 配置或生成代码关系，configuration-semantic 请求保持 unassessed。
- 静态拒绝、声明身份无法匹配与后端不匹配时不启动 ECU。通过后复用 P23 独立 ECU/client、通道锁、固定构建哈希、超时和清理；原始结果保留。
- 独立执行与诊断客户端分别产生 0.2 上下文报告，绑定项目/基线/候选/策略/执行输入及 run_id；执行工具版本与构建工具分别保存。复验不重跑总线，比较条件改变保持 not-comparable。
- 固定 OpenBSW 源码在独立副本重新构建成功，原始开发目录未修改。现场是 POSIX/vcan0，合成 ECUC 没有生成该二进制，不属于物理 ECU 验收。
- 两套公开合成项目，离线七场景、现场十场景；来源移除、审查、比较、二次搬移及篡改拒绝。首轮场景脚本使用错误审查子命令已修正；离线 blocked→failed 的总体比较按既有契约为 changed，现场 passed→failed 为 regressed，未为新案例改变旧比较语义。
- 初轮全量 393 tests：391 passed、2 环境跳过。后续补强客户端上下文与成功响应复验，最终验证结果另行回填，未沿用初轮结果作为最终验收。
- P29 保持 implementing。其后主阶段计划为 P30 基于项目证据的本地模型解释，先解决引用修补问题并保留判定权；硬件尚未取得，台架为后续条件门。P25 人工演示/真实反馈仍待取得。

- 最终本地：395 tests（393 passed、2 环境跳过）；8 项配置诊断测试及 2 项客户端上下文测试。54 schemas、76 bound/25 syntax-only、54-source mypy、Ruff、topology、compileall、pip check 全通过。离线与隔离安装各 7 场景/7 审查/5 类拒绝；固定 OpenBSW 现场 10 场景/10 审查/7 类拒绝，含客户端历史替换和成功响应篡改。原输入移除、二次搬移及最终归档 17 份项目/6 份比较复验、83 份相关 schema 实例验证通过。证据 `output/p29-diagnostic-validation/`（`offline-release/`、`installed-release/`、`live-release/`、`archive-verification.json`）。诊断门 local-accepted，等待固定实现提交的七 job；不沿用 CAN 门的旧 CI。


### P29：独立诊断远端验收与 P30 交接（2026-10-04）

- 实现 `654cd8fb907f79d69f3ad2636b8f222e5d1bb0b1` / [run `37166161292`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37166161292) 七 job 全部 success；已核对完整 head SHA 与全部作业结论。
- `core-contracts (windows-latest)`：job `111329362700`，success。
- `core-contracts (ubuntu-22.04)`：job `111329362821`，success。
- `runtime-currency`：job `111329362844`，success。
- `runtime-evidence (windows-latest)`：job `111329897458`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111329897466`，success。
- `controlled-rejections (windows-latest)`：job `111329897476`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111329897495`，success。
- Windows/Ubuntu 的 `Run configuration diagnostic link scenarios`、`Verify installed configuration diagnostic links`、`Upload configuration diagnostic link evidence` 全部 success；原始记录 `output/p29-diagnostic-validation/remote-ci.json`，artifact 为 `ecuc-diagnostic-links-Windows` / `ecuc-diagnostic-links-Linux`。
- 最终本地 395 tests：393 passed、2 环境跳过；54 schemas、76 bound/25 syntax-only、54-source mypy、Ruff、topology、compileall、pip check 通过。离线与隔离安装各 7 场景/7 审查/5 类篡改拒绝；安装为离线无额外依赖路径，不冒充安装后的现场诊断。
- 固定源码在独立干净副本重新构建，现场 10 场景/10 审查/7 类篡改拒绝；六次实际诊断的父/子上下文、不同进程 PID、通道锁与清理已核对，三次正常执行包含 SF/FF/FC/CF。最终原树移除后的归档 17 项项目、6 项比较、83 份相关 schema 验证通过；证据 `live-observations.json` 与 `archive-verification.json`。
- P29 按显式 CAN 映射及独立诊断验收依赖范围 remote-accepted。配置生成代码语义缺证据仍 unassessed；真实 ECU 身份、物理硬件、商业生成及可调度性不在已验收范围。
- 下一主阶段 P30 planned，先固定只读解释与引用校验；现有本地知识助手可复用，但不能将无效引用自动补成受支持结论。P25 人工演示/外部反馈保持未完成，硬件台架按设备取得后另验收。
- 本条及首页/路线为后续纯文档 `[skip ci]` 状态提交，固定引用实现 `654cd8f` / run `37166161292`；文档提交不作为新实现验收。


### P30：只读事实门实现（2026-10-04）

- 首轮实现项目 0.6–0.9 的只读请求与精确事实选取校验。复用项目完整复验和确定性审查，固定报告/来源哈希、JSON pointer、类型化值、问题与策略身份；不导出完整 ECUC 文件。
- 每次回答校验重建请求；无效引用不修补，状态/数值/对象值必须逐字按 JSON 类型一致。拒绝自由文本附加断言、跨请求/历史运行替换、请求/依赖篡改与重复 JSON 字段。通过仅表示事实选取有效，保留原项目状态和回答 unassessed，不宣称问题已回答或自然语言事实正确。
- 两工程 CLI 场景、中文空格路径、输入移除、搬移和隔离无依赖 wheel 场景已加入双平台 CI；本地最终与远端验收结果待回填。
- P30 保持 implementing，模型未接入；下一项 Ollama/现有知识助手适配、服务不可用回退、项目/资料来源分离和开发/独立问题评测。P25 人工门仍待完成。

- 首轮 local-accepted：全量 400 tests（398 passed、2 环境跳过）；新增类型/身份负例后 P30/topology 定向 9 tests 通过。56 schemas、76 bound/25 syntax-only、57-source mypy、Ruff、topology、pip check、whitespace 通过。源码与无依赖隔离安装各两工程、8 类 CLI 拒绝与归档复验通过。首次安装脚本错误解析 venv Python 符号链接，已保留原可执行路径并重跑成功。验收范围见[P30 验收表](p30-acceptance.md)，远端门待本次实现提交。


### P30：只读事实门远端验收（2026-10-04）

- 实现 `a82ee62c758c82741aa083636744b5c6766892a3` / [run `37183484781`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37183484781) 七 job 全部 success；Windows/Ubuntu 事实场景、隔离安装、证据上传均 success。
- `runtime-currency`：job `111380561415`，success。
- `core-contracts (windows-latest)`：job `111380561531`，success。
- `core-contracts (ubuntu-22.04)`：job `111380561539`，success。
- `runtime-evidence (ubuntu-22.04)`：job `111381028146`，success。
- `controlled-rejections (ubuntu-22.04)`：job `111381028182`，success。
- `runtime-evidence (windows-latest)`：job `111381028187`，success。
- `controlled-rejections (windows-latest)`：job `111381028195`，success。
- 原始记录 `output/p30-fact-validation/remote-ci.json`；artifact `project-explanation-Windows` / `project-explanation-Linux`。本轮新增六项 P30 单元测试纳入双平台与 Python 3.14 回归；源码与隔离安装的两工程/8 类 CLI 拒绝/搬移复验通过。
- 首轮按只读事实选取范围 remote-accepted。P30 整阶段 implementing；下一项 Ollama/现有知识助手适配、身份与原始输出记录、服务缺失回退及独立问题评测。P25 人工反馈仍待取得。
- 本条及首页/路线/验收表属于后续纯文档 `[skip ci]` 状态提交，引用 `a82ee62` / `37183484781`，不作为新实现 CI。


### P30：本地模型适配、缺口识别与资产复用（2026-10-04）

- 新增 explain-project / verify-model-explanation，复用已复验事实包；原 Ollama / 知识助手原文接口只读接入，绕开聊天引用补号。项目事实、手册摘录、语义未验证草稿和未执行建议分别保存。
- 固定输入、原始 HTTP/模型响应、提示版本、模型 digest 前后核对、服务版本、耗时与返回 token 指标。服务缺失、HTTP 超时、非法引用、字段/状态/数值改写、未审核资料、模型漂移和截断均保留回退或拒绝；离线重放不访问服务。
- 缺口分别记录项目未满足的门、上下文未选取、资料未请求/查询失败/无命中及模型/语义验收缺口，不从无命中推断整个知识库不存在资料。
- 盘点既有源码及 Docker，恢复原 Docker Desktop 与 Ollama/Qdrant/API 三容器，无下载模型、重建知识库或删除资产。23 份文档中 15 份可检索、4 份草稿待审核、1 份解析失败、3 份停用；保留 legacy_trusted 等原来源等级。Web/worker 保持停止。
- 源码和隔离安装协议夹具、单元/全量回归及真实模型开发调用执行中；最终结果、实现 SHA 和远端 CI 待回填。真实开发调用已暴露字段缺失、截断和双请求摘要歧义，原始失败保留，版本化提示改进不修补模型输出。
- 磁盘初查 C 剩约 59 GiB、D 剩约 47 GiB；已有 Docker 镜像约 9.409 GB、模型卷 5.27 GB、Qdrant 822.8 MB。无需为本次接入另下载模型或扩容；未挂载缓存/卷不自动当作垃圾删除。详细复用清单见[p30-reuse-inventory.md](p30-reuse-inventory.md)。
- P30 保持 implementing；下一项独立模型质量、资料适用性与人工可用性评测。P25 人工门及物理 ECU 仍未由本轮替代。


- 2026-10-05 最终本地 local-accepted：409 tests（407 passed、2 环境跳过），新增 8 项模型专项；57 schemas、76 bound/25 syntax-only、61-source mypy、Ruff、topology、pip check、whitespace 通过。最终源码/隔离安装各 12 个合成 HTTP 场景与 schema/离线复验/归档复验通过。
- 实际 Ollama 0.31.1 / qwen3.5:2b 6 次开发调用：1 个单事实结构化引用通过、5 次因字段、截断或引用问题拒绝；版本 0.4 单事实 18.886 秒，带手册 21.862 秒（摘录拒绝），缺证据 44.975 秒（引用拒绝）。失败记录保留，不修补返回文本，不视作模型独立评测或模型正确拒答。真实服务缺失的 blocked 回退另存，首轮提示各版本可重放。
- 适配工程门已 remote-accepted：`21a495e` / run `37264801076` 七 job success；Windows 归档 24 例在 Linux 复验通过。完整报告须同时保留 Docker/磁盘、现场成功和失败及剩余质量门，不宣称 P30 整阶段完成。

### P30 六类冻结评测入口（2026-10-06）

新增[评测指南](p30-model-evaluation-guide.md)、冻结问题及评分脚本，固定代码/证据/模型身份，在真实模型调用前核对 gold。将确定性复验、上下文覆盖、模型引用、检索逐字支持、模型拒答与校验器拦截分开记录；历史替换在推理前拒绝。四项评分/篡改边界测试通过，全量 413 tests（411 passed、2 环境跳过）；实现 `8735bc3b672bd4d95902fb5abcb431d88248efc1` / [run `37419810449`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37419810449) 七 job 全部 success。原 P24 gold 未改变。已有模型、镜像及只读 Python 依赖被复用，无新增下载；真实配对评测已完成：10 次推理均 refused，10 份归档复验通过，历史替换推理前拒绝。前三类 gold 未进上下文，诊断 gold 已进入但模型引用仍错。评测工具通过不等于模型质量通过；P30 整阶段仍 implementing。

下一项仍为 P30：版本化修正问题相关事实选择，优先纳入失败原因、精确影响对象与必要上下文；保留提示 0.1–0.4 的历史重放。随后针对结构化值、原文摘录和 unassessed 空引用约束改进输出，在新冻结问题上验收。当前六题已见，不再冒充后续未见测试；人工语义/资料适用性仍待验收。


### P30：问题相关事实、推理服务诊断与模型适用性（2026-10-08）

- 提示 0.5 优先点名检查/所问字段/影响对象及必要上下文，保持 24 条/12000 字符限制；事实 ID 与类型化原值成对约束，手册短摘录与 unassessed 空列表约束，独立严格校验不变。0.1–0.4 的排序、提示和 payload 保持重放兼容。
- 实测 Ollama 0.31.1 / qwen3.5:2b 的 think=false 不遵守最小 schema；开启推理和省略开关遵守。新版本省略强制开关，兼容非 thinking 模型；预算 4096，超时/截断仍拒绝。开发问题在 1600/4096 都有截断，不将调用改进视为模型质量通过。
- 冻结 v2 共七题，五个新问题、两个显式已见控制题；11/11 目标事实进入上下文。代理 gold 不是独立人工 gold；原六题不再宣称未见。
- 实现 `c60d8af5c0cc72c632a679e06fc264747267fb95` / [run `37646726266`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37646726266) 七 job 全部 success。418 tests（416 passed、2 环境跳过），17 项 P30 定向、隔离 wheel、合成协议场景和离线重放通过。
- qwen3.5:2b 的 12 次真实推理为 11 次截断拒绝、1 次超时、0 次结构化通过；12 份归档全通过离线复验。qwen3-vl 后续复验 11 份归档：7 次超时、4 次 HTTP 400；末份及汇总损坏，不是完整质量比较。详见[模型适用性评估](p30-model-suitability.md)。
- XML 仍由解析器/对象图/规则处理。视觉能力声明和 XML 输入能力均未转成工作台验收。暂不微调；缺独立人工语义 gold 和经过审核的训练数据。
- P30 整阶段保持 implementing。下一项为在工作台 120 秒边界内补足有效模型对照，完成独立人工语义/资料适用性验收，再确定用途和是否需要更强基线或训练。P25 人工演示/反馈及物理 ECU 未由本轮替代。


### P30：服务 grammar 阻塞定位与提示 0.6（2026-10-08）

- 原 qwen3-vl 试验续查：11 份归档通过离线复验，7 次超时、4 次 HTTP 400；末份 explanation 及 partial/summary 含空字节，保留原件，不补造完整结果。
- 恢复既有 Docker Desktop/Ollama/API/Qdrant；重放一条原始失败请求得到 HTTP 400，日志明确 `number of repetitions exceeds sane defaults`，对应 `char{0,4000}`。短探针仅返回截断的思考，HTTP 200 不算模型成功。
- 提示 0.6 已实现：针对本机 grammar 重复次数限制，将生成草稿上限从 4000 收紧至 160 字符；0.1–0.5 重放保持。418 项回归（416 passed、2 环境跳过）、13 项模型测试、schema/类型/拓扑检查通过；11 份既有 0.5 真实归档修改后复验通过。隔离安装通过（12 类协议场景及归档复验）；两条提示 0.6 的已见问题开发调用均超时、2/2 归档复验通过，无有效模型答复。本次实现 `ff08e4d58bacea55d2e6ea36b1e2e9d042ef55e3` 的 [run `37713395967`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37713395967) 七个作业全部 success，才计为实现验收。
- 本地证据 `output/p30-continuation-audit/`；原始错误正文及日志均留本地。新增人工审阅记录表，未自动填报人工结论。
- 下一项仍为 P30：版本化 8K 上下文预算，记录服务生成 token 用量并 fail closed；检查长输入上下文溢出，再用新冻结集完成模型对照和独立人工语义/资料适用性审阅。

- 0.6 两条开发调用均服务超时，2/2 离线复验通过；是已见问题诊断，不是完整配对或新未见质量验收。下一步优先隔离提示处理、思考生成、排队与资源占用造成的延迟，再恢复完整模型对照。


### P30：提示 0.6 上下文预算诊断与远端验收（2026-10-08）

- 实现提交 `ff08e4d58bacea55d2e6ea36b1e2e9d042ef55e3` / [run `37713395967`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37713395967) 七个 job 全部 success：`runtime-currency` 113104267049、`core-contracts` Ubuntu 113104267211 / Windows 113104267319、`controlled-rejections` Ubuntu 113106404765 / Windows 113106404875、`runtime-evidence` Ubuntu 113106404772 / Windows 113106404867。
- 新修复前后均保留 0.1–0.5 重放；隔离安装 12 个协议场景通过；418 项回归 416 通过、2 环境跳过。
- 本机 16K 上下文两条调用分别 130.610s 与 131.339s 超时，2/2 归档复验通过。服务日志：输入 prompt 约 1128/2706 tokens，16K KV 缓存约 1792 MiB，仅 20/29 层卸载 GPU，触及客户端 120s 超时。已见问题的 8K 开发探针约 30.717s 完成（3460 prompt / 292 output tokens），两项目标引用通过 schema 与严格引用验证；不是完整 adapter 归档、未见评测或语义正确性认证。
- 下一项实现提示 0.7：绑定 8192 context、4096 输出预算；读取 Ollama token 计数，缺失或超预算拒绝，并保留 0.5/0.6 历史负载。长上下文拒绝和双平台实现 CI 待验收。


### P30：提示 0.7 上下文预算与 token 用量门（2026-10-08）

- 新冻结提示 0.7 绑定 `num_ctx=8192` / `num_predict=4096`；0.5/0.6 的提示、16K payload 与历史复验保持。结构化生成输出上限为 160 字符；完成响应缺少整型 token 计数或 `prompt_eval_count + eval_count` 超上下文时拒绝。
- 已见诊断问题在 standalone 修改 payload 探针中 8K 返回成功（30.717 秒、3460 prompt / 292 completion tokens，目标事实 2/2），但它没有完整 adapter 重放边界。正式 0.7 adapter 同问题调用 56.251 秒，输出到 4096 token 上限而被拒绝；归档 `verify-model-explanation` passed，保持实际模型 status=refused。两个过程证明 8K 请求能较快完成，也暴露生成长度受上下文/模型行为影响，不能宣称稳定质量。
- 新增 token 上下文超限负例和版本化 payload 回归。本地全量 419 tests（417 passed、2 环境跳过）；14 项模型定向、Ruff、54-source 类型检查、57 schemas/76 bound/25 syntax-only examples、拓扑、pip check、compileall、安装后 12 协议场景与归档复验均通过。
- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。模型 v2 问题已见；结构化拒绝仍有发生，完整模型质量、语义及资料适用性人工审核未完成。见[模型适用性评估](p30-model-suitability.md)和[人工验收表](p30-human-review-guide.md)。
- 下一项仍为 P30：保留模型生成结束状态、输出 token 数及耗时诊断；确定 8K 下不同模型和问题类型能否在 120 秒内结构化完成，再建立新冻结集并完成独立人工语义/资料适用性审阅。质量门前不将解释结果用于工程判定。


### P30：提示 0.7 预算实现远端验收（2026-10-08）

- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。
- 419 项全量测试中 417 passed、2 环境跳过；14 项模型专项；隔离安装后的 12 项协议夹具和离线归档复验通过；Ruff、54-source mypy、57 schemas、76 schema-bound / 25 syntax-only、CI topology、pip check、compileall 通过。
- 本机正式 adapter 以 8K prompt 返回 4096-token length 截断并拒绝；该受控失败的归档离线复验通过。已见问题的直接修改 payload 探针有一次 30.717s 的 292-token 完成结果，不能代替正式 adapter 重放或新冻结问题对照。
- 本次记录属于 `[skip ci]` 文档状态回填，引用实现提交及其实际 run；新改运行代码时仍须该提交自己的 CI。
- 下一项为 P30：先确定 8K 下响应结束、耗时和 token 计数在模型/问题间的稳定范围，再冻结新评测集；完成独立人工语义及资料适用性审阅。现有代理编写的 gold 不是独立人工验收。P30 仍 implementing。


### P30：提示 0.8 的 qwen3-vl 思考模式适配（2026-10-08）

- qwen3-vl 本机 identity families=[qwen3vl] 经运行时核对后，在提示 0.8 使用 think=false；qwen3.5 和提示 0.1–0.7 不变，失败/成功均保存实际 model-input、身份与服务输出。不是所有 thinking 模型共用一个强制开关。
- 同一已见 qwen3-vl 问题的提示 0.7 默认调用用尽 4096 token、message.content 为空；提示 0.8 适配器调用约 25.7 秒结束，1129 prompt / 348 output tokens，结束原因为 stop。输出通过模型 schema、严格 fact_id/typed-value 校验，两个 gold 事实均被引用，正式归档离线复验通过。自然语言解释未经人工审核，prose 仍 unassessed；单个已见开发样本不是质量评估。
- 新增模型家族策略和归档复验回归。当前本地全量 420 tests（418 passed、2 环境跳过），15 项 P30 模型定向通过；隔离安装 12 协议场景/归档复验通过；Ruff、54-source mypy、57 schemas/76 bound/25 syntax-only、topology、pip check、compileall 均通过。
- 提示 0.8 的实现 `cb6294b8a9161647733c636ed07411b0975b1389` / [run `37733947430`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37733947430) 七 job 全部 success。下一项用新冻结问题配对 qwen3.5 与 qwen3-vl，再完成独立人工语义和资料适用性审阅；P30 继续 implementing。


### P30：提示 0.8 远端验收与六题已见回归（2026-10-08）

- 实现 cb6294b8a9161647733c636ed07411b0975b1389 / [run 37733947430](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37733947430) 七个 job 全部 success：runtime-currency 113169146393；core-contracts Windows 113169146725 / Ubuntu 113169146661；controlled-rejections Windows 113170820518 / Ubuntu 113170820559；runtime-evidence Windows 113170820597 / Ubuntu 113170820534。
- 全量 420 tests（418 passed、2 环境跳过）；15 项模型专项；隔离安装后 12 项协议场景及归档复验、Ruff、54-source mypy、57 schemas/76 bound/25 syntax-only examples、CI topology、pip check、compileall 通过。
- 新冻结 v2 全部题目明确为已见回归，共六个项目模式问题、一个历史 preflight 控制。qwen3-vl 六题中三题 structured pass、三题因 4096-token length 截断拒绝；gold recall 通过项为 1.0。7/7 行（含历史控制）归档复验 passed。初次从宿主 Ollama 地址运行一题因 DNS blocked，该失败另存，没有计为模型拒绝；正式运行在原 backend 容器网络完成。
- 一条 `diagnostic-affected-objects` 正式调用 25.7 秒、1129 prompt / 348 output tokens；schema 及两个 gold 引用通过。其中文解释没有经人工语义核对，仍为 unassessed。旧测试不是新未见评测，也不能替代人工 review。
- 下一项：冻结一批未参与提示调试的具体工程问题，做 qwen3.5 与 qwen3-vl 完整配对并记录结束原因/token/耗时；完成独立人工语义和资料适用性记录。P30 仍 implementing。


### P30：提示 0.10 阶段状态事实范围（2026-10-08）

- 对只询问项目整体状态与具名阶段状态的问题，0.9 会把 24 条事实送入上下文；0.10 仅选 project `/status` 与该 stage 的 `/status`。旧提示版本重放策略保持，schema 与版本回归同步更新。
- 开发 v4 使用两个不同的 P29 报告（integration、transmitter），每题两条 gold 状态。因题目用于开发 0.10，明确标记为已见开发回归。最终 qwen3-vl 两题均 stop、严格结构化通过且各引用 2/2 gold，耗时 61.1s/32.6s；qwen3.5 两题均失败（一次超时、一次 length 截断）。四个最终模型归档离线复验通过。状态回答正文尚未人工核验，资料适用性未测试。
- 本地全量 422 tests（420 passed、2 环境跳过）；17 项模型专项、隔离 wheel 两项目、12 个 HTTP 协议场景与归档复验、Ruff、8-source mypy、57 schemas/76 bound/25 syntax-only、topology、pip check、compileall 均通过。实现 `0d9c3ba4bf4faae5fb7bda5af43241cd7287a3c2` / [run `37771946406`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37771946406) 七 job 全部 success：`runtime-currency` 113293415542；`core-contracts` Windows 113293415264、Ubuntu 113293415630；`controlled-rejections` Ubuntu 113296212241、Windows 113296212339；`runtime-evidence` Windows 113296212256、Ubuntu 113296212372。该 run 是实现验收；本条文档回填不替代实现 CI。
- P30 保持 implementing。下一项冻结不同证据且不参与提示调试的问题集，做模型配对；同时独立审阅这两条状态回答，并记录语义准确性与人工可用性。不得将状态题的通过扩展为一般工程解释或资料适用性结论。


### P30：提示 0.10 不同证据状态题配对（2026-10-08）

- 在提示 0.10 实现及 CI 验收后冻结 v5；使用此前未进入 P30 cohorts 的 `repeat` 与 `identity-mismatch` P29 报告。每题 gold 固定 overall 与 ECUC stage status 两个字段，两个模型各自冻结后才执行。该 gold 是依据报告字段预先编写的代理标注，不是独立人工 gold。
- 清单摘要：qwen3.5 `763e4656252877a6a39afe7cbeee75afa46c4c07e86ffecc56870606a3b164ee`；qwen3-vl `31b26c62df09e9ec5ff3ad34b0110daf18b2e007c836a3b537157bfb1d439772`。qwen3.5：repeat 请求超时（135.8s，service unavailable），identity-mismatch 在 70.6s 被严格输出门拒绝；两题 context gold 均 2/2、引用 0/2。qwen3-vl：repeat 在 68.0s 正确引用 2/2 并通过结构化任务；identity-mismatch 在 19.5s 结构合法但只引用 1/2，任务未通过。四份完成的模型归档离线复验均 passed；两条回答语义仍 unassessed。
- 开发中的第一次 qwen3.5 调用仅留下预检文件，未计入 cohort；原件保留，正式 retry 使用新输出目录。模型结果没有据此调整提示或选择策略。
- P30 质量门仍 implementing。下一项由独立审阅者在查看答案前先写下两个报告的状态判断，再审阅 qwen3-vl 的两个自然语言回答、引用覆盖和可用性；没有独立 review 前，不把简单状态摘录扩展为一般解释能力。

- 2026-10-09：用户独立核对了上述 qwen3-vl 两条 v5 状态回答，并确认两题文本内容均正确。该人工复核仅覆盖所问 overall/ECUC status 的内容准确性；资料适用性和更广的解释可用性未评估。`identity-mismatch` 的 prose 虽正确，结构化 `project_claims` 仍缺 `/status` 引用，自动结构化任务仍失败。下一项修复同一事实在正文和 claims 之间的完整性，并用新证据验证；qwen3.5 的超时和无效输出仍需另行跟踪。


### P30：提示 0.11 状态引用完整性（2026-10-09）

- 根因已从原始归档确认：qwen3-vl 的 `identity-mismatch` 正文写出两个正确状态，但 `project_claims` 只引用 `/stages/ecuc/status`。旧 schema 只要求 claims 至少一条，校验器验证每条引用存在且值未改，没有检查状态题中两项被问事实是否都被引用。
- 提示 0.11 在“整体项目状态 + 具名阶段状态”窄场景中要求两个 claim；动态 JSON schema 将最少条数设为 2，运行时校验要求 claim ID 集合精确覆盖两个目标事实。缺项或误报 unassessed 会拒绝；提示 0.1–0.10 的重放逻辑不变。
- 全量 423 tests（421 passed、2 环境跳过）；18 项模型专项通过。Ruff、单文件 mypy、57 schemas/76 bound/25 syntax-only、CI topology、compileall、diff check 通过；隔离 wheel 安装后两工程、12 合成模型协议场景、2 旧模型归档重放通过，wheel SHA-256 `4d754e66317837bb2587da56c944622c141cbaf19f4ca1fc18811344cc46d841`。
- 使用已见 v5 做提示开发回归（不是独立评测）：qwen3-vl 的 `identity-mismatch` 用时 21.5s、引用 2/2 并通过；`repeat` 用时 71.4s、输出到 4096 token 上限而拒绝。qwen3.5 两题分别约 104.3s/72.1s，均因 length 截断拒绝。四份生成归档离线复验通过。缺引用问题在一个场景改善，但模型输出稳定性仍不足。
- 实现 `355955cf883e17b3adf2d77294041b220f8d9b00` / [run `37906579233`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37906579233) 七 job 全部 success：`runtime-currency` 113741384759；`core-contracts` Windows 113741384479、Ubuntu 113741384881；`controlled-rejections` Ubuntu 113743605146、Windows 113743605169；`runtime-evidence` Windows 113743605179、Ubuntu 113743605217。该实现门 remote-accepted；纯文档回填不替代实现 CI。
- 下一步在未参与提示调试的新证据上冻结状态题验证 .11，并继续定位输出截断，不放松引用校验。P30 一般解释、资料适用性和整体模型用途仍未验收。


### P30：提示 0.11 两模型配对复验（2026-10-09）

- 冻结 [v6 cohort](../research/p30-evaluation-cohort-v6.json)，选用 `backend-blocked` 与 `wrong-response-id` 报告，问题均询问 overall project 与 ECUC stage 状态。两份报告未用于 0.11 调整，但曾出现在更早提示开发组；因此这是 0.11 的新样本复验，不是全新工程证据集或独立人工 gold。状态 gold 在调用前由报告字段核对并冻结。
- 冻结摘要：qwen3.5 `e18610adccdfb31598869e52920a35ff6b924d16555aa8f1e741b3b5a6114227`；qwen3-vl `f3b492c570346fd73636920987c0699b77a1b8bf70387811dc7b33c879ca746f`。使用本机现有模型和 Docker backend，没有改提示/运行代码。
- qwen3-vl 两题均结构化通过、目标事实 2/2 进入上下文且引用 2/2；耗时 66.7s、33.0s。qwen3.5 两题均在适配器处拒绝无效/不完整输出，耗时 102.4s、78.3s，引用 0/2。四份实际调用归档的离线复验均 passed。拒绝不计为模型正确回答；qwen3-vl 通过也只证明结构和引用门通过，答案文字及可用性尚未独立审阅。
- 原始归档和汇总留在本机 `output/p30-continuation-audit/trial-v6-qwenvl/`、`trial-v6-qwen35/`；清单也留在同目录。未提交原始模型输出。
- 文档/冻结题集提交 `e311512` 已推送；其 CI [run `37912242301`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37912242301) 七项全部 success：runtime-currency `113759898063`；core-contracts Ubuntu `113759898327`、Windows `113759898606`；controlled-rejections Ubuntu `113761756218`、Windows `113761756282`；runtime-evidence Ubuntu `113761756289`、Windows `113761756308`。这是文档提交 CI，不替代提示 0.11 实现提交 `355955c` 的实现验收。
- 2026-10-10 用户确认 qwen3-vl 两条通过回答的文字准确且可用。该人工验收只覆盖 v6 两道简单状态复述，不包含手册适用性、复杂因果或一般工程判断。


### P30：提示 0.12 qwen3.5 输出恢复（2026-10-10）

- 原始 0.11 v6 响应显示 qwen3.5 两题均 `done_reason=length`、`eval_count=4096`，`message.content` 长度为 0，独立 `thinking` 字段分别约 16.6K/16.8K 字符；事实选择和模型身份均正确。因此失败是当前服务/模型组合在默认 thinking 下耗尽生成预算，不是缺少输入事实。
- 0.12 复用 0.11 的提示、两项状态引用和 8K 上下文，只在 `/api/tags` 实际返回 family=`qwen35` 时设置 `think=false`。0.8–0.11 对 qwen3-vl 的既有策略保留，0.11 及更早 qwen3.5 payload 不改，未知或非 thinking family 不强制该选项。
- 使用相同 v6 两题和固定 digest 重冻清单（`5eb332c0834a27103b2391010d76c36e40ef8305c2d0275fc7a7ffc6b6081801`）后，qwen3.5 两题均 `done_reason=stop`、thinking 长度 0，prompt/output token 为 1017/324、1012/289；适配总耗时 32.3/19.8 秒，目标事实均 2/2 进入上下文并引用，结构化任务和离线归档复验均通过。该组是输出修复对照，不是新的模型质量集。
- 本地验证：424 tests（422 passed、2 环境跳过）；模型专项 19/19；12 类合成 HTTP 场景、57 schemas/76 schema-bound/25 syntax-only、CI topology、Ruff、8-source mypy、compileall、diff check 通过。隔离 wheel 两工程、12 类模型场景与归档复验通过，wheel SHA-256 `e001b22ada382b436b351070773f77719a30e38ebe64e1182339297a17284a26`。
- 实现 `656098b8b8dca8373ba3974ced45a317f25d05ec` / [run `38012423168`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38012423168) 七 job 全部 success：`runtime-currency` `114095165644`；`core-contracts` Windows `114095165813`、Ubuntu `114095165919`；`controlled-rejections` Ubuntu `114096657670`、Windows `114096657681`；`runtime-evidence` Ubuntu `114096657716`、Windows `114096657724`。状态 remote-accepted；本条后续纯文档回填不替代实现 CI。
- qwen3.5 已能在该窄状态任务输出，不据此声明一般工程解释或资料适用性通过；下一步冻结未参与本轮修复的问题并分别计量 qwen3.5 与 qwen3-vl，继续保留独立人工语义/适用性门。


### P30：提示 0.9 嵌套字段选择与新题配对开发验证（2026-10-08）

- 复查提示 0.8 新题调用发现：点名检查时只保留检查直接字段，漏掉问题明确询问的 `binding/request_id`、`response_id`、`did` 和 `/stages/ecuc/status`。提示 0.9 将精确请求的嵌套字段与阶段状态加入选择器，同时保留 0.1–0.8 的历史版本逻辑，并更新模型解释 schema 版本枚举。
- 冻结 [v3 cohort](../research/p30-evaluation-cohort-v3.json)：两道新问题、复用既有 P29 项目报告。明确视为提示开发回归，而非独立人工 gold 或未见工程证据。最终 qwen3.5 清单摘要 `a98cb1bc33e2523d85d6fb309709ddf1b324e7efa335c7d7f23c186d683ffa9f`；qwen3-vl 清单摘要 `19b8384b95af8304ad05dfce143c8ddea95d973ef985a21e7b55ac45a4b56a1c`。模型身份/digest 固定，原始试验留本地 `output/p30-continuation-audit/`。
- 最终提示 0.9 两模型各两题的 gold 覆盖为 6/6。qwen3.5 两题均以 `done_reason=length`、4096 输出 token 截断拒绝，耗时约 76.2/74.9 秒；qwen3-vl backend 状态题同因截断拒绝（57.0 秒），绑定数值题在 43.4 秒 stop，1090 prompt / 372 output tokens，结构化引用 3/3 正确。4/4 实际调用离线归档验证 passed。自然语言语义、因果、资料适用性仍未人工评估。
- 提示 0.8 的先前四调用未覆盖所有目标字段；其中一条 schema 通过但 gold 引用 0/3，不能算任务通过。新结果只和最终 0.9 同批计分。
- 全量 421 tests（419 passed、2 环境跳过）；16 项模型专项通过。隔离 wheel 安装后两工程事实门、12 项模型 HTTP 合成协议、安装归档重放通过。Ruff、8-source mypy、57 schemas / 76 schema-bound / 25 syntax-only examples、CI topology、pip check、compileall 通过。
- 实现提交 `11361788108a8793d6b3808fe85ab506fa8e0b82` / [run `37742242675`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37742242675) 七 job 全部 success：runtime-currency `113195398856`；core-contracts Windows `113195398938` / Ubuntu `113195399041`；controlled-rejections Windows `113197537909` / Ubuntu `113197537982`；runtime-evidence Windows `113197538027` / Ubuntu `113197538036`。本条及同步状态文档是后续纯文档更新，不作为新实现验收。
- 下一项：在项目证据不同的冻结问题上重复配对，且由独立审阅者逐项审核唯一通过回答的自然语言、证据边界及资料适用性；未审前 P30 模型质量仍未通过。
