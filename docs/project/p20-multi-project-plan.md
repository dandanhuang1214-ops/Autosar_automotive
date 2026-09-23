# P20：声明驱动的多项目通信验证

状态：implementing，2026-09-23。这是 [长期路线 v3](roadmap.md) 的下一主阶段，整体尚未验收。P18/P19 已由提交 `88c24e2`、run `35748563878` 完成远端验收，P20a 已由实现提交 `1025907`、run `35809063044` 七 job 完成 remote-accepted；P20b 已由实现提交 `ef2e89e`、run `35875029401` 七 job 完成 remote-accepted，且两项目 SocketCAN 现场通过；下一实施包为 P20c 项目集成。

## 用户结果

新增一个公开通信项目时，只提供 DBC、canonical contract、BSW intent 和运行声明，即可完成静态检查、受门控的发送/接收、项目验收、审查和基线比较；无需修改 Python 内核或依赖 WindowStatus/WindowCommand 命名。

第二个公开样例选用合成的 ThermalControl：两个状态报文与一个请求报文，使用不同 CAN ID、信号数量和缩放值，并有本地 ECU Tx/Rx。它必须验证结构差异，不能只是给车窗文件改名。范围先限定 classic CAN、非 multiplexed 数值信号；不支持的布局必须在开始运行前显式拒绝。

## 代码审计与接入位置

| 位置 | 当前限制 | P20 处理 |
|---|---|---|
| `project_workflow.load_project` | 闭合的 project 0.1/0.2，仅三个输入；运行阶段无向量声明 | 新增显式版本的可选运行契约；旧版本走既有兼容路径；不增加任意命令执行 |
| `communication_runtime.run_communication_runtime` | 固定 0x100/0x200 filters | 从通过预检的计划导出精确过滤器，保留 isolation/probe/blocked |
| `can_runtime._round_trip/_command_receive` | 固定 WindowStatus/WindowCommand 与值 | 新建通用的、参数化的单消息交换内核；旧 lab 作为固定学习实验继续兼容 |
| `communication_evidence.run_communication_chain` | 将已有固定运行报告与映射路径绑定 | 逐声明消息/信号按 identity + direction + frame ID 绑定，不按列表位置推断 |
| `project_review` / `project_comparison` | 读取当前项目报告和阶段状态 | 验证新版本来源、阶段、引用及迁移；必要时显式扩版本，禁止悄悄改变原契约含义 |

## 四个实施包与验收

### P20a：运行声明与开总线前预检

实现 loader、契约和编译为运行计划的纯函数。初稿字段：本地 ECU 取自 intent；每个向量包含稳定 ID、DBC message 名、local direction、数值信号映射和有界 timeout；backend/channel 继续由 BusConfig 显式指定。具体 JSON 结构在编码前结合现有项目 schema 一次性确定，不先增加空 schema 占位。

预检应确认：消息与信号存在、稳定 ID 唯一、声明方向与 intent/DBC 一致、所有编码所需信号都有值、数值有限且可编码、classic CAN 限制成立、超时为有界正值。信号物理值的浮点量化比较需用原始编码值或明确量化规则，不能随意设浮点容差。非法输入必须在任何 bus open/send 和运行输出写入之前拒绝。

验收：合法车窗与 ThermalControl 计划；未知消息/信号、重复 ID、缺值、方向不符、不可编码值、bool 冒充数值、非有限值、非法 timeout、不支持 multiplex/CAN FD 等负例；用总线 mock 验证无副作用。loader/schema 的共同约束要有一致性测试。

### P20b：通用消息执行

复用 python-can/cantools 与既有 BusConfig，不编写新协议栈。对于 local Tx，由 local 发送、peer 接收；local Rx 则由 peer 发送、local 接收。报告保留声明、实际 frame ID/payload、解码值、结果/原因与输入哈希。过滤器来自已验证计划；多消息运行不依赖公开样例的名称、ID 或数量。

验收：三个不同报文的双向执行；编码/解码量化、错误 ID、无响应/超时、后端 blocked；任何异常均关闭 bus。virtual 是跨平台基线；SocketCAN 使用已有通道锁入口，现场未执行时不写成通过。

### P20c：接入项目到审查的完整流程

新增项目版本并保留 0.1/0.2。输入快照包含运行声明；静态失败时不得发送；声明向量报告与 communication paths 绑定，验收项通过稳定 locator 引用。只有具有兼容比较依据的项目版本才允许 baseline/candidate 比较，不将“同名 requirement ID”自动当作等价业务定义。

验收：两项目正常运行；一个输入变化导致静态失败并跳过通信；一个合法输入下的运行失败；项目 review 引用复验；比较稳定/回归/不可比较；整包迁移后复验。旧 P15–P19 示例和安装后 consumer 保持通过。

### P20d：完整公开交付与阶段冻结

在现有 runtime-evidence job 执行第二项目及回归案例，归档声明/运行/审查/比较结果；不要仅运行单元测试就认定项目可用。提供最小项目编写说明，列出支持与拒绝的 CAN/DBC 特性。实际跑一次 Linux SocketCAN（环境允许时），与 GitHub virtual 证据分开计量。

验收：本地全量及质量门、Windows/Ubuntu runtime/core/rejection、Python 3.14 共七 job，记录实现提交及 run URL。SocketCAN 现场门若 blocked，先交付跨平台 virtual 能力并明确现场未冻结；不会伪造整体全完成。

## 退出与回退

旧 CLI/样例保持兼容，新运行入口遇到不支持的输入显式拒绝，不能静默改为车窗实验。回退可停用新项目版本继续旧版本；新比较/运行契约采用显式版本管理。

P20 完成后直接进入 P21 配置对象图与变更影响。若实现中发现影响基础接口的缺口，在此计划记录调整及证据；不要用额外报告页面或新协议旁支替代多项目验收。

P20a 实际入口、支持边界及量化规则见 [通信声明说明](p20-communication-declarations.md)。P20b 已从计划的 frame ID 和 extended 标志生成匹配掩码；未改动既有只适用于标准帧的 `exact_can_filters`。
