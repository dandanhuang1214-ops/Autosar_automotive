# AI 平台只读 Agent 留出题 v2：来源与内容核对

2026-11-13 冻结题集 [`ai-platform-agent-heldout-v2-20261113.json`](ai-platform-agent-heldout-v2-20261113.json)，SHA-256 `ff50b78de3c794b63430c3fd246e6c350edf52e63709094f8e2ecdb1fa271885`。在访问模型前，runner 对原始图谱字节 SHA、三题指定片段 ID、报告字节 SHA 做了校验。图谱 `c5ec7ffa…642489f`、项目报告 `8d825499…276b35460` 均匹配。每模型每题只运行一次，没有改题或重跑。

原始结果保存在本机忽略目录：`output/ai-agent-heldout-v2-20261113/deepseek-run.json`（SHA-256 `9dc752ac23ba0a27251adce261c06623418ffcd6d8f9fa646316fe15e17fd212`）与 `ollama-run.json`（`f3c5fdd661effed1732c54502d3b94f18eaf742e1bd06d6b2210189c30c0890b`）。六条 `runs/<trace-id>.json` 的哈希链与动作库存离线复验均通过；复验只证明记录完整，不能证明答案正确。

| 模型 / 题目 | 协议状态 | 要求工具、来源 | 内容核对 |
|---|---|---|---|
| DeepSeek / NRC 31 | 完成；2 模型、1 工具调用 | 仅图谱；目标 `chunk.week07.K015` 命中 | 回答说明 NRC 31 不足以断定 DID 不存在，候选片段 K014/K015 支持此边界；非盲核对通过。 |
| DeepSeek / expected 与 actual | 完成；2 模型、1 工具调用 | 仅项目事实，工具选择正确 | **不通过**。回答说报告未提供这两个字段；原始报告 `/requirements/0/expected` 与 `/requirements/0/actual` 均为 `passed`。当时 MCP 事实投影确实未导出两字段，模型将“工具未提供”误写为“报告未提供”。 |
| DeepSeek / DcmDspData | 完成；3 模型、2 工具调用 | 项目事实 + 图谱；目标 `chunk.week07.K021` 命中 | 区分项目静态验收、DcmDspData 候选解释与未验证的运行值；非盲核对通过。 |
| 本地 qwen3.5:2b / NRC 31 | 完成；2 模型、1 工具调用 | 仅图谱，但目标 K015 **未命中** | 内容引入候选未支持的 NRC 含义和泛化 DID 说法；来源/内容门不通过。 |
| 本地 qwen3.5:2b / expected 与 actual | 完成；3 模型、2 工具调用 | 多选了图谱；项目事实未提供两字段 | 从缺失的事实中补造 `expected/actual=passed`，即使巧合与原报告一致，也不构成有据回答；工具/内容门不通过。 |
| 本地 qwen3.5:2b / DcmDspData | `blocked: http_500`；3 模型、2 工具尝试 | 两种要求工具已选，目标 K021 命中 | 第三次 Ollama 模型调用返回 HTTP 500，无最终回答；保留原始失败，不推测根因。 |

严格来源与任务内容联合门：DeepSeek **2/3**，本地 2b **0/3**。DeepSeek 协议完成与所需工具选择为 3/3；本地协议完成 2/3，但两条完成答案均未过来源/内容门。这是同一公开项目及图谱上的留出题，不是外部工程泛化评估。此处为 Codex 非盲核对，用户此前“我觉得是可用的”是对旧两包回答的整体意见；**独立逐句人工审阅仍未完成**，模型输出维持 `unassessed`。

发现的产品缺口：MCP 读取经复验报告时只投影了审查断言的有限字段，不能完整回答报告验收项中已有的 `expected/actual`。后续修复应增加精确 JSON 指针事实并保持报告 SHA 绑定；旧题及本结果不重跑。不能用改进后的工具输出追认本次回答。
