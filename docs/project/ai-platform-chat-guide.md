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

状态：本地实现与验证完成，远端 CI 尚待实现提交后跟进。普通聊天网页调用 `POST /api/chat/stream`，上游 Ollama `/api/chat` 明确使用 `stream: true`；浏览器逐段显示 NDJSON 内容。点击“停止生成”会调用 `POST /api/chat/cancel` 关闭本轮上游连接，已收到的文字以“回答未完成”保存；该轮不进入下一次模型上下文。旧 `/api/chat` 完整响应和工程证据问答合约保持兼容。

服务器默认以 `--knowledge-url http://127.0.0.1:18080` 自动查询**已有知识助手**的 `/api/search`、`/api/documents` 和 `/api/evidence/{id}`。网页不要求用户逐次挑选资料；只接收现有服务已启用、ready、已审核且来源哈希一致的最多三条候选片段。回答旁显示检索状态和片段身份；模型的 `[资料序号]` 文字尚未经过逐条引用验证。无命中或服务不可用时，普通聊天继续运行，并明确显示知识库状态；不把无命中解释为整个知识库缺资料。服务地址属于启动配置，不作为用户每次提问的选择。

聊天页参考 [ChatGPT 网页侧栏与输入区更新](https://help.openai.com/en/articles/6825453-chatgpt-release-notes)和其[停止生成操作](https://help.openai.com/en/articles/7996703-troubleshooting-chatgpt-error-messages)：保留左侧可点选会话，把阅读列与底部输入框居中，收紧顶部工程信息，并在生成期间显示停止按钮。实现只借鉴交互结构，没有复制品牌样式。

本地证据：AI Chat、图谱聊天和项目入口专项 16 项通过，随后新增知识服务不可用专项 1 项通过；全量 566 tests 通过（2 项环境跳过）；Ruff 与差异检查通过。隔离 Ollama HTTP 服务和 Chromium 实测 `stream: true`、逐段显示、停止、历史保存，1440px/375px 无横向溢出、无页面脚本错误。现有 Docker Desktop 恢复后，真实 Ollama `0.31.1` 与原知识助手 `/health/ready` 均可用；首次真实聊天取得 370 个流式片段和完整回答，但 4 秒知识检索超时，明确记录 `unavailable`。按现有知识助手调用预算改为 30 秒后，第二条真实聊天检索到 3 条已审核片段，Ollama 返回 197 个流式片段、完整回答；两次原始 trace 均留本机忽略目录 `output/ai-chat-live-20261106/`。这验证了调用链和资料注入，尚未验证模型引用文字逐项准确。

## 既有图谱接法

独立汽车知识图谱站点手动导出 `graph.json` 与对应来源 Markdown，再到“资料管理”导入并核验哈希。这是原工程证据模式的候选图谱路径；普通聊天 0.2 自动连接的是已有知识助手的已审核资料接口，不要求图谱导入。默认 `output/knowledge-chat` 目录没有激活图谱。当前没有自动文档同步或可验证模型引用。

## 本机检查与下一步

- 真实 Ollama `0.31.1` / `qwen3.5:2b` 在无图谱/无报告的新会话完成两轮对话，第二轮准确回忆第一轮测试代号；模型 digest 与本机已安装版本一致。冷加载首次约 83 秒，其中 Ollama 自报加载约 81.5 秒；热态第二轮约 1.1 秒。原始记录在本机忽略目录 `output/ai-chat-live-20261104/`。
- 真实浏览器确认默认普通聊天、路径隐藏、模型回答和调用时刻可见、工程模式路径按需显示、新会话回到普通聊天、记忆管理入口可用；375px 手机宽度无横向溢出和页面 JS 错误。另以不可用的本机模型端口验证页面明确显示“调用失败”而无伪回答。截图与场景记录在 `output/playwright/p31-ai-chat/`。
- 浏览器中的同一短句指令曾得到偏题/虚构自我描述，也曾正确照答。这里只证明链路和状态显示，模型内容质量尚未通过独立评测。

下一步先完成 Chat 0.2 实现提交及七 job 远端 CI；再补可验证引用与服务恢复场景。MCP、工具调用和 Agent 以 AI 平台 Host 为主线继续。Workbench P31 0.2 已验收，本轮不推进 Workbench。
