# P26 ECUC 体检与通信定位验收

更新：2026-10-01。P26 受限静态工程审查与两版配置影响整阶段 remote-accepted；四项既定静态能力均通过各自实现验收。下一主阶段为 P27（planned），环境与人工门独立保留。

| 验收门 | 证据与结果 |
|---|---|
| 项目选择与范围 | DPA/collection 选择活动模块；未选模块不误报、外部引用 unassessed |
| 公开失败场景 | 正常、未绑定、断引用、歧义四场景通过；仅使用合成工程 |
| 可移植复验 | 删除原输入后四组快照复验通过，报告/来源/库存篡改拒绝 |
| 本地回归 | 316 tests：314 passed、2 环境跳过；ECUC 定向 9/9 |
| 质量门 | 48 schemas、61 bound examples、25 syntax-only；Ruff、39-source mypy、topology、pip check 通过 |
| P24 兼容 | 原冻结记录不改，严格 0.1 输出保留；当前 0.2 历史回归 30 题及 12 负例/迁移通过，不声称新独立负例 |
| 双平台 CI | `c6320d5` / [run `36813404620`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36813404620) 七 job 全部 success；Windows/Ubuntu ECUC 场景和上传均 success |

本地证据：`output/p26-validation-20261001/`。首轮 `84b5469` / run `36742954252` Windows 因新增测试未指定 UTF-8 失败，Ubuntu/Python 3.14 成功，下游跳过；该 run 不作为验收依据。

通信引用链也已完成远端验收，详见下表。P25 人工演示/真实反馈、商业工具生成和物理 ECU 验证保持原有未验收边界。

验收实现完整 SHA：`c6320d503d3d704bdce5d64e294dc84811444e0c`。job/step 原始记录 `output/p26-validation-20261001/remote-ci.json`；各 job ID 见[进度账本](progress-log.md)。本表为后续纯文档回填，不把文档提交当作新实现验证。

## 通信跨层引用链验收（remote-accepted）

| 门 | 状态 |
|---|---|
| Tx/Rx、组信号、EcuC/PduR 两端、Buffer/HTH/HRH/CanController | 已实现，定向正负例通过 |
| 范围与失败 | 缺失/外部/错误类型/歧义/方向/条件/无路径九场景通过，额外多目标和定位测试通过 |
| 迁移与完整性 | 删除原输入后 9/9 复验，结论/来源/库存篡改 3/3 拒绝，旧 0.1 快照复验通过 |
| 本地完整回归 | 327 tests：325 passed、2 环境跳过；49 schema/61 bound/25 syntax-only、Ruff、41-source mypy、topology、pip check 通过 |
| 本轮七 job | `b6718640364104153490adbbd2d876f3172887c2` / [run `36817127099`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36817127099) 全部 success；双平台通信链场景及上传 success |

本地公开证据 `output/p26-chain-validation/`，真实工程只保存在忽略目录。当时下一项为应用/OS/RTE 调度集成缺口解释，现已随下述整阶段验收；不将本轮结构结果当生成或物理 ECU 证据。

通信链 job/step 原始记录 `output/p26-chain-validation/remote-ci.json`，各 job ID 见进度账本。该验收回填为后续 `[skip ci]` 文档提交，不代替实现提交自己的 CI。

## 整阶段收尾：工程审查与两版影响（remote-accepted）

| 验收门 | 证据 |
|---|---|
| 应用实例/组合与调度绑定 | 显式 prototype/type、事件/runnable 归属及 ASW/BSW→OsTask；缺失/错误类型/条件保持缺口 |
| 模式与工具观察 | BswM 引用/环检查，日志始终 historical-unbound；不混入当前结构失败 |
| 两版影响 | 对象参数/引用/增删及不透明内容；两侧依赖边见证，限定通信/任务/模式影响；重复身份 not-comparable |
| 用户完整路径 | 四个 CLI、离线 HTML/JSON，before/after 自包含交付 |
| 公开验证 | 十组审查/比较、10/10 移除原输入后的复验、结论/来源/HTML/库存四类拒绝；17 项专项测试 |
| 全量本地 | 344 tests：342 passed、2 环境跳过；51 schema，47-source mypy 与质量门 |
| 安装后流程 | 无项目依赖的隔离 wheel、仓库外同一完整流程和搬移副本复验；完整流程通过，证据 `installed-final-code/summary.json` |
| 本实现七 job | 实现 `6433e1cdf360e07d4d09e9294922380f68730018` / [run `36864006903`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36864006903) 七 job 全部 success；双平台新增场景、安装流程和上传均 success |

公开证据 `output/p26-stage-validation/`，本地真实工程仍只在忽略目录。初次安装后检查因验证脚本 resolve 了 venv 解释器符号链接、误用基础解释器而失败，已保留启动器路径修复。未知 XML 混合文本变化检测和有限 HTML 展示已补强。

P26 完成的范围为受限静态结构审查与快照影响，不包含厂商生成、实时调度、商业工具或物理 ECU。现转入[P27 声明式配置变更验收](p27-configuration-acceptance-plan.md)；P25 人工门独立保留。

本次 job ID、完整步骤与下一任务见进度账本；验收回填是后续纯文档 `[skip ci]` 提交，固定引用上述实现及 run。
