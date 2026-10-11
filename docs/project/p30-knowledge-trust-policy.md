# P30 Agent 知识来源信任策略

状态：implementing。本门只建立未来只读 Agent 的资料准入边界，不宣称资料内容、模型解释或完整 Agent 已通过人工验收。

## 为什么不能沿用旧字段

现有解释路径为兼容历史知识库，接受 `official`、`user_reviewed` 和 `legacy_trusted`。其中 `legacy_trusted` 只表示迁移前已有的信任标签，没有一份由 Workbench 固定的逐文档审核记录，也不能证明当前字节仍是审核时的字节。因此它可以继续支持历史回放，但不能自动成为 Agent 的高可信工具输入。

## 0.1 契约

`knowledge-source-policy-0.1` 是 `agent-read` 的显式 allowlist：

- 每个文档固定 `document_id`、完整文档 SHA-256 和 `official` / `user_reviewed` authority；schema 不允许 `legacy_trusted`。
- 每个条目必须记录 `approved` 决定、审核者和带时区的审核时间。
- `policy_id` 是除自身外整份策略正文的 canonical SHA-256，修改文档、摘要、authority 或审核记录都会使策略失效。
- 现场注册表仍必须同时满足 enabled、ready、approved，且 ID、摘要和 authority 与 allowlist 完全一致。
- 搜索命中还要通过 evidence endpoint 的逐字段一致性和 chunk 内容摘要绑定；任何未列入、漂移或 legacy 来源都 fail closed。

示例位于 `examples/knowledge/agent-read-policy.json`。它只绑定合成服务 fixture，不是生产资料清单。

## 与旧解释路径的关系

`retrieve()` 保留历史兼容语义，避免破坏提示 0.1–0.23 的归档回放。未来 Agent 工具只能调用 `retrieve_for_agent()`，且必须显式提供通过校验的策略；不存在“没有策略时默认信任全部 approved 文档”的回退。返回的 `agent-knowledge-retrieval-0.1` 在每个 source 上保存 policy ID 和审核记录，便于 trace、评测和离线复核。

## 尚未验收

- 当前合成 allowlist 不代表真实手册已完成独立审核。
- 还没有 `ToolRegistry + AgentRunner`，本门只提供它必须依赖的信任输入。
- 策略文件尚未签名，也不是组织身份、发布者身份或远程 attestation。
- `official` 仍是登记属性；实际生产清单需要人工核对发布者、版本、许可和适用 ECU/软件版本。

下一项是在此 fail-closed 入口上注册首批只读工具：项目事实查询、报告复验和受策略约束的资料检索，并加入步骤、token、工具次数和墙钟预算以及完整 trace。
