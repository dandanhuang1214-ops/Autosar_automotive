# AI 平台 Chat 0.1：直接 Ollama 对话

AI 平台与 Automotive Workbench 按产品职责分开。AI 平台首页是普通聊天；Workbench 是后续可选的工程资料与工具来源。当前工程证据问答仍可在“对话方式”中切换，旧 `/api/chat` 请求不带 `mode` 时保持原 `evidence` 行为。

## 启动与验收

在仓库根目录运行：

```bash
PYTHONPATH=src .venv/bin/python -m automotive_workbench.knowledge_chat_server \
  --data output/knowledge-chat --port 8767 \
  --ollama-url http://127.0.0.1:11434 --model qwen3.5:2b
```

打开 `http://127.0.0.1:8767/`。首页“普通聊天”不要求工程报告或知识图谱；发送消息会调用 Ollama `/api/tags`、`/api/version`、`/api/chat` 并再次核对模型 digest。回答旁显示本地时间格式的调用时刻和端到端耗时；展开可看 Ollama 自报的总耗时、加载、输入处理与生成耗时。模型离线或回答不完整时显示调用失败，不拿证据摘要冒充模型回答。原始传输和请求快照保存在 `--data/runs/`，属于本机私有数据。

Chat 0.1 暂按完整响应显示；冷启动模型时页面持续显示“正在调用本地 Ollama”，尚无逐字流式输出或中途取消。下一项先补这两个聊天交互，再接可选知识库。

短期记忆是当前会话最近最多 **6 组已完成**的用户/模型消息，另有约 12,000 字符的上下文上限；每次请求重新从本地 SQLite 取出，失败回答不进入后续模型上下文。不同会话互相隔离，完整聊天历史仍保存在 SQLite。长期记忆沿用现有 SQLite `memories`：用户在“管理长期记忆”中明确保存全局偏好或决定，可编辑、删除；普通聊天每次最多取最近 12 条全局记忆，跨会话使用。工程报告范围的记忆不进入普通聊天。模型回答不会自动写入长期记忆。

这套轻量实现参考了 [Ollama 的会话历史示例](https://github.com/ollama/ollama-python/blob/main/examples/chat-with-history.py)和 [LangGraph 对会话状态与跨会话存储的区分](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx)。[Mem0](https://github.com/mem0ai/mem0)提供记忆提取、检索、更新能力，[Letta](https://github.com/letta-ai/letta)面向更完整的有状态 Agent；现阶段单人本地 Chat 使用已有 SQLite 和显式保存即可，后续有大量长期记忆或 Agent 工作流时再对照评测。当前没有自动提取、向量召回、长对话摘要或相关性排序；长期对话只带最近 6 组，较早信息需要用户重提或明确保存。

## 目前的知识库接法

独立汽车知识图谱站点手动导出 `graph.json` 与对应来源 Markdown，再到“资料管理”导入并核验哈希。工程证据模式按问题中的标签/别名关键词找候选节点、关系，结合可选工程报告重放事实；图谱仍是待核实线索。**普通聊天当前不自动使用这套图谱。** 默认 `output/knowledge-chat` 目录没有激活图谱。现阶段没有文档向量检索、完整来源 Markdown 注入、自动文档同步或可验证模型引用，因此尚不是通用 RAG 知识库。

## 本机检查与下一步

- 真实 Ollama `0.31.1` / `qwen3.5:2b` 在无图谱/无报告的新会话完成两轮对话，第二轮准确回忆第一轮测试代号；模型 digest 与本机已安装版本一致。冷加载首次约 83 秒，其中 Ollama 自报加载约 81.5 秒；热态第二轮约 1.1 秒。原始记录在本机忽略目录 `output/ai-chat-live-20261104/`。
- 真实浏览器确认默认普通聊天、路径隐藏、模型回答和调用时刻可见、工程模式路径按需显示、新会话回到普通聊天、记忆管理入口可用；375px 手机宽度无横向溢出和页面 JS 错误。另以不可用的本机模型端口验证页面明确显示“调用失败”而无伪回答。截图与场景记录在 `output/playwright/p31-ai-chat/`。
- 浏览器中的同一短句指令曾得到偏题/虚构自我描述，也曾正确照答。这里只证明链路和状态显示，模型内容质量尚未通过独立评测。

下一步在 Chat 0.1 远端验收后补流式回答和中途取消，再设计可选资料附加与检索引用；MCP、工具调用和 Agent 以 AI 平台 Host 为主线继续。Workbench P31 0.2 已验收，Generate-Arxml 受控接入工作暂停且保留现有可行性证据，待 AI 平台基础能力稳定后再接入。
