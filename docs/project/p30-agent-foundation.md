# P30 Agent-ready 模型与工具链基础

状态：implementing。本文定义 P30 内的 Agent 基础，不宣称模型解释质量或完整 Agent 已验收。

## 架构结论

工作台需要接入 LLM，但不应把现有确定性链路整体改写成提示词。目标分工是：

- Agent 负责理解目标、选择工具、组织多步调用、遇到缺证据时停止并向用户说明。
- 现有项目导入、ECUC 审查、影响分析、运行验证、证据复验继续作为带 schema 的确定性工具。
- 安全策略、事实引用、模型身份、运行前检查和最终验收仍由代码执行；模型不能覆盖这些结论。
- MCP 可作为后续工具互操作边界，但不是编排器、权限系统或证据判定器。

目标调用关系：

```text
CLI / UI
   -> AgentRunner（循环、预算、暂停/恢复、审批）
      -> ModelClient（Ollama；后续可增加其他 provider）
      -> ToolRegistry
         -> 只读事实 / 检索 / 审查 / 比较
         -> 可执行验证（显式策略）
         -> 写配置或硬件动作（默认禁用，单独审批）
      -> Trace + Evidence Bundle + Evals
```

固定工作流不会被删除：它们成为可直接调用、可独立测试和可回放的工具，也继续支持无模型运行。这样 Agent 替代的是固定编排，不是工程确定性。

## 当前模型接入

工作台不导入另一个仓库的 Python 包。当前路径通过受限 HTTP 直接调用本地 Ollama，并按需读取知识服务的原始检索接口；Docker 负责承载已有 Ollama、知识 API 和向量库等运行服务，不等于 Agent 本身。

本轮增加 `ModelClient` 协议与 `OllamaModelClient`：模型版本、精确模型 digest、结构化生成、原生 tool calling 和 usage 由统一边界提供。当前适配器只声明已经实现和测试的能力：结构化输出、原生函数选择、身份固定和 usage；streaming 仍明确为未实现，不能因 Ollama 服务本身支持就自动视为工作台能力。详见[只读 Agent 指南](p30-readonly-agent-guide.md)。

## 上下文与 token 原则

1. 模型只接收确定性选出的最小事实集，不接收整个工程或完整历史。
2. 工具清单后续采用按命名空间发现和延迟加载；默认提示不展开所有 schema。
3. 短草稿使用任务级输出预算。提示 0.23 的 160 字 draft-only 路径从 4096 收紧为 512 token；一般复杂解释暂保留 4096，待真实评测后继续缩小。
4. 拒绝、截断和解析失败也必须保存 provider usage，不能只统计成功调用。
5. 多步 Agent 上线前必须增加总 token、调用次数、墙钟时间和工具次数四类硬上限；压缩后的状态必须保存证据 ID，而不是把旧自然语言摘要当事实。

已有真实 0.22 样本的输入/输出 token 明显低于 4096 输出上限，但样本量和任务范围不足以确定一般解释预算。0.23 的 512 是安全的首个短草稿上限，不是所有 Agent 任务的统一常数。

## 可信度与权限门

在任何开放式 Agent 工具发现前，必须完成以下前置门：

- 知识来源策略版本化。当前兼容的 `legacy_trusted` 只能作为历史迁移状态，不能自动获得未来 Agent 的高可信工具权限；[0.1 策略](p30-knowledge-trust-policy.md)要求显式来源清单、审核记录和内容摘要绑定。
- 工具分级：`read`、`execute`、`write`、`hardware`。首版 Agent 只注册 read；后三级分别要求策略检查、用户批准和实际环境证据。
- 每次模型请求、工具请求/响应、模型身份、预算变化和审批决定可回放；敏感原文不写入公共评测集。
- prompt injection 视为工具输入数据。外部文档无权改变 system policy、扩大工具权限或批准自身来源。

## 递进交付

### A. 模型边界与观测（本轮）

- provider-neutral `ModelClient` 与 Ollama 适配器；旧 HTTP 传输和离线回放保持。
- 0.1–0.22 请求 payload 保持不变；0.23 单独承载严格短草稿契约和动态输出预算。
- 超过 160 字、额外字段或错误的 project/retrieval 模式措辞 fail closed。
- 失败调用也保存 token/耗时字段。

验收：单元测试、历史版本 payload 回归、合成 HTTP 场景、schema、类型检查、全量测试和远端七 job。它只验收基础设施，不验收模型内容质量。

### B. 只读 AgentRunner（remote-accepted）

- 增加 typed `ToolRegistry`、最多 N 步的显式循环、调用/时间/token 预算及完整 trace。
- 首批仅开放项目事实查询、报告复验和已审核资料检索；未知工具、参数越界、重复调用和预算耗尽均拒绝。
- 同一任务保留确定性 CLI 基线，比较 Agent 与固定路径的事实正确性、调用成本和失败模式。

### C. 耐久执行与审批

- checkpoint、幂等调用键、暂停/恢复和人工审批；进程重启后不得重复执行有副作用工具。
- 再逐级开放 virtual 执行，最后才讨论写配置和硬件操作。远端 virtual 成功不代表现场 ECU 验收。

### D. 独立评测

- 新的未见 cohort 分开测事实选择、工具选择、参数正确性、引用、拒绝、恢复和 token 成本。
- 模型/提示/工具 schema 任一变化都产生新的冻结版本；开发集不得转称 held-out。
- 在独立人工语义和资料适用性门通过前，P30 继续 implementing，Agent 输出不进入工程判定。

## 下一实现项

B 的最小只读 `ToolRegistry + AgentRunner` 已完成远端实现验收：原生函数调用、结构化回退、紧凑 projection、动态工具隐藏、显式预算和可离线验签 trace 由实现 `3d69f544d0411cee201479b1b4bab9f17ce17f22` / [run `38189854764`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38189854764) 七 job 固定。独立 v1 cohort 已得到真实 3/5 failed 基线；checkpoint、幂等键与暂停/恢复由 `a96193087bb9a09b01e635c37e57e3556024a686`、跨平台修复 `fdf5e217683b97454f1677b1a8bb7c72f18dad3d` / [run `38429351251`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38429351251) 七 job 验收。下一门实现 approval request/decision、拒绝和过期状态，仍不直接开放写入或硬件。
