# Automotive Workbench 长期升级路线 v3

更新：2026-10-22。本文是当前升级顺序；[进度账本](progress-log.md)是实际状态源。[v2 历史路线](roadmap-v2-history.md)仅保留决策背景，不再作为下一步指令。

## 长期产品目标

形成个人可维护的汽车软件配置与验证工作台：把需求/接口、DBC、ARXML、BSW 配置意图、执行测试和工程审查连成可复现工作流。工程人员改变配置后，应能回答：**改了什么，影响哪些通信/诊断对象，哪些检查和实验受影响，哪些结论已有证据，哪些还未验证。**

目标使用者首先是你本人：做配置自动化、跨层问题定位和公开工程交付；以此积累汽车工具链开发能力，并支持 Classic AUTOSAR BSW 配置/集成方向。长期架构仍是 Windows 工程面 + Linux 执行面，复用 Generate-Arxml、现有审查内核和成熟 CAN/UDS 库，以 artifact 连接，避免重复建设工具内核。

半年交付目标不是命令数、schema 数或测试总数，而是以下四项用户能力同时成立：

1. 至少两个结构不同的公开项目由同一声明式流程运行；加入第二个项目不修改运行内核。
2. 配置变更能沿信号、PDU、路由与验收项追踪，输出有来源的影响范围；无法判断的部分显式标记未知。
3. 至少一条真实导出桥接和一条独立进程 ECU 通信/诊断路径，分别记录输入版本、工具版本、执行条件与失败证据。
4. 从干净环境完成配置导入、检查、运行、变更比较、审查和交付；公开演示可复现，求职表述能逐项指向证据。

## 个人情况与资源假设

依据 `D:/work/improve/README.md`、`docs/job-research/TARGET_PROFILE.md`、`docs/SKILL_MATRIX.md` 与第六周学习计划：已有 ASW/SWC/ARXML 与 Python 自动化积累；主出口为汽车工具链/配置自动化，BSW 配置集成为并行出口；当前个人学习在独立 UDS/ISO-TP 与 OpenBSW 调用链。记录未证明的能力不视为已经掌握。

沿用每两周 20～30 小时的个人总预算，建议分配：平台评审与集成 8～12 小时，通信/诊断和 C/C++ 学习实操 8～12 小时，复盘与表达 4～6 小时。下面 24 周是滚动容量规划，不是每阶段必然按日历完成的承诺；代理编码耗时也不等于你的学习投入。每两周用实际验收结果调整余量，阶段目标保持连续。

## 当前事实与主要缺口

| 领域 | 已有能力 | 本轮查证的缺口 |
|---|---|---|
| 工程入口 | P15/P16 项目执行、输入快照、实际生成器导出消费 | P20 已冻结两项目统一声明流程；P21 已补齐受限对象图与配置影响，P22 公开 ARXML 桥接已验收，P23 项目 0.5 已远端验收，P24 已验收，下一阶段 P25 |
| 通信运行 | virtual/SocketCAN、双向证据、过滤与 blocked | project 0.3 已接入通用运行与路径绑定；旧项目保留兼容路径 |
| BSW 映射 | Tx/Rx、DBC 属性、跨层引用一致性与 8 节点 trace | P21 已有四类稳定身份对象、规则覆盖与验收关联；仍不验证 vendor ECUC |
| 外部工具 | 固定 Generate-Arxml DOCX/contract/issues 三例 | P22 已有真实 SWC ARXML 受限离线导入/比较；项目 0.4 公开路径已远端验收，ECU Extract/ECUC 未覆盖 |
| ECU 执行 | 固定 OpenBSW 构建、CF01、独立进程生命周期及现场故障证据 | 项目 0.5 已远端验收，现场与离线证据分开 |
| 审查交付 | 确定性引用、拒答、项目比较、P19 HTML | 现有结果比较不等同于输入变更影响；检索审查不等同于通用语义诊断 |
| 质量基线 | 七 job CI、安装后验证、证据迁移复验 | P23 项目集成七 job 已通过；P24 完整分项评测与冻结后负例已独立远端验收 |

P15–P18 的历史跨平台冻结保持有效；P18 独立复验补强/P19 已由实现提交 `88c24e2`、远端 run `35748563878` 的七 job 全绿完成冻结。P19 属于既有工作流的易用性补强，不是新的长期产品方向。

## 未来 24 周的六个交付阶段

| 顺序 / 参考窗口 | 主阶段与交付 | 必须满足的阶段门 | 对你的能力价值 |
|---|---|---|---|
| P20 / 第 1～4 周 | **声明驱动的多项目通信验证**：从项目文件选择本地 ECU、消息、方向与测试向量，同一引擎支持车窗和第二个结构不同项目 | 两项目无需改内核运行；旧项目兼容；非法向量/不支持特性在开总线前拒绝；双平台 virtual + Linux SocketCAN 条件验收；项目/review/compare 完整闭环 | Python 平台抽象、DBC/Tx/Rx 与工程接口设计 |
| P21 / 第 5～8 周 | **BSW 通信对象图与变更影响**：明确 ComSignal、IPdu、PduR route、CanIf PDU 身份和关系；规则限定到可证实语义 | Tx/Rx 两链；至少覆盖断引用、重复身份、方向冲突、长度/布局冲突、路由端点错误、配置变化影响；每项规则有正负例与来源；两版本输入到受影响对象/验收项可追踪 | COM/PduR/CanIf 配置理解与分层定位 |
| P22 / 第 9～12 周 | **ARXML 与商业工具桥接**：优先消费可公开的 Generate-Arxml 导出，逐步接一条合法可用的 DaVinci 导入/回导 | 固定受支持的元素与 AUTOSAR 版本；保留源路径、工具版本和未支持语义；正常/悬空引用/语义变化三组 golden diff；商业工具往返须有真实执行证据 | ARXML/ECU Extract/ECUC 工具链能力；不把 SWC ARXML 等同 ECUC |
| P23 / 第 13～16 周 | **独立 ECU 执行纳入项目**：以固定 OpenBSW POSIX 构建和 CF01 为首条外部执行路径，统一运行前检查、诊断和报告 | 不在客户端内启动假 responder；绑定构建/寻址配置；成功、无响应、错误 DID/ID、环境 blocked；清理/超时/通道隔离可重放；virtual 和外部 ECU 证据分开 | C/C++ 调用链、ISO-TP/UDS 集成、执行系统设计 |
| P24 / 第 17～20 周 | **面向真实工程问题的审查**：利用 P20–P23 的输入、对象图和失败报告回答变更影响/配置定位问题 | 固定至少 30 个不同工程问题，保留独立未参与开发的负例；检索/规则/可选模型分别计量；关键无证据断言必须拒答；引用与严重度保真 | 工程 AI 应用能力，连接现有知识工作台 |
| P25 / 第 21～24 周 | **可复现平台交付与作品集**：统一安装/执行手册、英文入口、10 分钟演示、双岗位能力映射 | 干净环境重跑两项目与故障；安装后核心路径可用；CI 全绿和完整归档；演示每条能力可定位证据；真实外部使用/投递反馈形成下一轮问题清单 | 从研发到交付的完整叙事与可展示成果 |

依赖：P20 → P21 → P22；P23 可在 P20 稳定后穿插本地环境工作；P24 使用前三阶段证据；P25 的演示/文档随阶段积累，最后做统一验收。一次只保留一个主要实现阶段，环境等待可切换到已有计划的独立任务。

P22 商业工具许可或公开导出不可用时，完成公开 ARXML 导入和离线语义比较，商业往返保留 blocked，并推进 P23；不伪造导入成功，也不让许可等待阻断整个半年计划。P23 的 SocketCAN 环境不可用时完成离线/virtual 自动回归，现场门仍待验收。P24 只有确定性基线与真实解释缺口明确后才接可选模型，模型不拥有工程判定权。

## 当前执行：P30 implementing（P29 已按受限范围验收，P25 人工验收待完成）

2026-10-26 最新交接：0.6 `wrong-mapping` development v2 冻结 `0c25b9d` / [run `40159165690`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40159165690) 七 job success；唯一 Qwen 请求与停服双复验通过，但模型原文漏掉具体 reason 和项目整体 unassessed，[内容审阅](../research/p30-agent-evidence-pair-projection-v06-development-v2-review.json)为 `failed_for_the_requested_task`，旧题不重跑。[模型原文字面覆盖门 0.7](p30-agent-evidence-pair-model-coverage-v07-guide.md)已本地实现并在该旧结果上离线检出 `incomplete`；下一项先取得 0.7 自身七 job CI，再以新报告冻结规范行与关系判据并做单次模型开发验证。字面覆盖不等于语义正确；内容开发门通过前不冻结 held-out v2。独立人工适用性与 P25 人工演示仍待实际审阅，P30 不宣称整阶段完成。

1. P20 最终实现 `31ca4ef` / run `35979820300` 的七 job 与两项目本机 SocketCAN 全流程验收保持，见 [P20 验收表](p20-acceptance.md)。
2. P21 已 remote-accepted：实现提交 `79d1f3b`、[run `36022099415`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36022099415) 七 job 全部 success；两平台对象图/规则/影响/迁移复验场景及上传均通过，见 [P21 验收表](p21-acceptance.md)。
3. P22 公开路径 remote-accepted：项目 0.4 实现 `0e00245` / [run `36257173567`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36257173567) 七 job 全部 success，两平台项目场景与上传通过，见 [验收表](p22-acceptance.md)。商业工具往返仍 blocked，恢复需实际安装、许可与执行证据。实现 `3e4c29aba190f74cf0e17641af649892a37f415a` / [run `36331506323`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36331506323) 七 job 全部 success，Windows/Ubuntu 项目场景与上传均 success。P23 固定 POSIX/vcan0 范围 remote-accepted；现场证据沿用已记录的真实构建与诊断，不把远端离线验收当现场运行。 P24 固定问题、目录检索、对象级 gold、严重度与冻结后负例已 remote-accepted：实现 `6117b09e7ab80e7fdebca5a4654cdc4159f29a46` / [run `36451604309`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36451604309) 七 job 全部 success；Windows/Ubuntu 开发场景、分项评测及证据上传均 success。见 [P24 验收表](p24-acceptance.md)。[P25 隔离安装后多项目流程](p25-installed-delivery-guide.md)已 remote-accepted：实现 `911abc0e4e59d76fc72265fc73a75aea5b09c28a` / [run `36586481411`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36586481411) 七 job 全部 success；Windows/Ubuntu 的安装后双项目验证及完整归档上传均 success。仓库外双项目/故障、离线依赖、迁移引用、指南与能力证据映射已提供。下一项为人工演示实测和真实外部反馈，见[P25 验收表](p25-acceptance.md)；未取得前不标记整阶段完成。
4. P20 结果比较与 P21 配置依赖影响分别保留；P22 只映射源 ARXML 真正提供的语义，不从 SWC/interface 名称补造 COM/PduR/CanIf ECUC。

## 用户提供工程后的路线补充（2026-09-30）

用户先要求分析本地 BSW 配置工程，再授权继续升级。新增 [P26 真实 ECUC 配置体检与跨层定位](p26-ecuc-inspection-plan.md)，作为当时唯一代码实现主阶段：项目感知导入/引用体检 → 通信跨层定位 → 应用与调度集成检查 → 两版配置影响。首轮项目体检实现 `c6320d5` / [run `36813404620`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36813404620) 七 job 全部 success，双平台场景和上传通过，首轮门 remote-accepted。

P25 安装交付门保持 remote-accepted；人工演示和真实外部反馈仍待取得，不把新工程的代理分析算作 P25 人工验收，也不宣称 P25 整阶段完成。本地输入和细节不进入公共仓库，公开回归用合成 fixture。P26 真实 VALUE-REF 驱动的 COM/PduR/CanIf/Can 引用链已 remote-accepted：实现 `b671864` / [run `36817127099`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36817127099) 七 job 全部 success；Tx/Rx、组信号、路由分支、硬件对象/控制器与迁移复验通过，见[通信定位指南](p26-ecuc-communication-guide.md)。本轮合并交付应用/OS/RTE/BswM 集成缺口与两版快照影响，含安装后完整审查/比较/迁移流程；实现 `6433e1cdf360e07d4d09e9294922380f68730018` / [run `36864006903`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36864006903) 七 job 全部 success，见[P26 验收表](p26-acceptance.md)。其后已验收的阶段为[P27 声明式 ECUC 配置变更验收](p27-configuration-acceptance-plan.md)，将现有消费者接入统一项目声明和验收交付。

## 持续升级的完成规则

用户说“继续升级平台”，默认继续当前阶段尚未完成的验收项；当前阶段全部通过则进入已排定的下一阶段。无需再次等待用户提出某一个小功能。职业方向或资源发生变化时更新假设与后续顺序，并说明取舍。

每阶段交付必须同时包含：可操作的用户路径、输入与输出、正例与真实失败用例、自动验证、本轮远端 CI、更新后的首页状态/进度/下一项任务。状态严格分为 planned / implementing / local-accepted / remote-accepted / blocked；CI 未运行与 CI 失败必须分别记录。涉及机器环境的门另行记录，远端 virtual 成功不能代替现场执行。

在会话授权范围内完成提交推送、跟踪 CI 和失败修复；权限/凭据/外部环境确实阻塞时记录具体动作、错误和恢复入口。新提交改变运行代码或 CI 配置后，需要该提交自己的验收结果；纯文档状态回填引用已经通过的实现提交，并区分随后文档提交的运行状态。

保留底层核心、证据契约和回退路径。除非新 consumer 要求且当前阶段明确获益，不增加分布式服务、远程调度、完整 BSW 栈或协议覆盖面。每个阶段结束检查实际维护成本，优先消除重复内核。

## 本次官方资料核对与技术边界

- AUTOSAR 将 Classic Platform 架构与方法论同时纳入标准范围；平台路线因此保留 ASW/RTE/BSW 边界和跨工具交换，具体规则需固定文档版本后逐项落实。[AUTOSAR Classic Platform](https://www.autosar.org/standards/classic-platform)
- Vector 当前 DaVinci Configurator Classic CLI 文档列出导出、ECUC 派生、验证、生成与项目比较入口。因此商业桥接优先消费产物并调用已有工具；具体命令必须匹配本机安装版本和许可，不据在线文档认定本机已可运行。[Vector CLI reference](https://help.vector.com/davinci-configurator-classic/en/latest/user-manual/references/cli/index.html)
- OpenBSW 诊断与寻址受平台构建选项控制。P23 必须保存构建配置并显式配置请求/响应 ID，不把历史 CF01 地址假定为所有构建通用。[OpenBSW diagnostics](https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/features/diagnostics.html)

以上资料核对支持接口与边界选择；六阶段的优先级与预算是结合本仓状态作出的工程计划，不是厂商路线或就业保证。

## P27 当前交付与下一项（2026-10-02）

0.6 声明式 ECUC 项目、两工程、四状态接受条件、审查/比较/搬移与隔离安装流程已实现；实现 `55e208fffe6d51c233ff30d3604bafd992dfb080` / [run `36901660485`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36901660485) 七 job 全部 success，见[P27 验收表](p27-acceptance.md)。其后 P28 对象级配置变更验收已通过，见以下最终交接。

P28 版本化精确对象保护与字段不可变条件已 remote-accepted，旧契约保持；实现 `2269714e6895f6e1d3c2b7276e034b61262ea33b` / [run `37025748404`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37025748404) 七 job 全部 success，双平台场景/安装/上传通过，见[P28 验收表](p28-acceptance.md)。

[P29 配置验收与运行证据关联](p29-configuration-runtime-plan.md)已按显式映射/诊断验收依赖范围 remote-accepted；P28 静态冻结保持。当前下一主阶段为 P30 implementing。

P29 CAN 关联首轮已实现，详见[操作指南](p29-runtime-link-guide.md)与[验收表](p29-acceptance.md)。本地/隔离安装及本机 SocketCAN 条件验收已通过；实现 `b2da1472f82a6aceebe43efdfb477ceb4e1896fa` / [run `37091771686`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37091771686) 七 job 全部 success，CAN 关联门 remote-accepted；独立 ECU 诊断依赖亦已通过：实现 `654cd8fb907f79d69f3ad2636b8f222e5d1bb0b1` / [run `37166161292`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37166161292) 七 job 全部 success；本机独立 OpenBSW POSIX/vcan0 十场景通过。P29 在明确边界内完成，CAN 本地端点与独立诊断证据分别保存。

P29 诊断依赖已验收，下一主阶段为 [P30 基于项目证据的本地模型解释](p30-evidence-explanation-plan.md)：复用已有本地知识助手，以通过复验的报告为事实基础，先解决引用、状态和来源边界再接入模型。硬件台架按设备实际取得和独立现场证据推进，不改变当前主阶段。

P30 的只读事实门、模型适配、冻结评测器和提示 0.5–0.22 均已通过各自远端 CI；0.22 实现 `78e88085d836fd16ebc83447b0f36a601920ba8c` / [run `38066909019`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38066909019) 七 job success，但 v9 内容验收为 0/6。0.23 Agent-ready 基础及[知识来源信任策略 0.1](p30-knowledge-trust-policy.md)也已 remote-accepted：最新策略实现 `268482a0c730b77c5b915c702b070cb071258136` / [run `38123214672`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38123214672) 七 job success。[最小只读 Agent 工具链](p30-readonly-agent-guide.md)现已 remote-accepted：原生 Ollama function calling 与结构化回退、绑定 read tools、动态工具隐藏、完整结果/紧凑 projection、显式预算和离线验签 trace 已通过 446 项本地回归、隔离 wheel 协议场景和真实 qwen3.5:2b 开发试验；实现 `3d69f544d0411cee201479b1b4bab9f17ce17f22` / [run `38189854764`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38189854764) 七 job success。[独立只读 Agent v1 评测](p30-readonly-agent-evaluation-guide.md)在推理前冻结后取得真实 3/5 基线：概览、资料和主动越权拒绝通过，项目明细/混合路由失败；评测基础设施及跨平台修复 `49a5b5231be7c531ef355b1e38948f56c90c95ef` / [run `38402213934`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38402213934) 七 job success，模型质量结论仍为 failed。[只读 Agent checkpoint、暂停与幂等恢复](p30-agent-durability-guide.md)也已 remote-accepted：实现 `a96193087bb9a09b01e635c37e57e3556024a686`、跨平台测试修复 `fdf5e217683b97454f1677b1a8bb7c72f18dad3d` / [run `38429351251`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38429351251) 七 job success。一般复杂解释和真实资料适用性仍未验收，P30 保持 implementing；下一门先定义不开放写/硬件的 approval request/decision、拒绝和过期语义，再讨论副作用事务与幂等键。v1 路由缺口只能由新开发题和后续 v2 验收；qwen3-vl 留给后续图片/OCR 多模态入口。

2026-10-21 续进：复杂解释 v1 与 Codex-reference/Qwen v1 都保持真实 0/4 failed，旧 cohort 不修改、不重跑。[控制面证据纯文本摘要 0.2](p30-agent-evidence-summary-v2-guide.md)已 remote-accepted：实现 `fc56a68a6ef57f08b1af5c943599e08d8c348387` / [run `39543371725`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39543371725) 七 job success，旧 0.1 plan/frozen manifest 不变。其后全新 development-only 问题只调用 qwen3.5:2b 一次；result `46f65aaf…799570` 在纯文本协议与停服离线复验层 passed，但 top-6 事实遗漏 2/5 个指定检查，Qwen 仍补写其状态，Codex 非独立诊断为 `not_usable`。下一门先新增版本化的成对字段完整选择和缺项拒绝，保留 0.2/旧结果可复验；开发通过后才冻结 held-out cohort，比较 Qwen 与可审计的更强文本模型并完成独立 assessment。配置写入、SocketCAN、硬件和认证 operator 仍关闭。

2026-10-23 续进：[控制面完整证据对摘要 0.3](p30-agent-evidence-pair-summary-guide.md)实现 `56a522a1b6b347748821885f8830ae6085f74eb9` 继续保持 remote-accepted：[run `39719942007`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39719942007) head 一致、七个实际 job 全部 success。经用户授权，仅重建 Ollama 服务并把宿主机端口绑定 `127.0.0.1:11434`；模型持久卷不变，服务版本 `0.31.1`、qwen3.5:2b digest 与预冻结值一致。对新的 `project-acceptance-0.8` transmitter report 和五项 pair plan 恰调用一次；Qwen 输出的 5/5 ID 与 status/reason 逐项精确匹配冻结的 Codex 直接转录参考，未增加报告外事实；result `c738187a…12adae`，1 call、1202 prompt/58 output tokens，停服后离线 verifier passed。按预登记的狭义 criterion，此开发题支持 `usable`；结果中的 `semantic_assessment` 保持 `unassessed`，且 Qwen 遗漏了提示要求的明确证据边界句，这项非硬门缺口要加入下一 cohort 的显式检查，不能宣称一般解释能力或独立人工验收通过。

随后冻结全新 [证据对摘要 held-out v1](../research/p30-agent-evidence-pair-heldout-v1.json)：三份不同 runtime outcome 的报告（failed timeout / unassessed runtime identity / failed frame identity），每题六个显式 `status/reason` pair，Codex direct-transcription reference 在先、虚拟证据边界设为硬评分项。三份报告和共享计划均离线验证通过；Qwen 三题各调用一次，18/18 pair 精确匹配、协议及离线复验全通过；但边界硬门 0/3，严格任务可用性 `failed`。三题分别为：第一、二题完全未说明虚拟证据不证明物理 ECU 行为；第三题只说是 virtual CAN report，仍漏掉 physical-ECU 限制。Codex 对照审阅非盲且非独立人工，模型结果 `semantic_assessment` 仍为 `unassessed`。[结果与 Codex 评分](../research/p30-agent-evidence-pair-heldout-v1-codex-review.json)。下一步不重复或修补这组结果；新增版本让控制面确定性附加固定证据边界声明，在新 development cohort 验证后再冻新 held-out。旧 cohort 不改不重跑，独立人工 assessment pending。写配置、SocketCAN、硬件和认证 operator 仍关闭。

2026-10-15 续进：[审批请求与决定状态](p30-agent-approval-guide.md)、[本地一次性 claim 与非执行事务](p30-agent-transaction-guide.md)、[受限 virtual CAN execute tool](p30-agent-virtual-execution-guide.md)及[模型提案与控制面执行边界](p30-agent-action-proposal-guide.md)均已 remote-accepted。[动作提案 v2 评测](p30-agent-proposal-evaluation-v2-guide.md)实现 `7912f85094f9521fc08d2f581349bde697b3648c` / [run `38722912093`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38722912093) 七 job success；固定结果 0/5 failed，result `365c40cb…a9de` 离线重评分通过。proposal evidence 0.2 实现 `7a7aeec98134f3a7c2844b48197c6dfa6d40f54e` / [run `38741428620`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38741428620) 七 job success，已 remote-accepted；新开发题完整记录到模型把 `0x456` 改成 `1`。下一门不是继续提示修补或扩大权限，而是 control-plane-issued、哈希绑定的 action candidate：模型只选 candidate ID 或拒绝，不能重写参数；这同时减少 schema/参数 token，最终另冻新 cohort。配置写入、SocketCAN、硬件和认证 operator 仍不开放。状态真相继续使用 Workbench 版本化、哈希绑定协议；LangGraph 仅保留为未来 graph/checkpointer/interrupt 编排适配候选。

2026-10-16 续进：[控制面动作候选与 ID-only 选择](p30-agent-action-candidate-guide.md)已 remote-accepted。其后的 [candidate-selection v1](p30-agent-candidate-evaluation-v1-guide.md) 在预推理冻结后由实现 `c619883248fdb883b4b122ae1b17349fac35ad6b` / [run `38877648265`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38877648265) 七 job 完成基础设施远端验收，再只运行一次固定 qwen3.5:2b。真实结果 1/5 failed：准备、候选签发、证据绑定、非执行和成本均 5/5，但两个精确候选均选错，三个拒绝题仅 SocketCAN 越权正确；result `21a76c92…8b7b` 已停服离线重评分。下一门把 typed action intent、精确动作/能力/observation applicability 移回确定性控制面，模型不得覆盖过滤或拒绝；不在同一 cohort 上调提示或重跑。配置写入、SocketCAN、硬件和认证 operator 仍不开放。

2026-10-17 续进：[typed action intent 与确定性准入门](p30-agent-action-admission-guide.md)已 remote-accepted。控制面现在封存精确 action、受限 capability 和 checkpoint observation 条件；准入器在无模型调用时重验候选，只把唯一精确匹配交给现有审批链。无动作、越界能力、证据不足和零/多匹配不可被模型覆盖。实现 `36eac3b592bd060d9a27f75c0e66c57ea2987b14` / [run `38997832114`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38997832114) 七 job 全部 success。

2026-10-18 续进：[deterministic admission 后只读模型评测 v1](p30-agent-admission-evaluation-v1-guide.md)已按预推理冻结顺序完成。冻结实现 `5bca6c48324084ef7acb7c10b2cd84428de4051a` / [run `39001106717`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39001106717) head 一致且七 job 全部 success；随后固定 qwen3.5:2b cohort 只运行一次，五题均正确选择只读事实工具并暂停，确定性准入得到两个 `approval_required` 与三个预期拒绝，真实结果 5/5 passed。result `57d9e802…7bf8` 在 Ollama 停止后离线重评分通过。该结论不覆盖 prose、一般复杂解释或真实资料适用性，也没有生成 decision、claim 或 execution。P30 保持 implementing；下一门冻结新的复杂解释/可信资料 cohort 并形成独立人工审阅包，不扩大动作权限。旧 candidate-selection v1 保持 1/5 failed，配置写入、SocketCAN、硬件和认证 operator 仍关闭。

2026-10-18 续进：[Agent 独立人工审阅包](p30-agent-human-review-guide.md)已 remote-accepted：它从通过离线复验的评测生成不暴露 frozen gold、类别或自动逐题分数的 review pack，并把完整人工判断固化成哈希绑定、可重算的 assessment。实现 `4005c32482d908510a969c4dfa1038a613c00892` / [run `39137376642`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39137376642) head 一致且七 job 全部 success；本地 506 tests（2 项环境跳过）、84 schemas、源码合成全链和隔离 wheel 均通过。合成 reviewer 全部为 `not_assessable`，不冒充真实人工结论。下一门冻结新的复杂解释/可信资料 cohort；冻结实现远端通过后再执行一次真实 qwen3.5:2b 并交付独立审阅。P30 保持 implementing，动作权限边界不变。

2026-10-19 续进：[复杂解释与官方资料适用性评测 v1](p30-agent-explanation-review-v1-guide.md)已按预推理冻结顺序完成。冻结实现 `c904bd913703890e33d46c709d3efeb0b8ff533b` / [run `39192046821`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39192046821) head 一致且七 job 全部 success；随后固定 qwen3.5:2b 四题只运行一次，真实机器结果 0/4 failed。两道混合题取得 4/4 项目事实和两份 Vector 官方资料，但四题引用门均失败；result `dd91e3e7…4c36` 已停服离线复验。review pack `761361aa…ab8c` 已验签并保持 `pending_human_review`。官方资料仍不证明本机 license/SIP、命令执行或项目适用；不修改、不重跑本 cohort。下一门是完成独立 assessment，再只在新版本/新 cohort 处理工具选择、finish action 和引用缺口。P30 保持 implementing；配置写入、SocketCAN、硬件和认证 operator 继续关闭。

2026-10-23 续进：[证据对摘要 0.4](p30-agent-evidence-pair-summary-v04-guide.md)已在本地实现：外层 envelope 复用不可变 0.3 plan/runner，确定性附加 physical-ECU/配置写入/实车执行边界，同时保留可复验的 0.3 base result 和原始模型 trace；新增 schema/CLI，0.3 合同不变。全量既有 525 tests 通过（2 项环境跳过），随后新增 refusal regression 单独通过；93 schemas / 79 bound / 25 syntax-only、Ruff、scoped mypy、CI topology、compileall、diff check 均通过。实现 `d66e54c` 的 run `39931330099` 中 runtime-currency 和 Ubuntu core-contracts success，但 Windows core tests 因新增 schema 的默认 cp1252 解码失败，downstream jobs skipped；已修正为等价 JSON `\u` 转义并通过 18 项针对性测试，修复提交与重跑待完成，尚无远端验收。下一项：取得该修复 head 一致的七 job CI 全绿后，冻结全新 development-only 报告、问题、Codex reference 和边界 criteria，再对 Qwen 恰运行一次并停服离线复验。确认开发门后再冻结新 held-out；旧 v1 保持真实失败、不修改、不重跑，独立人工 assessment pending。写配置、SocketCAN、硬件和认证 operator 仍关闭。

状态回填（2026-10-23）：0.4 修复提交 `bf2447fb4895668c1b5699492160bfb9f464fd73` 对应 [run `39942378767`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39942378767)，head 一致、七个实际 job 全部 success（Windows core `120376688704`、Ubuntu core `120376688891`、runtime-currency `120376688960`、controlled-rejections Ubuntu `120380021668` / Windows `120380021688`、runtime-evidence Windows `120380021773` / Ubuntu `120380022000`）。此前 run `39931330099` 的 cp1252 失败已保留为兼容性修复证据，不用于接受结论。P30 当前仍 implementing；0.4 remote-accepted，但新 Qwen development case 未开始。下一步冻结新 report/question/Codex reference/边界 criteria，再在冻结包自身 CI 通过后只运行一次 Qwen，随后离线复验；新开发题达标后才冻新 held-out，旧 held-out `failed_for_the_requested_task` 不修改、不重跑，独立人工 assessment pending。

下一步状态更新（2026-10-23）：0.4 implementation 和 development v1 冻结提交均 remote-accepted；冻结提交 `aae053fe689bb95c51f855e710e67f442a638984` / [run `39944788642`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39944788642) head 一致、七 job success。随后对唯一冻结题发起一次运行，Ollama 请求以 `service_unavailable:URLError` 阻断，无 request/response/model summary，记录模型调用为 0；结果停服后离线 verifier passed，含义仅为结构/trace 可重放，不能算模型验收。按冻结策略未重试，development v1 整体状态为 `blocked_environment`，内容标准不可评估，独立人工 review pending。下一步先用不调用模型的 health check 诊断 Workbench 到 Ollama 的 endpoint 路由及 proxy bypass；确认可达后再冻结 byte-distinct development v2，取得其自身 CI 后运行一次。旧 held-out v1 仍 failed、不改不重跑，P30 保持 implementing。

2026-10-24 续进：Docker Desktop Linux engine 已恢复，既有 Ollama 容器保留原卷且仅监听 `127.0.0.1:11434`；WSL `curl` 和 Python `urllib` 非推理版本探测均返回 `0.31.1`，模型 digest 与旧冻结值一致。新的 [0.4 development v2 冻结包](../research/p30-agent-evidence-pair-summary-v04-development-v2.json)绑定 byte-distinct integration protected 报告与五项应用/任务 pair，报告和 plan 已离线复验；当前 `pre_inference_frozen`，目标模型尚未调用。下一步是该冻结提交自身 CI 全绿后恰运行一次、停服复验和按预置判据审查，再决定新 held-out；独立人工审阅仍 pending。

状态回填（2026-10-24）：冻结提交 `9416e1285092bbc30aec15ef0c368c17ff62b644` / [run `39986811298`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39986811298) head 一致、七 job 全部 success；其后 v2 唯一 Qwen 调用和停服离线复验均完成。协议与 5/5 输入 pair 完整、控制面证据边界通过，但模型将五项 status/reason 合并描述，未给逐项 reason 原值；按预冻结内容标准，开发题 `failed_for_the_requested_task`，原结果 `semantic_assessment=unassessed`。详见[逐项审阅](../research/p30-agent-evidence-pair-summary-v04-development-v2-review.json)。下一门是新版本的确定性逐项呈现与模型原文分离，或另一文本模型的新冻结开发比较；不据此冻结 held-out v2。P30 仍 implementing，独立人工 assessment 继续 pending。

2026-10-24 续进：[证据对确定性呈现 0.5](p30-agent-evidence-pair-presentation-v05-guide.md)已本地验收：从通过原报告/0.4 结果离线复验的完整 pair 确定性生成用户可见逐项 status/reason，模型原文另列 unassessed；旧 v2 真结果 5/5 pair 和旧服务阻断结果 4/4 pair 均通过停服复验，源模型失败/阻断结论不变。全量 528 tests（2 项环境跳过）、94 schemas、Ruff、类型/拓扑和隔离 wheel 验证通过；实现提交自身远端 CI 待完成。下一步先验收本实现，再以新冻结开发题检查模型文本的附加价值；未通过前不进入 held-out v2，独立人工审阅继续 pending。

状态回填（2026-10-24）：0.5 实现 `fe9777cf14974ed386cc6cdce7913f22491c92a3` / [run `40055697502`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40055697502) head 一致、七个实际 job 全部 success，现为 remote-accepted。下一任务改为冻结全新开发题，衡量模型原文在确定性事实表之外是否提供准确、有证据支持的解释；冻结提交远端通过后只调用一次。新开发门未通过前不冻结 held-out v2，独立人工审阅继续 pending；0.4 旧失败不回调。

2026-10-24 续进：[0.5 附加解释 development v1 冻结包](../research/p30-agent-evidence-pair-presentation-v05-development-v1.json)已在目标推理前固定：全新 `wrong-address` 项目报告与四项 status/reason pair、静态通过和运行未验收的关系参考、禁止补造具体根因、模型 digest 和单次预算。report/plan 均离线复验，两个结果路径不存在；当前 `pre_inference_frozen`，没有模型调用。下一步必须先取得冻结提交自身 head 一致的七 job CI 全绿，再唯一调用 Qwen、生成 0.5 确定性呈现并停服审查；结果不回调，人工独立审阅仍 pending。

2026-10-24 状态回填：上述冻结提交 `5eab6b2c63ac286961fb0fc78d2dbbba2ab6e977` / [run `40067728218`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40067728218) head 一致、七 job success；唯一运行在初次请求 Ollama 时因 `service_unavailable:URLError` 阻断，记录 4/4 完整事实、0 model calls，故无模型文本可评。0.5 仍确定性显示四组精确 pair 和证据边界，0.4/0.5 在停服后均离线复验 passed；[逐项审阅](../research/p30-agent-evidence-pair-presentation-v05-development-v1-review.json)将总体记为 `blocked_environment`。重启容器后的同一 Python Endpoint 只读版本/digest 检查成功，但不解释原失败瞬间。下一门先在实际 runner 环境做紧邻推理的只读 version/tags 预检，再为不同报告冻结 development v2；它通过内容门后才建立新 held-out。旧 cohort 不重跑，P30 仍 implementing，独立人工评估 pending。

同日续进：[development v2 冻结包](../research/p30-agent-evidence-pair-presentation-v05-development-v2.json)已改用 byte-distinct 的 `backend-blocked` 报告：两项静态/存在检查 passed，两项运行关联 blocked/interface_missing。报告和四项 plan 离线复验通过，结果路径为空；Codex 直接参考、关系判据、禁止根因补造及单次预算均在模型调用前固定。下一步先获得冻结提交自身七 job success，再在同一 Python runner 环境核对 Ollama version/tags/digest 并紧接唯一模型调用。开发内容通过后才进入 held-out；当前 P30 implementing。

同日状态更新：v2 冻结提交 `f4361aa71ade1f26b3a4956846392ad22c5fc616` / [run `40071744818`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40071744818) head 一致、七 job success，但唯一 runner 再次在首个服务请求因 `URLError` 阻断，0 model calls；0.5 事实呈现和停服离线复验均通过，模型内容不可评。[逐项审阅](../research/p30-agent-evidence-pair-presentation-v05-development-v2-review.json)记录环境原因：相同只读 Endpoint 脚本在默认沙箱重现 `URLError`，授权网络执行则返回正确版本/digest。先前已批准的 `python -c` 预检与默认沙箱 CLI runner 权限不同。v1/v2 不重试。新的 [development v3 冻结包](../research/p30-agent-evidence-pair-presentation-v05-development-v3.json)绑定不同的 `second-run` passed 报告和关系判据；先取得其冻结提交七 job success，再以同一授权网络执行只读预检与唯一模型调用，停服审阅后才决定是否进入 held-out。P30 仍 implementing。

同日结论：v3 冻结提交 `a57c0584b9a1cfab9693860b9041f7e4123ab923` / [run `40074217607`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/40074217607) head 一致、七 job success；授权网络路径中的唯一 Qwen 调用 protocol passed、4/4 status/reason 准确、停服双 verifier passed。按[预注册判据审阅](../research/p30-agent-evidence-pair-presentation-v05-development-v3-review.json)，模型原文错误地称 `RX_PRESENT` 为运行中观察到 radio presence，并声称接收数据匹配发送数据；仅选取的 pair 和验收项文本均不支持这些细节。开发内容整体 `failed_for_the_requested_task`，原结果仍 `semantic_assessment=unassessed`，不重跑、不冻结 held-out。下一主实现门是版本化模型证据投影，把验收项原文与 status/reason 同源绑定并重新冻结开发题，保留 0.5 确定性用户可见基线和旧契约；独立人工评估仍 pending，P30 implementing。

## P30 事实选择与模型适用性进展（2026-10-08）

提示 0.5 的实现、418 项回归、隔离安装与远端七 job 已通过（`c60d8af` / run `37646726266`）。qwen3.5 冻结结果为 11 次截断拒绝、1 次超时、0 次结构化通过；qwen3-vl 已复验 11 份服务失败归档，末份及汇总损坏；未形成有效模型答复。阶段质量门尚未通过。下一步完成独立人工语义/资料适用性验证，并在客户端时限内补足模型对照，再确定用途和是否需要更强基线或训练。XML 沿用文本解析与对象图；多模态是后续图像证据入口，不能替代 XML 校验。见[模型适用性评估](p30-model-suitability.md)。


## 提示 0.6 服务兼容性修正（2026-10-08）

提示 0.6 已实现：针对本机 grammar 重复次数限制，将生成草稿上限从 4000 收紧至 160 字符；0.1–0.5 重放保持。418 项回归（416 passed、2 环境跳过）、13 项模型测试、schema/类型/拓扑检查通过；11 份既有 0.5 真实归档修改后复验通过。隔离安装通过（12 类协议场景及归档复验）；两条提示 0.6 的已见问题开发调用均超时、2/2 归档复验通过，无有效模型答复。本次实现 `ff08e4d58bacea55d2e6ea36b1e2e9d042ef55e3` 的 [run `37713395967`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37713395967) 七 job 全部 success。

本机服务日志证明 grammar 的 `char{0,4000}` 超出重复次数限制；这是服务兼容性阻塞，不能据此归因于模型的汽车领域能力。生成限制变小，独立引用/类型校验和语义 unassessed 边界不变。

下一项仍为 P30：验收 0.6 的服务兼容性，恢复 120 秒内完整模型对照，随后按[人工验收表](p30-human-review-guide.md)完成独立语义/资料适用性审阅；质量门通过前不宣称模型解释可用。


### P30：提示 0.7 上下文预算与 token 用量门（2026-10-08）

- 新冻结提示 0.7 绑定 `num_ctx=8192` / `num_predict=4096`；0.5/0.6 的提示、16K payload 与历史复验保持。结构化生成输出上限为 160 字符；完成响应缺少整型 token 计数或 `prompt_eval_count + eval_count` 超上下文时拒绝。
- 已见诊断问题在 standalone 修改 payload 探针中 8K 返回成功（30.717 秒、3460 prompt / 292 completion tokens，目标事实 2/2），但它没有完整 adapter 重放边界。正式 0.7 adapter 同问题调用 56.251 秒，输出到 4096 token 上限而被拒绝；归档 `verify-model-explanation` passed，保持实际模型 status=refused。两个过程证明 8K 请求能较快完成，也暴露生成长度受上下文/模型行为影响，不能宣称稳定质量。
- 新增 token 上下文超限负例和版本化 payload 回归。本地全量 419 tests（417 passed、2 环境跳过）；14 项模型定向、Ruff、54-source 类型检查、57 schemas/76 bound/25 syntax-only examples、拓扑、pip check、compileall、安装后 12 协议场景与归档复验均通过。
- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。模型 v2 问题已见；结构化拒绝仍有发生，完整模型质量、语义及资料适用性人工审核未完成。见[模型适用性评估](p30-model-suitability.md)和[人工验收表](p30-human-review-guide.md)。
- 下一项仍为 P30：保留模型生成结束状态、输出 token 数及耗时诊断；确定 8K 下不同模型和问题类型能否在 120 秒内结构化完成，再建立新冻结集并完成独立人工语义/资料适用性审阅。质量门前不将解释结果用于工程判定。


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
