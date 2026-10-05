# Automotive Workbench 长期升级路线 v3

更新：2026-10-05。本文是当前升级顺序；[进度账本](progress-log.md)是实际状态源。[v2 历史路线](roadmap-v2-history.md)仅保留决策背景，不再作为下一步指令。

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

P30 已进入 implementing：首轮[只读事实门](p30-fact-gate-guide.md)已 remote-accepted（`a82ee62` / run `37183484781` 七 job success），验证事实来源和值，尚未接入模型。本轮继续交付[Ollama / 原知识助手适配](p30-model-adapter-guide.md)、回退和资产/磁盘盘点；下一项为六类工程问题的独立模型质量评测、资料适用性及人工可用性，仍按 P30 统一验收。
