# Automotive Workbench 全局目标、前沿性与代码质量审计

## 执行结论

项目没有发生实质性方向偏离。当前实现仍围绕公开样例、确定性实验、统一工程证据、Windows/Linux 双平面和开放 adapter 展开；量产 ECUC、供应商 BSW generator、真实 ECU 正确性、远端身份认证和通用 LLM 产品仍被明确排除。P4-P9 虽然扩大了证据交付与完整性能力，但仍是原始 artifact-first 平台目标的自然延伸，而不是新产品线。

真正的问题是工程治理没有完全跟上功能增长：顶层 README 的“四件事”已经扩展为 33 项；路线文档同时保留多个历史“下一阶段”；三个核心模块超过 1,000 行；CI 没有 lint、type、coverage 或 JSON Schema 实例门禁；Python 只验证 3.11；GitHub Actions 原先使用可移动 major tag。审计还复现了一个真实闭合契约缺陷：Python 的 `bool` 是 `int` 子类，导致 evidence manifest、delivery receipt 和 capsule report 的布尔计数字段被手写 loader 当作整数接受。

本轮已经修复布尔计数缺陷、增加三组回归测试，并将 CI 中的 GitHub 官方 actions 更新到当前版本、固定到完整 commit SHA，同时把默认 `GITHUB_TOKEN` 权限收敛为 `contents: read`。其余建议按窄里程碑推进，不建议立即加入 DDS、Rust、DoIP、SOVD、远端 attestation 或通用语义 AI。

## 审计范围与判定基线

本次审计以仓库内以下内容作为既定目标的事实来源：

- `README.md`：公开能力、运行入口和明确边界；
- `docs/project/roadmap.md`：统一体验、分离内核、开放 adapter 的平台方向；
- `docs/project/progress-log.md`：P0-P9、R1-R5 的实施证据和冻结边界；
- `pyproject.toml`、`.github/workflows/ci.yml`：运行时、依赖和跨平台门禁；
- `src/automotive_workbench/`、`tests/`、`schemas/`：代码、测试与声明契约。

外部前沿性以 2026-09-10 可访问的一手来源为准，优先采用 AUTOSAR、Eclipse OpenBSW、Python、依赖项目、GitHub、SLSA、in-toto、OASIS 和 ASAM 的官方资料。标准更新只在与当前边界直接相关时转化为建议，不以“新”本身作为扩张理由。

## 全局目标对齐

| 既定目标 | 当前实现证据 | 判断 | 说明 |
|---|---|---|---|
| 统一 Artifact/Finding/Trace/TestResult/Evidence 契约 | schemas、adapter、review、bundle、capsule | 对齐 | P5-P9 强化了 artifact 生命周期 |
| 公开车窗样例的 DBC→SWC→COM→PduR→CanIf 研究链 | BSW intent、DBC/canonical adapter、P4 通信链 | 对齐 | 仍明确不是量产 ECUC |
| Windows 工程面与 Linux 执行面分离 | Windows/Ubuntu CI、WSL/SocketCAN 脚本 | 对齐 | virtual baseline 保证跨平台确定性 |
| CAN/UDS/DTC 的可重复运行实验 | R1-R4、精确过滤、blocked/failure 证据 | 对齐 | 没有把样例结果外推为真实 ECU 保证 |
| 基于显式证据的本地工程审查 | R5 request/evaluation/cohort | 对齐 | 仍是 retrieval-only 和调用方断言，不声称语义理解 |
| 开放 adapter 与限时 OpenBSW spike | Generate-Arxml、cantools、OpenBSW patch artifact | 对齐 | OpenBSW 未被误作完整 Classic BSW |
| 轻量、确定性、纯本地 | 无数据库、GPU、远端 LLM 或远端 artifact 拉取 | 对齐 | P5-P9 只做本地字节与依赖图验证 |

### 对齐判断

技术方向保持一致，偏离风险主要存在于表达和维护层：

1. `README.md` 的“只做四件事”已与 33 项能力清单矛盾，容易让读者误判项目边界。
2. `roadmap.md` 按时间累积了多个“下一阶段”，虽然可作为历史记录，但不再适合作为唯一当前状态视图。
3. P4-P9 使用新的里程碑编号叠加在 R1-R5 后，没有一张稳定的能力域映射表；继续追加会增加路线理解成本。
4. 证据完整性能力已经接近供应链证明领域，但文档仍正确地区分“本地哈希一致”与“身份/来源可信”。这一边界必须保留。

因此总体判断是：**产品目标未偏离，路线叙事出现轻度漂移，工程质量门禁存在中度滞后。**

## 全局校验结果

### 已执行验证

| 校验 | 结果 |
|---|---|
| `unittest` 全量测试 | 148 项运行：146 项通过，2 项按环境跳过 |
| evidence 定向回归 | 22 项通过 |
| Python `compileall` | 通过 |
| 全部 schema/example JSON 解析 | 通过 |
| 全部 Linux Bash `bash -n` | 通过 |
| `pip check` | 无依赖冲突 |
| `git diff --check` | 通过 |
| 最近双平台主线 CI | Windows/Ubuntu 均通过 |

两个跳过项分别对应当前环境没有 `vcan0` 和仅在非 Linux 上有意义的结构行为；这与既定 blocked/conditional contract 一致，不是隐藏失败。

### 代码规模与可维护性

`src/automotive_workbench` 约 9,451 行 Python。最大模块为：

| 模块 | 行数 | 风险判断 |
|---|---:|---|
| `review.py` | 1,246 | 高认知负担；解析、执行、引用和渲染职责耦合 |
| `uds_runtime.py` | 1,197 | 场景、transport、responder 和报告职责耦合 |
| `review_eval.py` | 1,057 | 多版本兼容、producer、materialization、metrics 耦合 |
| `dtc_intent.py` | 516 | 可接受，但 schema 演进继续时需拆分 validator |
| `evidence_bundle.py` | 475 | 安全敏感路径，适合保持小型 helper 与强回归 |
| `evidence_capsule_verification.py` | 441 | 安全敏感路径，当前职责仍可理解 |

模块长度本身不是错误，但前三个模块已经越过“单次局部修改容易完整理解”的范围。建议在下一次触碰对应能力时按职责拆分，不做无功能收益的大爆炸重构。

## 已确认并修复的代码缺陷

### JSON boolean 被当作 integer

Python 中 `isinstance(True, int)` 为真。原 loader 仅用 `isinstance(value, int)` 检查计数字段，因此以下非法 JSON 能通过部分闭合契约：

```json
{
  "artifact_count": true,
  "total_bytes": false,
  "size_bytes": false
}
```

JSON Schema 将 `boolean` 与 `integer` 定义为不同类型。该差异会使代码实现弱于仓库声明的 schema，尤其在单 artifact、零字节、零 dependency 等边界值上可以完整绕过聚合相等检查。

修复覆盖：

- `evidence-bundle-manifest` 的 `artifact_count`、`total_bytes`、artifact `size_bytes`；
- `communication-evidence-delivery` 的四个 artifact/dependency 计数；
- `evidence-capsule-report` 的六个 artifact/dependency/external 计数；
- manifest、delivery、capsule 三条布尔输入回归测试。

修复后的策略与 `diag_intent.py`、`dtc_intent.py`、`review.py` 已采用的显式 `isinstance(value, bool)` 拒绝方式一致。

## 尚未构成功能错误、但需要管理的风险

### P1：声明 schema 尚未成为 CI 可执行契约

`scripts/check_json.py` 只调用 `json.loads`，能发现语法错误，却不能验证 required、type、enum、pattern、additionalProperties 或跨字段约束。当前正确性主要依赖各 loader 的手写校验和单元测试；本轮的 boolean 缺陷正说明两者可能漂移。

建议建立一个独立的 contract-conformance 测试层：

- 用 Draft 2020-12 validator 校验所有正向 fixture；
- 为每个安全敏感 schema 至少生成 type/additionalProperties/path/hash 负例；
- 对同一 fixture 同时执行 JSON Schema 和 Python loader，要求 accept/reject 一致；
- 把 format 检查策略明确化，避免 `date-time` 仅作为注解存在。

### P1：Python 运行时矩阵偏旧

项目声明 `requires-python >=3.11`，CI 只跑 3.11。Python 官方已将 3.11 标为 security-only，支持到 2027-10；当前 feature release 是 3.14。[^1] 这并不意味着 3.11 立即不安全，但只跑最低版本无法及时发现新解释器、typing、依赖 wheel 或标准库行为变化。

建议保留 3.11 作为最低兼容门槛，增加一个 Ubuntu/Python 3.14 的轻量全量测试 lane；Windows 继续保留 3.11，待首轮兼容通过后再决定是否扩展完整 OS×Python 矩阵。不要立即测试 free-threaded build，因为 python-can/ISO-TP 的线程与 native dependency 组合尚无当前业务需求。

### P1：缺少 lint、type 与 coverage 门禁

当前 CI 没有 Ruff、mypy/pyright 或 coverage。cantools 自身的贡献流程同时运行 Ruff、mypy、测试和 coverage，可作为同类 Python CAN 项目的工程参照。[^2]

建议先引入低争议规则：未使用 import、未定义名称、明显控制流错误和格式稳定；type checking 先覆盖新模块或 public API，不要一次性要求 9,000 多行全严格通过；coverage 应按高风险模块设置增量门槛，而不是追求全仓单一百分比。

### P1：GitHub Actions 引用与权限

原 workflow 使用 `actions/checkout@v5`、`actions/setup-python@v6` 和 `actions/upload-artifact@v7`。GitHub 官方指出，只有完整 commit SHA 是 action 的不可变引用，并建议显式限制 token 权限。[^3] 当前官方 action 已演进到 checkout v7、setup-python v7、upload-artifact v7.0.1。[^4][^5]

本轮已完成：

- checkout 固定到 v7.0.1 commit；
- setup-python 固定到 v7.0.0 commit；
- upload-artifact 固定到 v7.0.1 commit；
- workflow 默认权限固定为 `contents: read`。

后续应使用 Dependabot 或定期人工审计更新 SHA；固定 SHA 不是“永不更新”，而是把更新变成可审查变更。

### P2：依赖只有范围，没有可复现实例锁

`pyproject.toml` 对 CAN/diagnostic optional dependencies 使用合理的 major 上界；本地环境为 cantools 41.4.3、python-can 4.6.1、can-isotp 2.0.7、udsoncan 1.26.1，`pip check` 通过。python-can 4.6.1 仍是最新稳定 release，但 main 分支已有未发布变更。[^6] cantools 当前稳定文档对应 41.4.3。[^2]

对于库项目，保留兼容范围是正确的；对于 CI evidence，建议额外生成 resolved dependency inventory 或 constraints snapshot，以便说明“这次证据究竟由哪些版本产生”。不要把开发环境 lock 误作公共库的唯一依赖约束。

### P2：CI 文件已接近单体流水线

单个 matrix job 包含近 50 个步骤，正常验证、预期失败、artifact 上传和 review evaluation 全部串行。优点是上下文简单，缺点是：

- 任一早期非预期失败会阻止大量后续证据；
- Windows/Ubuntu 重复执行所有逻辑，耗时和故障定位会继续增长；
- `continue-on-error` 的预期失败在 UI 中产生 annotation 噪音。

建议在新增下一能力前拆为 `core-contracts`、`runtime-evidence`、`controlled-rejections` 三个 job，并用显式 job outputs 或独立重建避免共享可变目录。当前运行约一分钟，尚不需要为性能而紧急重构。

## 前沿更新及项目影响

### AUTOSAR R25-11

AUTOSAR Classic、Adaptive 和 Foundation 当前公开 release 都是 R25-11；R26-11 发布活动计划在 2026-12-03 举行。[^7][^8] R25-11 的 Classic Release Overview 明确说明其取代 R24-11，并包含约 1,900 项跨标准 incorporation tasks。[^9]

与本项目直接或潜在相关的更新包括：

- COMHandler：抽象 intra/inter-ECU signal 类型，并聚合数据完整性、deadline、invalidity 和 range error 监测；[^9]
- Time Synchronization over CAN 拆出纯协议 PRS 与 Classic 集成 SWS；[^9]
- Classic Platform 引入 DDS 支持，包括 Dds/DdsXf、discovery 与 ClientServerInterface；[^9]
- Vehicle Data Protocol 面向生产车辆的可重配置数据采集；[^10]
- Rust in Classic/Adaptive、security、IVC 和 CAPI 持续演进。[^8]

判断：这些更新证明当前“通信契约 + 运行证据 + applicability”方向仍有行业相关性，但不构成立即实现 DDS、VDP 或 Rust 的理由。当前项目只有两个 Classical CAN message 和公开学习 intent；加入 DDS/VDP 会引入以太网、服务发现、QoS、RTE/generator 与资源配置等全新变量，明显越过窄闭环。

建议只做两项低成本跟进：

1. 新研究引用优先使用 R25-11；现有 R24-11 文档保留为当时行为基线，并标注 superseded，不机械重写历史报告。
2. 在未来 applicability profile 中预留 `standard_release` 或等价字段，避免跨 R24-11/R25-11 证据被误当作完全可比较。

### Eclipse OpenBSW

OpenBSW 仍处于 Eclipse incubating 状态，官方定位是面向汽车微控制器的 code-first SDK，而不是完整商业 AUTOSAR Classic stack。[^11] 官方文档继续确认 POSIX 可在无汽车硬件时运行，并在主机支持时通过 SocketCAN 使用 CAN；这与现有 R3 策略一致。[^12] DoCAN 官方文档仍将其定义为 ISO-15765 transport，并依赖 async 模块。[^13]

2026 年 OpenBSW 已出现 DoIP、基础 Rust 支持、Bazel 集成和未来 SOME/IP/message routing 的明确活动；项目也在规划更规律的 release process。[^14] 官方 coverage 页面显示整体 function coverage 较高，但 POSIX SocketCAN transceiver 的可见覆盖仍明显较低，说明真实 adapter 集成仍应保留独立运行证据。[^15]

本地 clone 与 patch 固定在 `dbd6e118`，当前远端 HEAD 为 `00052043`。因此：

- 已归档 patch 继续作为 2026-08-17 的历史证据，不应静默改写；
- 若准备上游化，先同步远端、重放最小 patch、重新运行目标和全量 CTest；
- 若下一目标是 DoCAN 对照，可优先做 source/API drift report；
- 不因 DoIP/Rust/SOME/IP 已出现就并行开启三个新 adapter。

### CAN/UDS Python 生态

当前依赖版本没有发现必须升级的稳定版缺口。python-can 4.6.1 仍为最新 release；其未发布 changelog 已包含 ASC timestamp mode、硬件 filter 和 Python 3.9 支持移除等变化，说明未来 4.7/5.0 升级前应重点回归 log replay、filter 与 backend 初始化。[^6]

cantools 41.4.3 官方文档继续覆盖 DBC、ARXML、CDD、candump decode 和 C generator；项目当前只使用 DBC 解析/编码的保守子集，依赖上界 `<42` 合理。[^2] can-isotp v2 仍同时支持 user-space transport 与 Linux SocketCAN ISO-TP wrapper，当前 virtual baseline + SocketCAN conditional path 的架构没有过时。[^16]

建议：不追逐未发布依赖；增加新 Python runtime lane和 resolved-version evidence，比扩大协议功能更优先。

### 诊断前沿：DoIP 与 SOVD

OpenBSW 已有初始 DoIP，ASAM 2026 资料显示 SOVD 已演进到 1.2.0。[^14][^17] 它们代表 service-oriented vehicle diagnostics 的行业方向，但当前项目的价值在于把 UDS/ISO-TP/DTC 的行为和证据边界做清楚。

建议把 DoIP/SOVD 作为“触发式研究”：只有当出现以太网诊断、远程诊断或 OpenBSW DoIP 互操作的具体用例时再启动。当前立即实现会稀释已经稳定的 CAN/UDS/DTC 纵向闭环。

### 证据供应链：SLSA、in-toto 与 GitHub attestations

SLSA 当前批准版本为 1.2，新增/强化了 Source Track，并继续区分 provenance 存在、真实性和生成隔离等级。[^18] in-toto Attestation Framework 当前 latest spec 为 v1.2，Statement 将 predicate 绑定到 subject，Envelope 负责认证。[^19] GitHub artifact attestations 可用 OIDC/Sigstore 将 artifact 绑定到 repository、workflow、commit 和 triggering event，但官方明确指出：生成 attestation 本身没有安全收益，必须验证；也不建议给频繁测试构建中的每个文件签名。[^20]

这与 P5-P9 的边界完全一致：当前 manifest/capsule 是本地字节完整性与可搬运性，不是 provenance authentication。建议：

- 当前不引入 attestation，继续保持文档中的否定性边界；
- 当项目首次发布 wheel、独立 CLI binary、容器或正式 capsule release 时，再设计“一个发布物 + 一个 attestation + 一个 consumer verification”窄闭环；
- 不自创签名格式，优先兼容 in-toto Statement/SLSA provenance 或 GitHub 官方 attestation bundle；
- attestation verifier 必须以仓库/workflow/ref 等 expectation 驱动，不能只检查签名数学有效。

### Finding 互操作：SARIF

SARIF 2.1.0 加 Errata 01 仍是 OASIS 当前公开标准，GitHub code scanning 支持其子集和上传。[^21][^22] Workbench 已有统一 Finding，因此未来增加只读 `Finding -> SARIF` export adapter 有现实互操作价值。

但它不应成为当前 P10：项目尚未接入静态分析平台，直接增加 SARIF 只会多一个未消费格式。触发条件应是 Generate-Arxml findings 需要进入 GitHub code scanning，或已有第三方 consumer 明确要求 SARIF。

## 推荐路线

### P10：Contract Conformance 与 Runtime Currency

推荐把下一窄里程碑定义为：**不增加新的汽车功能，只提高既有契约在 schema、loader、Python runtime 和 CI 供应链上的一致性。**

建议验收条件：

1. 所有安全敏感 loader 与 JSON Schema 对正/负 fixture 的 accept/reject 一致；
2. 修复 boolean/integer、date-time policy、portable path 和 additionalProperties 的差异目录；
3. 保持 Python 3.11 最低版本，并增加 Python 3.14 兼容测试；
4. 引入最小 Ruff 门禁；type checking 先覆盖 evidence 与 domain public API；
5. 输出 resolved dependency inventory；
6. GitHub Actions 均固定完整 SHA，权限默认只读；
7. Windows/Ubuntu 的现有 148 项回归和所有 controlled rejection 继续通过。

### P11 候选：OpenBSW Drift Revalidation

仅在 P10 完成且确有 OpenBSW adapter/上游化需求时启动：

- 比较 `dbd6e118..current HEAD` 对 cpp2can、SocketCAN、DoCAN、build presets 的变化；
- 重放 CANFrame invariant patch；
- 重新执行 target/label/full CTest；
- 形成 source-anchor drift report；
- 再决定 issue/PR，而不是直接提交旧 patch。

### 暂不启动

- AUTOSAR DDS、VDP、Rust CP generator；
- OpenBSW DoIP/SOME-IP/message router adapter；
- SOVD client/server；
- 远端 artifact 下载、签名、attestation policy engine；
- 通用 LLM、embedding、vector database 或 Web UI；
- 大规模拆分全部 1,000 行模块。

这些方向都可能有价值，但当前缺少明确 consumer、真实输入或验收场景。前沿性应体现为“知道何时进入”，而不是“同时实现所有新名词”。

## 最终判定

| 维度 | 评级 | 结论 |
|---|---|---|
| 目标一致性 | 绿 | 技术主线与边界保持一致 |
| 功能正确性 | 绿/黄 | 全量回归健康；发现并修复一类闭合契约类型缺陷 |
| 契约严谨性 | 黄 | loader 很强，但 schema 尚未成为统一可执行门禁 |
| 跨平台性 | 绿 | Windows/Ubuntu CI 稳定，SocketCAN 使用 conditional/blocked 语义 |
| 可维护性 | 黄 | 三个核心模块过大，CI 单体化，缺 lint/type/coverage |
| 依赖前沿性 | 黄 | 稳定依赖当前；Python CI 仅 3.11，需要现代 runtime lane |
| 汽车技术前沿性 | 绿 | 已识别 R25-11、OpenBSW/DoIP/Rust/SOVD 更新，且没有盲目扩张 |
| 供应链安全 | 黄→绿 | action SHA/最小权限已修；正式发布前仍无需 attestation |

结论：继续当前方向，但暂停新增汽车协议功能一个里程碑，先完成 P10。这样既不偏离最初“轻量、开放、证据优先”的目标，又能让已有 P0-P9 能力在 2026 年的 Python、AUTOSAR 与 CI 生态中保持可信和可维护。

## Sources

[^1]: Python Software Foundation, “[Download Python — Active Python Releases](https://www.python.org/downloads/),” accessed 2026-09-10.
[^2]: cantools, “[CAN BUS tools — cantools 41.4.3 documentation](https://cantools.readthedocs.io/en/stable/),” accessed 2026-09-10.
[^3]: GitHub, “[Secure use reference — Pin actions to a full-length commit SHA](https://docs.github.com/en/actions/reference/security/secure-use),” accessed 2026-09-10.
[^4]: GitHub Actions, “[actions/checkout changelog](https://github.com/actions/checkout/blob/main/CHANGELOG.md),” accessed 2026-09-10.
[^5]: GitHub Actions, “[actions/upload-artifact](https://github.com/actions/upload-artifact),” accessed 2026-09-10; actions/setup-python, “[Advanced usage](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md),” accessed 2026-09-10.
[^6]: python-can, “[Changelog](https://python-can.readthedocs.io/en/main/changelog.html),” accessed 2026-09-10.
[^7]: AUTOSAR, “[Classic Platform](https://www.autosar.org/standards/classic-platform/),” accessed 2026-09-10.
[^8]: AUTOSAR, “[Release Event R25-11 and R26-11](https://www.autosar.org/news-events/release-event),” accessed 2026-09-10.
[^9]: AUTOSAR, “[Classic Platform Release Overview R25-11](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_TR_ReleaseOverview.pdf),” 2025-11-27.
[^10]: AUTOSAR, “[Requirements on Vehicle Data Protocol R25-11](https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_RS_VDP.pdf),” 2025-11-27.
[^11]: Eclipse Foundation, “[Eclipse OpenBSW project](https://projects.eclipse.org/projects/automotive.openbsw),” accessed 2026-09-10.
[^12]: Eclipse OpenBSW, “[POSIX platform documentation](https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/platforms/posix/index.html),” 2026-07-28 build.
[^13]: Eclipse OpenBSW, “[docan — Diagnostics over CAN](https://eclipse-openbsw.github.io/openbsw/sphinx_docs/libs/bsw/docan/doc/index.html),” 2026-06-23 build.
[^14]: Eclipse OpenBSW, “[OpenBSW Monthly / 2026-02-23](https://github.com/eclipse-openbsw/openbsw/discussions/365),” 2026-02-23.
[^15]: Eclipse OpenBSW, “[Coverage report](https://eclipse-openbsw.github.io/openbsw/coverage/index.html),” test date 2026-06-26.
[^16]: python-can-isotp, “[IsoTp Sockets](https://github.com/pylessard/python-can-isotp/blob/v2.x/doc/source/isotp/socket.rst),” accessed 2026-09-10.
[^17]: ASAM, “[Technical Seminar 2026-03-18](https://www.asam.net/index.php?eID=dumpFile&f=10988&t=f&token=01819a586972010b9d9b1e850ef0f9e6a6ff09b0),” 2026-03-18.
[^18]: SLSA, “[SLSA Specification v1.2](https://slsa.dev/spec/v1.2/),” accessed 2026-09-10.
[^19]: in-toto, “[Attestation Framework Specification](https://github.com/in-toto/attestation/blob/main/spec/README.md),” latest version v1.2, accessed 2026-09-10.
[^20]: GitHub, “[Artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations),” accessed 2026-09-10.
[^21]: OASIS, “[SARIF Version 2.1.0 Plus Errata 01](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html),” 2023-08-28.
[^22]: GitHub, “[About SARIF files for code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/sarif-files),” accessed 2026-09-10.
