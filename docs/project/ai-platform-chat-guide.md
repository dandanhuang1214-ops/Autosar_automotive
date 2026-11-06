# AI 平台 Chat 0.1：直接 Ollama 对话

状态：实现 `8bd5a6f`、界面状态修正 `c31c930`、跨平台测试修正 `d76d1da` / [core-ci run `41798800109`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/41798800109) head 一致，七个实际 job 均为 `success`，Chat 0.1 已远端验收。此状态由后续文档提交回填；文档提交本身不代表实现验收。

AI 平台与 Automotive Workbench 按产品职责分开。AI 平台首页是普通聊天；Workbench 是后续可选的工程资料与工具来源。当前工程证据问答仍可在“对话方式”中切换，旧 `/api/chat` 请求不带 `mode` 时保持原 `evidence` 行为。

## 启动与验收

在仓库根目录运行：

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.knowledge_chat_server \
  --data output/knowledge-chat --port 8767 \
  --ollama-url http://127.0.0.1:11434 --model qwen3.5:2b
```

打开 `http://127.0.0.1:8767/`。首页“普通聊天”不要求工程报告或知识图谱；发送消息会调用 Ollama `/api/tags`、`/api/version`、`/api/chat` 并再次核对模型 digest。回答旁显示本地时间格式的调用时刻和端到端耗时；展开可看 Ollama 自报的总耗时、加载、输入处理与生成耗时。模型离线或回答不完整时显示调用失败，不拿证据摘要冒充模型回答。原始传输和请求快照保存在 `--data/runs/`，属于本机私有数据。

Chat 0.1 的 `/api/chat` 完整 JSON 合约仍保留，供旧调用方使用。Chat 0.2 新增独立流式入口，见下文。

短期记忆是当前会话最近最多 **6 组已完成**的用户/模型消息，另有约 12,000 字符的上下文上限；每次请求重新从本地 SQLite 取出，失败回答不进入后续模型上下文。不同会话互相隔离，完整聊天历史仍保存在 SQLite。长期记忆沿用现有 SQLite `memories`：用户在“管理长期记忆”中明确保存全局偏好或决定，可编辑、删除；普通聊天每次最多取最近 12 条全局记忆，跨会话使用。工程报告范围的记忆不进入普通聊天。模型回答不会自动写入长期记忆。

这套轻量实现参考了 [Ollama 的会话历史示例](https://github.com/ollama/ollama-python/blob/main/examples/chat-with-history.py)和 [LangGraph 对会话状态与跨会话存储的区分](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx)。[Mem0](https://github.com/mem0ai/mem0)提供记忆提取、检索、更新能力，[Letta](https://github.com/letta-ai/letta)面向更完整的有状态 Agent；现阶段单人本地 Chat 使用已有 SQLite 和显式保存即可，后续有大量长期记忆或 Agent 工作流时再对照评测。当前没有自动提取、向量召回、长对话摘要或相关性排序；长期对话只带最近 6 组，较早信息需要用户重提或明确保存。

## Chat 0.2：流式聊天与现有知识助手

状态：实现提交 `61258bf9340273fffe6d032c53f72d967bc1f2a6` / [core-ci run `42143392204`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/42143392204) head 一致，`runtime-currency`、Windows/Ubuntu `core-contracts`、Windows/Ubuntu `runtime-evidence`、Windows/Ubuntu `controlled-rejections` 七个实际 job 全部 `success`，Chat 0.2 实现门已远端验收。本段由后续文档状态提交回填，不把文档提交视为实现 CI。普通聊天网页调用 `POST /api/chat/stream`，上游 Ollama `/api/chat` 明确使用 `stream: true`；浏览器逐段显示 NDJSON 内容。点击“停止生成”会调用 `POST /api/chat/cancel` 关闭本轮上游连接，已收到的文字以“回答未完成”保存；该轮不进入下一次模型上下文。旧 `/api/chat` 完整响应和工程证据问答合约保持兼容。

2026-11-06 纠正：上述实现提交把默认知识源误接成旧 `simulink-assistant` 的 `127.0.0.1:18080`。用户指出这不是所指的汽车知识源；修正实现 `7fd2b8b` / [run `42149301258`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/42149301258) head 一致且七 job 全部 `success`，已取消旧服务的默认连接，只有显式传入 `--knowledge-url` 才使用该服务。此前真实检索到的三条片段属于旧助手，**不能当成汽车知识图谱接入证据**。此前实现提交的远端 CI 结论只覆盖其当时的代码。

显式配置旧知识助手时，Chat 查询其 `/api/search`、`/api/documents` 和 `/api/evidence/{id}`。网页不要求用户逐次挑选资料；只接收服务已启用、ready、已审核且来源哈希一致的最多三条候选片段。回答旁显示检索状态和片段身份；模型的 `[资料序号]` 文字尚未经过逐条引用验证。无命中或服务不可用时，普通聊天继续运行，并明确显示知识库状态；不把无命中解释为整个知识库缺资料。

聊天页参考 [ChatGPT 网页侧栏与输入区更新](https://help.openai.com/en/articles/6825453-chatgpt-release-notes)和其[停止生成操作](https://help.openai.com/en/articles/7996703-troubleshooting-chatgpt-error-messages)：保留左侧可点选会话，把阅读列与底部输入框居中，收紧顶部工程信息，并在生成期间显示停止按钮。实现只借鉴交互结构，没有复制品牌样式。

本地证据：AI Chat、图谱聊天和项目入口专项 16 项通过，随后新增知识服务不可用专项 1 项通过；全量 566 tests 通过（2 项环境跳过）；Ruff 与差异检查通过。隔离 Ollama HTTP 服务和 Chromium 实测 `stream: true`、逐段显示、停止、历史保存，1440px/375px 无横向溢出、无页面脚本错误。现有 Docker Desktop 恢复后，真实 Ollama `0.31.1` 与旧 `simulink-assistant` 知识助手 `/health/ready` 均可用；首次真实聊天取得 370 个流式片段和完整回答，但 4 秒知识检索超时，明确记录 `unavailable`。按旧助手调用预算改为 30 秒后，第二条真实聊天检索到 3 条片段，Ollama 返回 197 个流式片段、完整回答；两次原始 trace 均留本机忽略目录 `output/ai-chat-live-20261106/`。这只验证旧助手调用链，不证明目标汽车知识源接入，也未验证模型引用文字逐项准确。

## 直接接入汽车知识图谱站点

目标来源固定为用户确认的私有 [汽车软件知识图谱站点](https://automotive-knowledge-graph-oct21.silly-civet-8184.chatgpt.site/)。本地启动时可用 `--sync-graph-site` 从站点读取 `graph.json` 和其中声明的来源 Markdown；站点私有访问令牌由终端无回显输入，或在本次进程环境中通过 `AUTOMOTIVE_GRAPH_SITE_TOKEN` 提供。程序只将令牌发送到固定站点，拒绝重定向、异常文件名、超限文件和来源哈希不符；全部文件验证后才切换 `--data/active.json`。不保存访问令牌。无令牌时可继续使用已验证的本地快照；在站点发生变化后须再次同步，当前没有后台自动刷新。

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.knowledge_chat_server \
  --data output/knowledge-chat --port 8767 --model qwen3.5:2b --sync-graph-site
```

首次真实同步已从站点版本 5 取回图谱 `c5ec7ffa61365ee0d179911b846dd26799eab014ea675a0b701facabd642489f`，包含 66 节点、90 关系、71 条主张与 71 片段；来源 Markdown 的哈希通过图谱声明核对，本机快照在忽略目录 `output/knowledge-chat/`。普通聊天不要求用户选择资料：每题自动在活动图谱的标签、别名、标题和摘要中检索，最多注入 6 条关联片段，并显示文档、片段、候选状态和来源原文链接。图谱主张仍是候选资料；模型引用内容的语义准确性需要独立核对，单凭编号存在不等于已验证。显式旧 `--knowledge-url` 仍保留兼容，启动新 Chat 时应移除旧命令中的 `--knowledge-url http://127.0.0.1:18080`。

本地核验：专项 18 项、全量 572 项测试通过（2 项环境跳过），Ruff 与差异检查通过；无头 Chromium 桌面/375px 手机能展开来源原文，页面无横向溢出或 JS 错误。真实 Ollama 流式问答两轮均检索到活动图谱片段，但 `qwen3.5:2b` 对清楚的字节问题仍扩写出未被片段支持的内容；收紧提示后仍有错误，因此**内容质量未通过**。页面来源区现显示候选摘录及“模型回答未核验”，供直接核对。原始本机 trace 在 `output/knowledge-chat/runs/`，不上传。

## 本机检查与下一步

- 真实 Ollama `0.31.1` / `qwen3.5:2b` 在无图谱/无报告的新会话完成两轮对话，第二轮准确回忆第一轮测试代号；模型 digest 与本机已安装版本一致。冷加载首次约 83 秒，其中 Ollama 自报加载约 81.5 秒；热态第二轮约 1.1 秒。原始记录在本机忽略目录 `output/ai-chat-live-20261104/`。
- 真实浏览器确认默认普通聊天、路径隐藏、模型回答和调用时刻可见、工程模式路径按需显示、新会话回到普通聊天、记忆管理入口可用；375px 手机宽度无横向溢出和页面 JS 错误。另以不可用的本机模型端口验证页面明确显示“调用失败”而无伪回答。截图与场景记录在 `output/playwright/p31-ai-chat/`。
- 浏览器中的同一短句指令曾得到偏题/虚构自我描述，也曾正确照答。这里只证明链路和状态显示，模型内容质量尚未通过独立评测。

下一步先核对模型引用的资料序号与实际检索片段是否一致，并补服务恢复场景；随后按依赖推进 AI 平台 MCP、工具调用和 Agent。Workbench P31 0.2 已验收，本轮不推进 Workbench。
