# P30 只读 Agent 工具链与 LLM API 评审

状态：**remote-accepted**。实现 `3d69f544d0411cee201479b1b4bab9f17ce17f22` 的 [run `38189854764`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38189854764) 七个 job 全部成功。P30 整阶段仍为 implementing；本文只验收只读 Agent 基础设施，不把一次真实模型成功当作通用解释质量或工程判定验收。

## 结论

Workbench 已经接入 LLM，但不依赖 `simulink-assistant` 的 Python 包或对话链。它通过 provider-neutral `ModelClient` 边界调用现有 Ollama HTTP 服务，并按需通过受策略约束的 HTTP 接口读取已审核资料。

Docker 的职责是承载和隔离运行服务：

| 容器 / 边界 | 职责 | 不负责 |
|---|---|---|
| `simulink-assistant-ollama` | 本地模型推理和原生 function calling | 工程验收、工具权限、Agent 循环 |
| `simulink-assistant-api` | 文档注册表、搜索和 evidence 读取 | 信任某份资料或改写项目事实 |
| `simulink-assistant-qdrant` | 向量索引存储 | 证据裁决、引用正确性 |
| Workbench `AgentRunner` | 步骤循环、预算、工具许可、trace 和 fail-closed | 推理服务或向量数据库 |
| Workbench 确定性工具 | 报告复验、事实选择、策略校验 | 自由文本表达 |

因此，“Workbench 是否引用 LLM”的答案是：引用的是已部署服务接口，不是将另一个项目的内部实现当作 Workbench 内核。这使两个项目能独立演进，同时复用已有模型、索引和审核资料。

## 实现的 Agent 循环

`run-readonly-agent` 将操作者选定的项目报告、可选知识策略和服务地址绑定到运行时。模型不能提供文件路径、服务地址、策略 ID 或新工具。首批工具为：

- `project_verify_report`：重放项目报告，只返回完整性、顶层状态和报告摘要。
- `project_query_facts`：重放后最多选取 6 条与问题相关的结构化事实。
- `knowledge_retrieve_reviewed`：仅在 endpoint 与 digest-bound `agent-read` 策略成对提供时注册。
- `agent_finish`：协议级结束工具，必须引用已存在的 observation ID。
- `agent_decline`：协议级拒绝终态，只能返回 `requires_write`、`requires_external_action` 或 `outside_registered_tools`；它不授予权限，也不生成工程结论。

每个成功的只读工具在本次运行中只暴露一次；更具体的事实查询还会隐藏已被它覆盖的顶层报告复验。模型伪造隐藏工具、重复调用、未知工具、越界参数或伪造 evidence ID 都会被运行时拒绝。

Ollama 路径优先使用原生 `tools` / `tool_calls`；客户端不声明 tool calling 时才使用单对象 JSON Schema 动作包作为兼容回退。回退不放宽工具参数和证据校验。

## Token 与上下文设计

当前方案的节省点不是“少写一句 prompt”，而是缩小每一轮必须重发的状态：

1. 不发送整个 ECUC 工程或完整报告，先用确定性代码选择最多 6 条事实。
2. trace 保存完整工具结果；后续模型轮次只看经过哈希绑定的紧凑 projection。
3. 已完成或已被替代的工具不再发给模型，同时减少 schema token 和误调用空间。
4. 每轮输出、总 token、context window、模型调用、工具调用和观测字符有独立上限；墙钟预算在每一个步骤前后阻止继续。
5. 超时或无效 provider 响应也作为已发起的模型调用写入哈希链，不再记成 0 成本。

现阶段不将服务端会话状态或 prompt cache 当作必需前提。OpenAI 官方文档明确提醒，即使通过 `previous_response_id` 链接响应，之前的输入 token 仍会计入输入用量；因此服务端状态可减少传输和应用代码，但不能代替上下文精简。参见 [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state)。

## 与当前 Agent API / 框架的对照

| 一手实现模式 | 其要点 | Workbench 对应决策 |
|---|---|---|
| [Ollama tool support](https://ollama.com/blog/tool-support) | `tools` 提供函数 schema，模型返回 `tool_calls` | 已用真实 Ollama 0.31.1 验证原生路径；不让 provider 自动执行工具 |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) | 应用接收工具请求、执行并回传结果 | `ModelClient` 归一化 provider 协议，`ToolRegistry` 独立执行和验参 |
| [OpenAI tools](https://developers.openai.com/api/docs/guides/tools) | 可用工具可动态加载，以减少工具定义占用 | 本版通过成功后隐藏和 `supersedes` 先做最小动态暴露；后续再做命名空间搜索 |
| [Anthropic tool use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use) | 工具名、输入 schema、call ID 和 tool result 构成显式循环；工具定义和结果亦消耗 token | 已分离 call ID、完整 result、model projection 和 observation ID，并计量每轮 usage |
| [LangGraph durable execution](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph) | 节点边界 checkpoint、区分瞬时/模型可恢复/用户可解决错误、interrupt 审批 | 本版先完成只读 trace；checkpoint、幂等键、暂停/恢复和审批仍是下一层，未假装已实现 |
| [OpenAI agent evals](https://developers.openai.com/api/docs/guides/agent-evals) | 以 trace 检查选工具、参数、安全策略和回归 | 下一门冻结独立只读 Agent cohort，不用单次开发成功代替评测 |

这一设计符合当前 Agent 开发的核心原理：模型决定下一个受限动作，应用保持工具执行权、状态、权限、可观测性和验收权。它比将整条固定链改成一段 prompt 更可控，也比让模型直接生成文件路径或命令更安全。

## Trace 和故障分类

`readonly-agent-trace-0.1` 记录模型精确 digest、服务版本、工具 manifest、预算、每轮请求/响应摘要、usage、完整工具结果、模型 projection 及哈希链。模型请求超时会留下没有 response 的 `blocked` 事件；策略拒绝、无效动作或预算穷尽为 `refused`；只有引用存在 observation 的 `agent_finish` 才能使运行为 `passed`。

无论运行是否通过，模型摘要始终是 `semantic_status=unassessed`，不能改写项目的 passed/failed/blocked 状态。

## 用法

```bash
python -m automotive_workbench.cli run-readonly-agent \
  output/project/bundle/project-report.json \
  --goal "核对项目为什么被阻断" \
  --model qwen3.5:2b \
  --ollama-url http://127.0.0.1:11434 \
  --output output/agent/trace.json \
  --max-steps 3 --max-model-calls 3 --max-tool-calls 2 \
  --max-total-tokens 2048 --max-output-tokens-per-call 256 \
  --context-window 8192 --max-seconds 120

python -m automotive_workbench.cli verify-readonly-agent-trace \
  output/agent/trace.json
```

现有 Compose 不向宿主默认发布 Ollama 11434；在 `simulink-assistant_backend` 网络内应使用该部署的 Ollama 服务名。上面的 localhost 仅适用于用户明确发布或单独运行 Ollama 的环境。

`--timeout` 是每个 HTTP 请求的传输超时，`--max-seconds` 是 Agent 是否继续下一步的总墙钟预算。当前为同步 HTTP 调用，运行时能在请求返回后拒绝继续，但不能保证在底层 socket/Ollama 返回之前按总预算瞬时抢占中断。需要强实时 deadline 时应由进程级 supervisor 或支持取消的异步 transport 提供；本轮不声称该能力已验收。

## 验证结果与剩余边界

- 本地全量 446 tests 通过，2 个环境条件跳过；10 个 Agent 定向单测通过。
- 60 schemas、77 个 schema-bound 示例和 25 个 syntax-only 示例通过；Ruff、mypy、compileall、pip check 和 diff check 通过。
- 源码与隔离 wheel 的 12 类 HTTP 协议场景、Agent 知识策略、3 工具/4 模型轮次和服务停止后验签通过。wheel SHA-256 为 `a2d43ae44845511d1d784ec47bf29a643b2c73efbce10d1da736433b32cc7698`。
- 真实 Ollama 0.31.1 / `qwen3.5:2b` digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df` 的最终开发试验为 2 次模型调用、1 次事实工具调用、1574 tokens、12.706 秒；模型选中 `diagnostic_backend_mismatch` 和 `blocked`，然后引用该 observation 结束，离线验签通过。
- 前置开发试验暴露过 JSON grammar 不遵循、Ollama `function.index` 差异、冗余工具选择、token 耗尽和超时；这些被作为协议与编排修复依据，不算独立质量样本。
- 远端实现验收 completed/success：runtime-currency `114620063262`；core-contracts Windows `114620063355`、Ubuntu `114620063368`；runtime-evidence Ubuntu `114621961465`、Windows `114621961532`；controlled-rejections Ubuntu `114621961479`、Windows `114621961579`。后续纯文档状态提交不替代该实现 run。

独立只读 Agent cohort 已按[评测指南](p30-readonly-agent-evaluation-guide.md)完成真实 3/5 基线；[checkpoint、暂停与完成态幂等恢复](p30-agent-durability-guide.md)已通过远端七 job 验收，[审批请求与决定状态](p30-agent-approval-guide.md)已 local-accepted。未验收：一般复杂解释、真实资料适用性、流式调用、并发/崩溃 exactly-once、一次性授权消费、幂等副作用及执行/写入/硬件工具。批准记录不认证操作者且不授权执行。
