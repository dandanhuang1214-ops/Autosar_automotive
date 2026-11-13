# AI 平台只读 Agent 0.1

状态：2026-11-13 本地实现和真实同题对照已完成；实现提交自身远端 CI 待记录。模型文字始终为 `semantic_status=unassessed`，不能改变项目验收状态。

## 能力与边界

聊天页新增“只读 Agent”。模型根据工程目标逐步选择 `graph_search` 和 `project_evidence`，最多三次模型调用、两次工具调用、总计 6000 token 和 120 秒继续执行预算。图谱工具只读已验证的本地活动快照，最多返回两个候选节点的四条片段，绑定图谱及来源文档 SHA；项目工具通过独立 Workbench MCP 服务重放已选报告，返回最多八条事实与报告 SHA。工程报告路径和 MCP 地址由 Host 绑定，模型只能给查询文本；写入类 MCP 工具不向 Agent 注册。

每步模型请求/响应、工具输入/完整结果、来源哈希、响应 ID、用量和失败原因写入本机 `runs/<trace-id>.json`。完成动作必须引用本轮全部 observation ID；未知工具、空查询、重复工具、虚构引用和服务失败均停止，页面明确显示未完成。`python -m automotive_workbench.ai_platform_agent <trace-path>` 可复验保存的 trace 哈希链及引用清单；这是记录完整性复验，原始来源的现场重放仍由图谱快照验证和 MCP 项目报告验证承担。云端模型没有本地 digest，记录服务返回的模型名和响应 ID，不伪造身份固定。Agent 0.1 使用受限 JSON 动作包；没有声称原生 DeepSeek function calling、流式 Agent 步骤或人工内容验收。

## 运行

先在单独终端启动只读 MCP 服务。`--root` 必须包含要查询的项目报告及完整验收包；不加 `--enable-project-actions`：

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.mcp_service \
  --root output/ai-project-final-20261103 --transport streamable-http --port 8768
```

在已设置 `DEEPSEEK_API_KEY` 的同一 WSL 终端启动 AI 平台：

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.knowledge_chat_server \
  --data output/knowledge-chat --port 8767 --provider deepseek \
  --mcp-url http://127.0.0.1:8768/mcp
```

网页选择“只读 Agent”，输入工程目标。只问图谱时可留空侧栏工程报告；需要项目事实时填写位于 MCP `--root` 下的绝对 `project-report.json` 路径。原普通聊天、流式取消、工程证据问答和项目候选接口保持兼容。MCP 停服时项目调用失败关闭，不能把图谱候选或模型文字提升为项目事实。模型或工具执行中的同步请求尚不支持即时取消；每轮返回后检查总预算。

## 验证与剩余门

冻结三题及原始证据见[同题对照](../research/ai-platform-agent-comparison-20261113.md)。替身正例覆盖图谱、项目、组合，负例覆盖不可用工具、虚构 observation、重复工具、MCP 故障及 trace 篡改；网页令牌、会话保存、旧聊天回归和桌面/375px 页面检查均通过。全量本地回归 584 项通过、2 项环境条件跳过；后续传输/界面修正的专项 26 项、Ruff、mypy、页面脚本语法及差异检查通过。

真实 DeepSeek 三题均完成所需工具选择；默认 `qwen3.5:2b` 三题均被动作边界拒绝，已安装的 Qwen 4B instruct 完成图谱单工具一题，其余两题未完成。这是本次已见开发题的非盲比较，不能替代新留出题和独立人工逐句内容审阅。首字测量仅在另行运行的同题普通聊天流式路径取得；同步 Agent 模型调用没有首字数据。远端实现验收、独立人工内容判断、更多未见任务和 P25 人工演示继续待完成。
